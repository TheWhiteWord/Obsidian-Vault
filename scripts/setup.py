"""
Obsidian-vault setup questionnaire (the deterministic stage machine).

Install-time only: location → name → preset → per-role profile
assignment → finalize. The agent is the human interface (relays
SETUP:question JSON, feeds answers back via --answer); the script owns
every decision. Run once per stage:

    python3 scripts/setup.py --setup                    # print current question
    python3 scripts/setup.py --setup --answer <value>   # validate + build stage
    python3 scripts/setup.py --setup --reset            # start over

Post-install mutations live in scripts/roles.py (--role
bind/unbind/transfer/list); the mechanical core is scripts/vault_ops.py.
Environment:
    HERMES_HOME   override the Hermes home (default: ~/.hermes).
    OBSIDIAN_VAULT_PLUGIN   override the plugin dir (default: repo root).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from vault_ops import (_active_agent_names, _block_text, _create_profile,
                       _grant_role, _revoke_globs, _role_skill,
                       _soul_identity, enable_plugin_for_profile,
                       ensure_peer_memory, ensure_soul_sections,
                       install_cron_jobs, install_skills, profile_home,
                       refresh_profiles, scaffold_vault, seed_profile_config)

# --- setup stage machine (P6 redesign, 2026-08-05) -------------------------

#: Machine-readable markers the agent relays verbatim (the agent is the
#: human interface; the script owns every decision).
Q_MARK = "SETUP:question"
B_MARK = "SETUP:built"
A_MARK = "SETUP:alert"
D_MARK = "SETUP:done"

SETUP_STATE_FILENAME = ".obsidian-vault-setup.json"

#: Roles asked per preset, in ask order. The default profile is implicit
#: (system owner, D8); each listed role gets a profile assigned to it.
ROLES_STANDARD = ["manager", "creative", "dev", "researcher"]
ROLES_BLANK = ["manager"]

#: Role metadata: the profile name `create` yields, the skill role, the
#: contributor domain glob, and the profile description.
ROLE_META = {
    "manager": {
        "profile": "vault-manager", "skill": "manager", "domain": None,
        "desc": "Vault maintenance: meta/config/read, no content ownership",
    },
    "creative": {
        "profile": "creative", "skill": "contributor", "domain": "creative",
        "desc": "Vault contributor for the creative domain",
    },
    "dev": {
        "profile": "dev", "skill": "contributor", "domain": "coding",
        "desc": "Vault contributor for the coding domain",
    },
    "researcher": {
        "profile": "researcher", "skill": "contributor", "domain": None,
        "desc": "Vault contributor for shared research (work/*/knowledge/**)",
    },
}


def _setup_state_path(hermes_home: Path) -> Path:
    return hermes_home / SETUP_STATE_FILENAME


def _load_setup_state(hermes_home: Path) -> dict:
    p = _setup_state_path(hermes_home)
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"stage": 0, "answers": {}}


def _save_setup_state(hermes_home: Path, state: dict) -> None:
    # The setup state is often the first thing written into a virgin home
    # (fresh-machine E2E) — create the home dir rather than crashing.
    hermes_home.mkdir(parents=True, exist_ok=True)
    _setup_state_path(hermes_home).write_text(
        json.dumps(state, indent=2), encoding="utf-8")


def _stage_list(state: dict) -> list[str]:
    """The stage sequence for this run: 3 fixed + one profile stage per role.

    Preset is stage 3, so until answered the default (standard) drives the
    role list — the agent sees the same 8 stages either way (blank reuses
    the same sequence; its profile stages are a single manager role).
    """
    preset = state["answers"].get("preset", "standard")
    roles = ROLES_STANDARD if preset == "standard" else ROLES_BLANK
    return (["location", "name", "preset"]
            + [f"profile:{r}" for r in roles]
            + ["finalize"])


def _stage_question(stage: str) -> dict:
    """The question for a stage — relayed verbatim by the agent."""
    if stage == "location":
        return {"stage": stage, "kind": "text",
                "prompt": "Where should the vault live? (absolute path "
                          "to the parent folder — the vault gets its own "
                          "folder inside it)"}
    if stage == "name":
        return {"stage": stage, "kind": "text",
                "prompt": "Vault name (the folder that will hold the "
                          "vault, e.g. MyVault)"}
    if stage == "preset":
        return {"stage": stage, "kind": "choice",
                "prompt": "Which preset?", "choices": ["standard", "blank"]}
    if stage.startswith("profile:"):
        role = stage.split(":", 1)[1]
        return {"stage": stage, "kind": "profile",
                "prompt": f"Profile for role '{role}'?",
                "choices": ["create", "default", "existing:NAME"]}
    return {"stage": stage, "kind": "none", "prompt": ""}


def _validate_answer(stage: str, answer: str, hermes_home: Path) -> tuple[bool, str]:
    """Validate one answer. (ok, alert) — alert is looped back to the user."""
    if stage == "location":
        if not answer.strip():
            return False, "vault location cannot be empty"
        if not Path(answer).expanduser().is_absolute():
            return False, "vault location must be an absolute path"
        return True, ""
    if stage == "name":
        if not answer.strip():
            return False, "vault name cannot be empty"
        if "/" in answer or "\\" in answer:
            return False, "vault name cannot contain slashes"
        if answer.strip() in (".", ".."):
            return False, "vault name cannot be '.' or '..'"
        return True, ""
    if stage == "preset":
        if answer not in ("standard", "blank"):
            return False, "preset must be 'standard' or 'blank'"
        return True, ""
    if stage.startswith("profile:"):
        role = stage.split(":", 1)[1]
        if answer == "create":
            name = ROLE_META[role]["profile"]
            if profile_home(hermes_home, name).is_dir():
                return False, (f"profile '{name}' already exists — use "
                               f"'existing:{name}' or 'default' instead")
            return True, ""
        if answer == "default":
            return True, ""
        if answer.startswith("existing:"):
            name = answer.split(":", 1)[1].strip()
            if not name:
                return False, "existing profile name is empty"
            if not profile_home(hermes_home, name).is_dir():
                return False, f"profile '{name}' does not exist"
            return True, ""
        return False, "answer must be 'create', 'default', or 'existing:NAME'"
    if stage == "finalize":
        # A proceed-marker: the agent calls with any answer ('' is natural)
        # to trigger the terminal build. kind "none" tells the agent this
        # stage asks nothing — it is the recap/finalize trigger.
        return True, ""
    return False, f"stage '{stage}' takes no answer"


def _resolve_profile(role: str, answer: str) -> str:
    """The profile name an answer maps a role onto."""
    if answer == "create":
        return ROLE_META[role]["profile"]
    if answer == "default":
        return "default"
    return answer.split(":", 1)[1].strip()


def _assignments(state: dict) -> dict[str, set[str]]:
    """Map of profile name -> set of roles assigned to it (accumulation)."""
    out: dict[str, set[str]] = {}
    for stage, answer in state["answers"].items():
        if stage.startswith("profile:"):
            role = stage.split(":", 1)[1]
            out.setdefault(_resolve_profile(role, answer), set()).add(role)
    return out


def _vault_root(state: dict) -> Path:
    """The vault root: the name answer names the vault's folder inside the
    location (2026-08-07) — the user picks the parent and the name; the
    installer creates `<location>/<name>`."""
    loc = Path(state["answers"]["location"]).expanduser()
    name = state["answers"].get("name", "").strip()
    return loc / name if name else loc


def _build_stage(stage: str, answer: str, state: dict,
                 hermes_home: Path, dry_run: bool) -> list[str]:
    """Build the aspect a stage answer finalises. Returns recap lines.

    The stage machine owns the sequence and every decision; this is the
    only place fs work happens. Location/name/profile answers only
    record (accumulation needs all answers); the preset answer scaffolds
    the tree; finalize creates profiles + skills + SOUL + grants + env.
    """
    if stage == "preset":
        vault_root = _vault_root(state)
        created = scaffold_vault(vault_root, answer, dry_run=dry_run)
        return [f"vault scaffolded ({answer}): {len(created)} dirs"]
    if stage == "finalize":
        return _finalize(state, hermes_home, dry_run)
    return []  # location / name / profile:N — recorded, built at finalize


def _finalize(state: dict, hermes_home: Path, dry_run: bool) -> list[str]:
    """The terminal stage: create profiles, install skills, grants, env.

    Builds every profile the answers named, plus the default profile
    (system owner, D8 — always present). Role accumulation is applied
    here: a profile holding manager + any contributor gets the combined
    skill role and both directive files.
    """
    vault_root = _vault_root(state)
    roles_path = vault_root / ".vault" / "roles.yaml"

    # default always participates (system owner); named assignments on top.
    assignments = _assignments(state)
    profiles: dict[str, set[str]] = {"default": {"system"}}
    for prof, roles in assignments.items():
        profiles.setdefault(prof, set()).update(roles)

    out: list[str] = []
    for prof, roles in sorted(profiles.items()):
        skill_role = _role_skill(roles)
        is_default = prof == "default"
        created = False
        if dry_run:
            out.append(f"[dry-run] profile {prof}: skill={skill_role} "
                       f"roles={sorted(roles)}")
        else:
            if not is_default and not profile_home(hermes_home, prof).is_dir():
                desc = "; ".join(ROLE_META[r]["desc"] for r in roles
                                 if r in ROLE_META) or "Vault profile"
                _create_profile(prof, desc)
                created = True
            pskills = profile_home(hermes_home, prof) / "skills"
            install_skills(pskills, role=skill_role)
            soul = profile_home(hermes_home, prof) / "SOUL.md"
            # P8.1: a full role SOUL is written only for a profile CREATED
            # by this run (a fresh `hermes profile create` seed — zero
            # user intent). Existing profiles (default / existing:NAME)
            # keep their identity: block-only append. The manager maps to
            # its own identity template (2026-08-06 review), same gate.
            identity = _soul_identity(roles) if created else ""
            ensure_soul_sections(soul, skill_role,
                                 profile_name=prof, identity=identity)
            ensure_peer_memory(hermes_home, prof)
            seed_profile_config(hermes_home, prof)
            enable_plugin_for_profile(hermes_home, prof, vault_root)
        out.append(f"profile {prof}: {skill_role} "
                   f"({'default system owner' if is_default else ' + '.join(sorted(roles))})")

    # Grants — the manager role activates/creates the manager block; the
    # contributor roles extend-or-append their domain globs.
    if roles_path.is_file():
        for prof, roles in sorted(assignments.items()):
            for role in sorted(roles):
                if role == "system":
                    continue
                if _grant_role(roles_path, prof, role, dry_run=dry_run):
                    out.append(f"roles.yaml: {prof} ← {role}")
        # P7: unassigned preset agents must not linger. A preset agent no
        # profile maps to (one-agent installs: creative/dev/researcher left
        # active) would hold grants the assignment never meant to give —
        # and under ownership rules a leftover owning the same domain as
        # the assignee makes every write there ambiguous. Comment out.
        import re as _re
        mapped = set(assignments) | {"default"}
        for name in _active_agent_names(roles_path):
            if name in mapped:
                continue
            block = _block_text(roles_path, name)
            pairs = [(m.group(1), _re.findall(r'"([^"]+)"', m.group(2)))
                     for m in _re.finditer(
                         r"(?m)^    ([a-zA-Z0-9_-]+):\s*\[(.*?)\]", block)]
            if pairs and _revoke_globs(roles_path, name, pairs,
                                       dry_run=dry_run):
                out.append(f"roles.yaml: {name} commented out (unassigned)")

    # Scheduled maintenance cron on the manager profile — role-dependent:
    # whatever profile the questionnaire bound the manager role to
    # (one-agent installs land on `default`), never a hardcoded name.
    for prof in sorted(p for p, roles in profiles.items()
                       if "manager" in roles):
        out.extend(install_cron_jobs(prof, dry_run=dry_run))

    if not dry_run:
        _save_setup_state(hermes_home, {"stage": 0, "answers": {}})
    out.append("Done. Restart Hermes to activate the new profiles.")
    return out



def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)

    # Setup questionnaire (P6 stage machine) — the new install flow.
    ap.add_argument("--setup", action="store_true",
                    help="Run the deterministic setup questionnaire "
                         "(stage machine; the agent relays questions)")
    ap.add_argument("--answer", metavar="VALUE",
                    help="Answer the current stage's question "
                         "(with --setup)")
    ap.add_argument("--reset", action="store_true",
                    help="(with --setup) wipe the in-progress state "
                         "and start over")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print actions without performing them")
    ap.add_argument("--refresh", action="store_true",
                    help="Re-apply the installer's per-profile state to a "
                         "live install (SOUL blocks, memory seeds, skills, "
                         "config, plugin enable) — run after `hermes "
                         "plugins update` to pick up new managed sections")
    args = ap.parse_args()

    hermes_home = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()

    if args.refresh:
        for line in refresh_profiles(hermes_home, dry_run=args.dry_run):
            print(f"{B_MARK} {line}")
        return 0

    if not args.setup:
        ap.print_help()
        return 1

    return _run_setup(hermes_home, args.answer, args.reset, args.dry_run)


def _run_setup(hermes_home: Path, answer: str | None, reset: bool,
               dry_run: bool) -> int:
    """Drive the deterministic questionnaire — one stage per invocation.

    The agent relays: run without --answer to print the current question;
    run with --answer to validate + build that stage. An invalid answer
    loops back (alert + the same question). The finalize stage prints the
    recap and clears the state.
    """
    if reset:
        p = _setup_state_path(hermes_home)
        if p.is_file():
            p.unlink()
            print(f"{B_MARK} state reset")
        return 0

    state = _load_setup_state(hermes_home)
    stages = _stage_list(state)
    idx = state["stage"]
    if idx >= len(stages):
        print(f"{D_MARK} setup already complete — run with --reset to "
              "start over")
        return 0

    stage = stages[idx]
    if answer is None:
        print(f"{Q_MARK} " + json.dumps(_stage_question(stage)))
        return 0

    ok, alert = _validate_answer(stage, answer, hermes_home)
    if not ok:
        print(f"{A_MARK} {alert}")
        print(f"{Q_MARK} " + json.dumps(_stage_question(stage)))
        return 1

    state["answers"][stage] = answer
    recap = _build_stage(stage, answer, state, hermes_home, dry_run)
    for line in recap:
        print(f"{B_MARK} {line}")
    if stage == "finalize":
        # Completion marker — the agent relays it verbatim; setup is over.
        print(f"{D_MARK} setup complete — restart Hermes to activate")
        return 0
    state["stage"] = idx + 1
    _save_setup_state(hermes_home, state)
    nxt = stages[idx + 1]
    print(f"{Q_MARK} " + json.dumps(_stage_question(nxt)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

