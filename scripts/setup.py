"""Obsidian-vault installer (setup questionnaire) + growth protocol.

The setup flow (P6, 2026-08-05) is a DETERMINISTIC STAGE MACHINE: the
script owns the sequence, validation, and every filesystem decision; the
agent is only its human interface (relays questions, feeds answers back).
Run it once per stage:

    python3 scripts/setup.py --setup                    # print current question
    python3 scripts/setup.py --setup --answer <value>   # validate + build stage
    python3 scripts/setup.py --setup --reset            # start over

Questions come back machine-readable (SETUP:question JSON); the agent
relays them in-chat and passes the answer via --answer. An invalid answer
loops back with SETUP:alert + the same question. The final stage
(finalize) prints the recap and resets the state.

Stages (standard preset): location → name → preset → profile:manager →
profile:creative → profile:dev → profile:researcher → finalize. Each
profile stage accepts `create` (canonical name), `default` (map the role
onto the default profile), or `existing:NAME`. Role accumulation is
supported: mapping several roles onto one profile yields the combined
skill role (both directive files) and unioned grants.

Growth protocol (P5c) — manager:
    python3 scripts/setup.py --vault /path/to/vault \
        --add-contributor NAME                  # profile + overlay + SOUL + env
    python3 scripts/setup.py --vault /path/to/vault \
        --add-domain DOMAIN --owner PROFILE [--config FILE]
                                                # tree + config + grant + manifest
    # Growth protocol (P5c) — domain owner:
    python3 scripts/setup.py --vault /path/to/vault \
        --add-subdomain work/<domain>/<sub> --owner PROFILE
                                                # ride obsidian_scaffold; manifest entry

Profile configs:
    Named profiles are seeded from the system `default` config.yaml as a
    working baseline (model, memory, plugins, etc.), then the plugin is
    enabled and the OBSIDIAN_* env vars written on top. Review each
    profile's model/memory/plugins after install — a profile config that
    already declares `memory:` is treated as customised and left alone.

Environment:
    HERMES_HOME   override the Hermes home (default: ~/.hermes). Tests use
                  a scratch dir.
    OBSIDIAN_VAULT_PLUGIN   override the plugin dir (default: repo root).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# --- paths ----------------------------------------------------------------

PLUGIN_DIR = Path(os.environ.get(
    "OBSIDIAN_VAULT_PLUGIN",
    str(Path(__file__).resolve().parents[1]),
))
BUNDLED_SKILL = PLUGIN_DIR / "skills" / "note-taking" / "obsidian-vault"
MANAGER_SKILL = PLUGIN_DIR / "skills" / "note-taking" / "obsidian-vault-management"
STARTER = PLUGIN_DIR / "examples" / "starter-vault"
BLANK = PLUGIN_DIR / "examples" / "blank-vault"

#: The growth subcommands import the engine's grant machinery (add_subdomain
#: rides obsidian_scaffold's grant check); make the plugin root importable
#: no matter where setup.py is invoked from.
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

# --- SOUL sections (P5b) ---------------------------------------------------

#: Anchor marking the installer-managed SOUL block. Re-runs replace the
#: block in place (update-safe); the pre-P5b single-paragraph directive is
#: upgraded in place on first contact.
SOUL_ANCHOR = "<!-- vault-soul: managed by the installer; do not edit -->"


def _soul_block(role: str) -> str:
    """The SOUL sections for a role: contributor | manager | combined.

    One `## Vault` umbrella with lean `###` subsections (06-growth-design
    §3.1). Every bullet names a tool or a reference — never prose
    instruction. Contributor and combined carry the convention sections and
    the manifest; the manifest starts empty-but-directed and the growth
    protocol (P5c) appends entries. A manager SOUL carries NO conventions
    sections and NO manifest add-marker — that marker's absence is what
    makes growth subcommands refuse to touch manager SOULs (conventions are
    contributor-maintained). Combined is dedicated text, not concatenation:
    it states the dual role once (2026-08-05).
    """
    ops = {
        "contributor": (
            "- For any task touching an Obsidian vault, load the "
            "`obsidian-vault` skill first — it holds the writing loop "
            "and the conventions.\n"
        ),
        "manager": (
            "- For any task touching an Obsidian vault, load the "
            "`obsidian-vault-management` skill first — it holds the "
            "sweep, triage, and growth flows.\n"
        ),
        "combined": (
            "- Author and maintain: load `obsidian-vault` for writing "
            "rules, `obsidian-vault-management` for the sweep and "
            "triage.\n"
        ),
    }
    issues = {
        "contributor": (
            "### Issues\n"
            "- Raise and track ledger issues: `obsidian_issue`, "
            "`obsidian_issue_list`, `obsidian_issue_resolve`. See "
            "`references/issues.md`.\n"
        ),
        "manager": (
            "### Issues\n"
            "- Triage the ledger and run the sweep: "
            "`obsidian_issue_list`, `obsidian_issue_resolve`, "
            "`obsidian_maintain`. See `references/issues.md`, "
            "`references/maintenance.md`.\n"
        ),
        "combined": (
            "### Issues\n"
            "- Raise like a contributor, triage like the manager: "
            "`obsidian_issue`, `obsidian_issue_list`, "
            "`obsidian_issue_resolve`, `obsidian_maintain`. See "
            "`references/issues.md`, `references/maintenance.md`.\n"
            "- Dual role: sweep findings about your own domains are "
            "yours to fix; about other domains, raise them.\n"
        ),
    }
    conventions = (
        "### Convention maintenance\n"
        "- Maintained conventions live in "
        "`conventions/<vault>-conventions.md`; create/edit when a user "
        "preference about writing rules lands; register below.\n"
    )
    manifest = (
        "### Convention manifest\n"
        "<!-- maintained by the growth protocol; one line per convention "
        "file -->\n"
        "<!-- add: - `conventions/<vault>-conventions.md` — description "
        "(domain) -->\n"
    )

    if role == "manager":
        return (
            f"{SOUL_ANCHOR}\n"
            "## Vault\n"
            "- Operating this vault — tools, issues, and maintenance. "
            "Each subsection points at what governs it.\n"
            "### Vault operations\n"
            f"{ops[role]}"
            f"{issues[role]}"
        )
    return (
        f"{SOUL_ANCHOR}\n"
        "## Vault\n"
        "- Operating this vault — tools, conventions, issues, and "
        "maintenance. Each subsection points at what governs it.\n"
        "### Vault operations\n"
        f"{ops[role]}"
        f"{issues[role]}"
        f"{conventions}"
        f"{manifest}"
    )

# --- composition (pure) ---------------------------------------------------

def _identical_dir(a: Path, b: Path) -> bool:
    """True when every file under ``a`` matches ``b`` (a stale copy of b)."""
    try:
        a_files = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    except OSError:
        return False
    if not a_files:
        return False
    for rel in a_files:
        try:
            if (b / rel).read_bytes() != (a / rel).read_bytes():
                return False
        except OSError:
            return False
    return True


def _ensure_symlink(link: Path, target: Path) -> None:
    """Make ``link`` a symlink to ``target`` unless it already is one.

    A real file/dir at ``link`` is replaced only when its content is
    identical to ``target``'s — i.e. a stale copy from a pre-P5a install.
    A *modified* real dir is a deliberate copy-on-write escape hatch
    (06-growth-design §2.3) and is left alone. SKILL.md is engine-owned:
    any real file there is a stale composed variant and is always replaced.
    """
    if link.is_symlink():
        if link.resolve() == target.resolve():
            return
        link.unlink()
    elif link.exists():
        if target.is_dir():
            if not _identical_dir(link, target):
                return  # copy-on-write — leave the real dir alone
            shutil.rmtree(link)
        else:
            if link.is_dir():
                shutil.rmtree(link)
            else:
                link.unlink()
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target, target_is_directory=target.is_dir())


def profile_home(hermes_home: Path, name: str) -> Path:
    """Where a profile's state lives.

    The `default` profile is the HERMES_HOME root itself; every named
    profile lives under ``profiles/<name>/``.
    """
    return hermes_home if name == "default" else hermes_home / "profiles" / name


#: Role → skill bundles (2026-08-05 skill split). The role owns which skills
#: a profile holds: a contributor gets the authoring skill, a manager gets the
#: management skill, a one-profile setup (combined) gets both. The maintained,
#: growing per-vault file is `<vault>-conventions.md`, created from the
#: template by the growth protocol into the contributor skill's conventions/
#: — never seeded here.
ROLE_SKILLS = {
    "contributor": ["obsidian-vault"],
    "manager": ["obsidian-vault-management"],
    "combined": ["obsidian-vault", "obsidian-vault-management"],
}
SKILL_BUNDLES = {
    "obsidian-vault": BUNDLED_SKILL,
    "obsidian-vault-management": MANAGER_SKILL,
}


def install_skills(profile_skills: Path, role: str) -> list[Path]:
    """Overlay the role's skill bundle(s) into a profile's skills area.

    A contributor gets `note-taking/obsidian-vault`, a manager gets
    `note-taking/obsidian-vault-management`, a one-profile setup gets both
    (2026-08-05 skill split). `SKILL.md`, `references/` and `templates/`
    become symlinks to each bundle — the immutable base, update-
    propagating, never rewritten. The contributor skill carries a real
    `conventions/` dir: the maintained per-vault file
    (`<vault>-conventions.md`) is created there by the growth protocol,
    never here.

    Role alignment is symmetric at the skill level: a skill the role no
    longer holds loses its bundle-derived surface (the symlinks). Real
    content — `conventions/` and copy-on-write customisations — is
    preserved (the survival guarantee).

    A profile that deliberately edited a reference or template (broke the
    symlink into a real dir, copy-on-write — 06-growth-design §2.3) is
    preserved; only content-identical stale copies from a pre-P5a install
    are replaced by symlinks. `SKILL.md` is engine-owned: any real file
    there is a stale composed variant and is always replaced.
    """
    if role not in ROLE_SKILLS:
        raise ValueError(f"unknown role: {role!r} (contributor|manager|combined)")
    wanted = ROLE_SKILLS[role]
    targets: list[Path] = []
    for name in wanted:
        bundle = SKILL_BUNDLES[name]
        target = profile_skills / "note-taking" / name
        target.mkdir(parents=True, exist_ok=True)
        _ensure_symlink(target / "SKILL.md", bundle / "SKILL.md")
        for sub in ("references", "templates"):
            _ensure_symlink(target / sub, bundle / sub)
        if name == "obsidian-vault":
            (target / "conventions").mkdir(exist_ok=True)
        targets.append(target)

    skills_root = profile_skills / "note-taking"
    if skills_root.is_dir():
        for existing in sorted(skills_root.glob("obsidian-vault*")):
            if existing.name in wanted:
                continue
            for sub in ("SKILL.md", "references", "templates"):
                link = existing / sub
                if link.is_symlink():
                    link.unlink()
    return targets


def ensure_soul_sections(soul_path: Path, role: str) -> bool:
    """Write/refresh the managed SOUL sections block for a profile's role.

    Role: contributor | manager | combined (one-profile setup). Returns
    True if the file changed. Idempotent: an anchored block is replaced in
    place; the pre-P5b single-paragraph directive is upgraded in place
    (removed and replaced by the block); otherwise the block is appended.
    """
    block = _soul_block(role)
    if not soul_path.exists():
        soul_path.parent.mkdir(parents=True, exist_ok=True)
        soul_path.write_text(block, encoding="utf-8")
        return True
    text = soul_path.read_text(encoding="utf-8")

    old_directive = (
        "## Vault operations\n"
        "For any task touching an Obsidian vault (reading/writing notes, "
        "search, graph, index, audit, scaffold), load the `obsidian-vault` "
        "skill first — it routes to the right tools and conventions."
    )

    if SOUL_ANCHOR in text:
        # Already managed — replace the anchored block in place.
        start = text.index(SOUL_ANCHOR)
        prefix = text[:start].rstrip()
        new_text = (prefix + "\n\n" + block) if prefix else block
    elif old_directive in text:
        # Pre-P5b single paragraph — replace it with the full block.
        start = text.index(old_directive)
        end = start + len(old_directive)
        prefix = text[:start].rstrip()
        suffix = text[end:].lstrip()
        new_text = "\n\n".join(part for part in (prefix, block, suffix) if part)
    else:
        new_text = text.rstrip() + "\n\n" + block

    if new_text == text:
        return False
    with soul_path.open("w", encoding="utf-8") as fh:
        fh.write(new_text)
    return True


# --- plugin enablement (per profile) --------------------------------------

def link_plugin(profile_plugins: Path) -> Path:
    """Symlink the plugin bundle into a profile's plugins dir (if absent).

    Plugin discovery scans only the profile's own home
    (``<home>/plugins``), so a named profile needs the plugin visible there.
    A symlink (not a copy) mirrors the skill pattern — plugin code is shared
    and immutable, unlike per-profile conventions.
    """
    profile_plugins.mkdir(parents=True, exist_ok=True)
    link = profile_plugins / "obsidian-vault"
    if not link.exists():
        link.symlink_to(PLUGIN_DIR, target_is_directory=True)
    return link


def ensure_profile_env(env_path: Path, vault_root: Path, agent: str) -> bool:
    """Write OBSIDIAN_VAULT_PATH + OBSIDIAN_VAULT_AGENT into a profile .env.

    Without these, a profile session would fall back to DEFAULT_AGENT and
    act as `default` (wrong grants). Returns True if anything changed.
    """
    def upsert(lines: list, key: str, value: str) -> None:
        prefix = f"{key}="
        for i, ln in enumerate(lines):
            if ln.startswith(prefix):
                lines[i] = f"{key}={value}"
                return
        lines.append(f"{key}={value}")

    if not env_path.exists():
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text("", encoding="utf-8")
    before = env_path.read_text(encoding="utf-8")
    lines = before.splitlines()
    upsert(lines, "OBSIDIAN_VAULT_PATH", str(vault_root))
    upsert(lines, "OBSIDIAN_VAULT_AGENT", agent)
    after = "\n".join(lines) + ("\n" if lines else "")
    if after != before:
        env_path.write_text(after, encoding="utf-8")
        return True
    return False


def seed_profile_config(hermes_home: Path, name: str) -> bool:
    """Seed a named profile's config.yaml from the system default profile.

    `hermes profile create` seeds a bare stub (model only, no memory and
    most other settings). New profiles should start from the default config
    as a working baseline; the user reviews model/memory/plugins per profile.

    Copy-if-missing: a target that already declares ``memory:`` is treated
    as customised and left untouched. The default config carries no identity
    keys (name/profile/alias), so a verbatim copy cannot mislabel the
    profile. Returns True if the config was written.
    """
    if name == "default":
        return False
    source = profile_home(hermes_home, "default") / "config.yaml"
    if not source.is_file():
        print(f"[setup] warning: no default config at {source}; "
              f"skipping seed for {name}")
        return False
    target = profile_home(hermes_home, name) / "config.yaml"
    if target.is_file() and "memory:" in target.read_text(encoding="utf-8"):
        return False  # already a full config (seeded or customised)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, target)
    print(f"[setup] config seeded for {name} (from default; review "
          f"model/memory/plugins)")
    return True


def enable_plugin_for_profile(hermes_home: Path, name: str, vault_root: Path) -> None:
    """Make the obsidian-vault plugin available and correctly scoped for a profile.

    Named profiles: symlink the bundle into the profile's plugins dir and
    enable it via the CLI (``hermes --profile <name> plugins enable``), which
    writes ``plugins.enabled`` into that profile's config.yaml. The `default`
    profile is the HERMES_HOME root: the bundle is linked into its root
    plugins dir (same symlink as named profiles — plugin discovery scans
    ``<home>/plugins``) and enabled via the bare ``hermes plugins enable``.
    A fresh user machine has NO obsidian entry at all: without the link the
    bare enable fails with "not installed or bundled" (the old code assumed
    the bundle already lived at the root — true only on a dev machine that
    symlinked it by hand; fixed 2026-08-04 by the fresh-machine E2E probe).
    Every profile gets OBSIDIAN_VAULT_PATH and OBSIDIAN_VAULT_AGENT in its
    .env. Enable failures are surfaced as warnings, not swallowed.
    """
    import subprocess
    prof_home = profile_home(hermes_home, name)
    if name != "default":
        link_plugin(prof_home / "plugins")
        cmd = ["hermes", "--profile", name, "plugins", "enable",
               "obsidian-vault", "--no-allow-tool-override"]
    else:
        link_plugin(hermes_home / "plugins")
        cmd = ["hermes", "plugins", "enable",
               "obsidian-vault", "--no-allow-tool-override"]
    res = subprocess.run(cmd, check=False, capture_output=True,
                         text=True, timeout=120)
    if res.returncode == 0:
        print(f"[setup] plugin enabled for profile: {name}")
    else:
        detail = (res.stderr or res.stdout).strip()
        print(f"[setup] WARNING: plugin enable failed for {name}: {detail}")
    if ensure_profile_env(prof_home / ".env", vault_root, name):
        print(f"[setup] profile env updated: {prof_home / '.env'}")


# --- vault scaffolding (pure) ---------------------------------------------

STARTER_TREE = [
    "system/handbook",
    "system/logs",
    "system/decisions",
    "work/creative/knowledge",
    "work/creative/projects",
    "work/coding/knowledge",
    "work/coding/projects",
]

#: Per-domain .vault configs (spec §3.3/§3.4/§3.6). Each domain declares its
#: own vocabulary additions; the KNOWLEDGE schema is identical everywhere and
#: is the §3.3 inheritance proving case. Copied only on first scaffold
#: (copy-if-missing) — they are policy, like the root configs.
DOMAIN_CONFIGS = [
    "system/.vault/config.yaml",
    "work/creative/.vault/config.yaml",
    "work/coding/.vault/config.yaml",
    "work/creative/knowledge/.vault/config.yaml",
    "work/coding/knowledge/.vault/config.yaml",
]


def _copy_if_missing(src: Path, dst: Path) -> None:
    """Copy a config file only when the target does not exist.

    The .vault configs are *policy* — they may have been customised after the
    first scaffold (e.g. activated contributor grants). Re-running the
    installer must never clobber them; the tree dirs are re-ensured instead.
    """
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)


def scaffold_vault(vault_root: Path, preset: str,
                   dry_run: bool = False) -> list[Path]:
    """Create the vault root: .vault/ config + roles, and the tree.

    preset="standard" → starter tree + per-domain configs (the standard
                       install: 5-role starter).
    preset="blank"    → bare root: neutral config + deny-by-default roles
                        (custom installation; no domains until the manager
                        adds them).
    Returns the created directories. Config files are written only on first
    scaffold — existing ones (customised policy) are preserved. dry_run
    prints the actions without touching the filesystem.
    """
    if preset not in ("standard", "blank"):
        raise ValueError(
            f"preset must be 'standard' or 'blank', got {preset!r}")
    source = STARTER if preset == "standard" else BLANK
    if dry_run:
        print(f"[dry-run] mkdir {vault_root} (preset: {preset})")
        print(f"[dry-run] .vault/config.yaml + roles.yaml from {source.name}")
        if preset == "standard":
            for rel in STARTER_TREE:
                print(f"[dry-run] mkdir {vault_root / rel}")
        return [vault_root]
    vault_root.mkdir(parents=True, exist_ok=True)
    created = [vault_root]

    vault_cfg = vault_root / ".vault"
    vault_cfg.mkdir(exist_ok=True)
    _copy_if_missing(source / ".vault" / "config.yaml", vault_cfg / "config.yaml")
    _copy_if_missing(source / ".vault" / "roles.yaml", vault_cfg / "roles.yaml")
    # Orientation doc — copy-if-missing so a customised README survives re-runs.
    _copy_if_missing(source / "README.md", vault_root / "README.md")

    if preset == "standard":
        for rel in STARTER_TREE:
            d = vault_root / rel
            d.mkdir(parents=True, exist_ok=True)
            created.append(d)
        # Per-domain + KNOWLEDGE configs — policy, copy-if-missing.
        for rel in DOMAIN_CONFIGS:
            src = STARTER / rel
            if src.is_file():
                _copy_if_missing(src, vault_root / rel)
    return created


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
                "prompt": "Where should the vault live? (absolute path)"}
    if stage == "name":
        return {"stage": stage, "kind": "text",
                "prompt": "Vault name (used for conventions files, e.g. "
                          "<name>-conventions.md)"}
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


def _role_skill(roles: set[str]) -> str:
    """Skill role for a profile: combined iff manager + any contributor."""
    if "manager" in roles and len(roles) > 1:
        return "combined"
    if "manager" in roles:
        return "manager"
    return "contributor"


def _role_grants(role: str) -> list[tuple[str, list[str]]]:
    """(kind, globs) lines a role's grant block must contain."""
    if role == "manager":
        return [("meta", ["**"]), ("config", ["**"]), ("read", ["**"])]
    if role == "creative":
        return [("write", ["work/creative/**"]),
                ("config", ["work/creative/**"]),
                ("read", ["work/creative/**", "work/*/knowledge/**"])]
    if role == "dev":
        return [("write", ["work/coding/**"]),
                ("config", ["work/coding/**"]),
                ("read", ["work/coding/**", "work/*/knowledge/**"])]
    if role == "researcher":
        return [("write", ["work/*/knowledge/**"]),
                ("config", ["work/*/knowledge/**"]),
                ("read", ["work/*/knowledge/**", "system/**"])]
    return []


def _ensure_agent_block(roles_path: Path, profile: str,
                        needed: list[tuple[str, list[str]]],
                        dry_run: bool = False, label: str = "") -> bool:
    """Extend-or-append a profile's grant block with (kind, globs) lines.

    THE grant mechanism — one implementation for every caller (setup role
    assignment, growth domain creation). Role accumulation (one-profile
    setups) means a profile may already hold grants: an existing block is
    extended by unioning the missing globs into each kind line, never
    refused. A profile with no block gets a full block appended. Comment-
    preserving text surgery (policy comments must survive); the result
    must re-parse as YAML. Idempotent: all globs already present → no
    change, False.
    """
    import re as _re
    import yaml

    if not needed:
        return False
    text = roles_path.read_text(encoding="utf-8")
    m = _re.search(rf"^  {_re.escape(profile)}:\s*$", text, _re.M)
    if m is None:
        # Fresh profile — append a full block at the end of agents:.
        lines = text.splitlines(keepends=True)
        agents_idx = next((i for i, ln in enumerate(lines)
                           if ln.startswith("agents:")), None)
        if agents_idx is None:
            raise ValueError(f"{roles_path}: no 'agents:' section")
        for ln in lines[agents_idx + 1:]:
            if ln.strip() and not ln[:1].isspace() and not ln.startswith("#"):
                raise ValueError(
                    f"{roles_path}: top-level key after 'agents:' — "
                    f"refusing blind append; add the grant by hand")
        block = f"  {profile}:\n" + "".join(
            f'    {kind}: {_fmt_globs(globs)}\n' for kind, globs in needed)
        if dry_run:
            print(f"[dry-run] roles.yaml + grant block for {profile}"
                  + (f" ({label})" if label else ""))
            return True
        if not text.endswith("\n"):
            text += "\n"
        text += block
        yaml.safe_load(text)
        roles_path.write_text(text, encoding="utf-8")
        return True

    # Existing block — union missing globs into each kind line. Work on
    # LINE indices: m.start() is a character offset, unusable for indexing
    # the splitlines() list (bug fixed 2026-08-05).
    lines = text.splitlines(keepends=True)
    start = next(i for i, ln in enumerate(lines)
                 if _re.match(rf"^  {_re.escape(profile)}:\s*$", ln))
    # A block is its header plus `    kind:` lines. The first non-blank
    # line that is not a kind line ends it — that includes a two-space
    # comment (the next block's docstring, e.g. the blank preset's
    # commented manager stub) and the next agent key.
    end = len(lines)
    for i in range(start + 1, len(lines)):
        ln = lines[i]
        if not ln.strip():
            continue
        if _re.match(r"^    [a-zA-Z0-9_-]+:", ln):
            continue
        end = i
        break
    changed = False
    inserts: list[tuple[int, str]] = []
    for kind, globs in needed:
        found = None
        for i in range(start, end):
            km = _re.match(rf"^    {_re.escape(kind)}:\s*\[(.*?)\]\s*$",
                           lines[i].strip("\n"))
            if km:
                found = i
                break
        if found is None:
            inserts.append((end, f"    {kind}: {_fmt_globs(globs)}\n"))
            end += 1
            changed = True
            continue
        raw = lines[found].strip()
        existing = _re.findall(r'"([^"]+)"', raw)
        merged = list(existing)
        for g in globs:
            if g not in merged:
                merged.append(g)
        if merged != existing:
            lines[found] = f"    {kind}: {_fmt_globs(merged)}\n"
            changed = True
    if not changed:
        return False
    if dry_run:
        print(f"[dry-run] roles.yaml + extend {profile}"
              + (f" ({label})" if label else ""))
        return True
    if inserts:
        for pos, line in inserts:
            lines.insert(pos, line)
    yaml.safe_load("".join(lines))
    roles_path.write_text("".join(lines), encoding="utf-8")
    return True


def _grant_role(roles_path: Path, profile: str, role: str,
                dry_run: bool = False) -> bool:
    """Ensure a profile's grant block covers a role (extend-or-append).

    Thin wrapper over :func:`_ensure_agent_block` with role-defined globs.
    Manager globs are unioned into an existing block like any other role
    (one-agent setups: default-as-manager needs meta/config at root); only
    when NO block exists do we delegate to _ensure_manager_grant, which
    knows how to activate the blank preset's COMMENTED stub.
    """
    import re as _re

    text = roles_path.read_text(encoding="utf-8")
    if role == "manager":
        if not _re.search(rf"^  {_re.escape(profile)}:\s*$", text, _re.M):
            return _ensure_manager_grant(roles_path, profile, dry_run=dry_run)
        needed = [("meta", ["**"]), ("config", ["**"]), ("read", ["**"])]
    else:
        needed = _role_grants(role)
    return _ensure_agent_block(roles_path, profile, needed,
                               dry_run=dry_run, label=role)


def _fmt_globs(globs: list[str]) -> str:
    """Render a grant globs list the way the starter writes it."""
    return "[" + ", ".join(f'"{g}"' for g in globs) + "]"


def _build_stage(stage: str, answer: str, state: dict,
                 hermes_home: Path, dry_run: bool) -> list[str]:
    """Build the aspect a stage answer finalises. Returns recap lines.

    The stage machine owns the sequence and every decision; this is the
    only place fs work happens. Location/name/profile answers only
    record (accumulation needs all answers); the preset answer scaffolds
    the tree; finalize creates profiles + skills + SOUL + grants + env.
    """
    if stage == "preset":
        vault_root = Path(state["answers"]["location"]).expanduser()
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
    vault_root = Path(state["answers"]["location"]).expanduser()
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
        if dry_run:
            out.append(f"[dry-run] profile {prof}: skill={skill_role} "
                       f"roles={sorted(roles)}")
        else:
            if not is_default and not profile_home(hermes_home, prof).is_dir():
                desc = "; ".join(ROLE_META[r]["desc"] for r in roles
                                 if r in ROLE_META) or "Vault profile"
                _create_profile(prof, desc)
            pskills = profile_home(hermes_home, prof) / "skills"
            install_skills(pskills, role=skill_role)
            soul = profile_home(hermes_home, prof) / "SOUL.md"
            ensure_soul_sections(soul, skill_role)
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

    if not dry_run:
        _save_setup_state(hermes_home, {"stage": 0, "answers": {}})
    out.append("Done. Restart Hermes to activate the new profiles.")
    return out


def _create_profile(name: str, description: str) -> None:
    """Delegate profile creation to the Hermes CLI (stable contract).

    The CLI is the single supported way to create a profile (it wires the
    alias, skill seeding, etc.). Failure is non-fatal for the vault — the
    skill still installs into the profile's skills dir — but it is surfaced
    as a warning (re-running the installer against existing profiles is a
    normal scenario; silent "success" would be a lie).
    """
    import subprocess
    print(f"[setup] create profile: hermes profile create {name}")
    try:
        res = subprocess.run(
            ["hermes", "profile", "create", name,
             "--description", description],
            check=False, capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            detail = (res.stderr or res.stdout).strip()
            print(f"[setup] WARNING: profile '{name}' not created: {detail}")
    except Exception as exc:  # pragma: no cover - environment dependent
        print(f"[setup] warning: profile creation failed: {exc}")


# --- growth protocol (P5c) ------------------------------------------------

def vault_conventions_name(vault_root: Path) -> str:
    """Name of the maintained conventions file: ``<vault>-conventions.md``.

    One per profile per vault (06-growth-design §2.1): the one file in the
    contributor skill's conventions/ that grows through interaction — never
    seeded, never touched by the installer. Subdomains share it unless their
    rulesets genuinely diverge — the split is a documented LLM step, not a
    mechanical branch.
    """
    return f"{vault_root.name}-conventions.md"


def ensure_conventions_file(profile_skills: Path, vault_root: Path,
                            dry_run: bool = False) -> Path:
    """Copy-if-missing the maintained conventions file into a profile.

    ``conventions/<vault>-conventions.md`` from ``templates/vault-conventions.md``,
    with the vault name substituted. Never overwrites an existing file (it
    grows through interaction — the installer's survival guarantee).
    """
    conv_dir = profile_skills / "note-taking" / "obsidian-vault" / "conventions"
    dst = conv_dir / vault_conventions_name(vault_root)
    if dst.exists():
        return dst
    if dry_run:
        print(f"[dry-run] create {dst} from template")
        return dst
    conv_dir.mkdir(parents=True, exist_ok=True)
    text = (BUNDLED_SKILL / "templates" / "vault-conventions.md"
            ).read_text(encoding="utf-8")
    text = text.replace("<Vault name>", vault_root.name)
    dst.write_text(text, encoding="utf-8")
    return dst


def append_manifest_entry(soul_path: Path, line: str,
                          dry_run: bool = False) -> bool:
    """Append one convention-manifest line to a SOUL's Convention manifest.

    Inserts the line immediately before the ``<!-- add:`` marker (the
    manifest's directed placeholder), so real entries accumulate above it.
    Idempotent: an exact line already present → no change, False. Refuses
    when the SOUL has no add-marker — that is a manager SOUL (conventions
    are contributor-maintained), so this is the right guard.
    """
    if not soul_path.is_file():
        raise FileNotFoundError(
            f"SOUL not found: {soul_path} — install the skill for that "
            f"profile first (--add-contributor / the installer)")
    text = soul_path.read_text(encoding="utf-8")
    if line in text:
        return False
    marker = "<!-- add:"
    idx = text.find(marker)
    if idx == -1:
        raise ValueError(
            f"{soul_path}: no convention-manifest add-marker — a manager "
            f"SOUL? Conventions are contributor-maintained.")
    if dry_run:
        print(f"[dry-run] manifest entry: {line}")
        return True
    soul_path.write_text(text[:idx] + line + "\n" + text[idx:],
                         encoding="utf-8")
    return True


def _append_agent_grant(roles_path: Path, owner: str, domain: str,
                        dry_run: bool = False) -> bool:
    """Ensure an owner's grant block covers ``work/<domain>/**``.

    Thin wrapper over :func:`_ensure_agent_block` (the one grant
    mechanism). Existing owners are EXTENDED, not refused — role
    accumulation is first-class since P6; the old "refuse existing
    owner" path is gone. Idempotent: owner + globs already present →
    False, no change.
    """
    if not roles_path.is_file():
        raise FileNotFoundError(f"roles.yaml not found: {roles_path}")
    needed = [
        ("write", [f"work/{domain}/**"]),
        ("config", [f"work/{domain}/**"]),
        ("read", [f"work/{domain}/**", "work/*/knowledge/**"]),
    ]
    return _ensure_agent_block(roles_path, owner, needed,
                               dry_run=dry_run, label=domain)


def _domain_config_stub(domain: str) -> str:
    """Minimal honest config for a new domain: extends the root schema with
    no vocabulary of its own. The manager/owner evolves fields afterwards
    via obsidian_edit_config / scaffold (mechanical, tool-mediated)."""
    return (
        f"# work/{domain} — domain config (growth protocol)\n"
        "# Extends the root schema via union. Declare what this domain adds\n"
        "# or changes; never re-declare root fields.\n"
        "# E.g.:\n"
        "#   fields:\n"
        "#     type:\n"
        "#       allowed: [<domain-specific>]\n"
    )


def _ensure_manager_grant(roles_path: Path, manager: str,
                          dry_run: bool = False) -> bool:
    """Activate the manager's grant block in roles.yaml (blank preset).

    The blank preset ships the manager block COMMENTED OUT (deny-by-default
    until a manager exists). When the installer creates/reuses a manager
    profile, that block must become active — otherwise the custom-install
    manager holds no grants at all and every maintenance operation fails.
    Idempotent: an active ``<manager>:`` block is left alone.
    """
    import re as _re
    import yaml

    if not roles_path.is_file():
        raise FileNotFoundError(f"roles.yaml not found: {roles_path}")
    text = roles_path.read_text(encoding="utf-8")

    if _re.search(rf"^  {_re.escape(manager)}:\s*$", text, _re.M):
        return False  # already an active grant block

    # The blank preset's commented stub — any manager name, commented lines.
    stub = _re.search(r"^  # [a-zA-Z0-9_-]+:\n(?:^  # .*\n?)*", text, _re.M)
    block = (
        f"  {manager}:\n"
        f'    meta:   ["**"]\n'
        f'    config: ["**"]\n'
        f'    read:   ["**"]\n'
    )
    if dry_run:
        print(f"[dry-run] roles.yaml + active manager block for {manager}")
        return True
    if stub:
        text = text[:stub.start()] + block + text[stub.end():]
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += block
    yaml.safe_load(text)  # never ship broken YAML
    roles_path.write_text(text, encoding="utf-8")
    return True


def add_contributor(hermes_home: Path, name: str, vault_root: Path,
                    dry_run: bool = False) -> None:
    """Growth (manager): create a contributor profile bound to the vault.

    Profile (if missing) + skill overlay + SOUL sections + config seed +
    plugin enable + env — the same per-contributor steps as the interactive
    install (extracted so the growth protocol and the installer share one
    code path, thin entry points).
    """
    if dry_run:
        if not profile_home(hermes_home, name).is_dir():
            print(f"[dry-run] hermes profile create {name}")
        print(f"[dry-run] install skill overlay + SOUL sections for {name}")
        print(f"[dry-run] seed config + enable plugin + env for {name}")
        return
    contrib_skills = profile_home(hermes_home, name) / "skills"
    if not profile_home(hermes_home, name).is_dir():
        _create_profile(name, "Vault contributor")
    install_skills(contrib_skills, role="contributor")
    soul = profile_home(hermes_home, name) / "SOUL.md"
    ensure_soul_sections(soul, "contributor")
    seed_profile_config(hermes_home, name)
    enable_plugin_for_profile(hermes_home, name, vault_root)


def add_domain(hermes_home: Path, vault_root: Path, domain: str,
               owner: str, config_file: str = "",
               dry_run: bool = False) -> None:
    """Growth (manager): a full new domain ``work/<domain>/``.

    Tree + .vault/config.yaml + roles.yaml grant for the owner + the
    owner's maintained conventions file + SOUL manifest entry (06-growth-
    design §4.2). The owner profile must already exist (--add-contributor).
    """
    import yaml

    root_cfg = vault_root / ".vault" / "config.yaml"
    if not root_cfg.is_file():
        raise FileNotFoundError(
            f"{root_cfg} missing — scaffold the vault first")
    owner_home = profile_home(hermes_home, owner)
    if not owner_home.is_dir():
        raise FileNotFoundError(
            f"profile '{owner}' does not exist — create it first "
            f"(--add-contributor {owner})")

    domain_dir = vault_root / "work" / domain
    if dry_run:
        print(f"[dry-run] mkdir {domain_dir} + .vault/config.yaml")
    else:
        (domain_dir / ".vault").mkdir(parents=True, exist_ok=True)
        if config_file:
            cfg = Path(config_file)
            if not cfg.is_file():
                raise FileNotFoundError(f"config file not found: {cfg}")
            raw = cfg.read_text(encoding="utf-8")
            yaml.safe_load(raw)  # refuse to ship broken YAML
            (domain_dir / ".vault" / "config.yaml").write_text(
                raw, encoding="utf-8")
        else:
            (domain_dir / ".vault" / "config.yaml").write_text(
                _domain_config_stub(domain), encoding="utf-8")

    roles = vault_root / ".vault" / "roles.yaml"
    _append_agent_grant(roles, owner, domain, dry_run=dry_run)

    owner_skills = owner_home / "skills"
    ensure_conventions_file(owner_skills, vault_root, dry_run=dry_run)
    line = (f"- `conventions/{vault_conventions_name(vault_root)}` — "
            f"{domain} domain conventions (work/{domain}/**)")
    append_manifest_entry(owner_home / "SOUL.md", line, dry_run=dry_run)


def add_subdomain(hermes_home: Path, vault_root: Path, rel_path: str,
                  owner: str, dry_run: bool = False) -> None:
    """Growth (owner): register a scaffolded subdomain in the SOUL manifest.

    Rides ``obsidian_scaffold`` — the tool (write-gated) creates the
    directory + config delta + INDEX; this subcommand only records the
    subdomain in the owner's Convention manifest. Verifies the directory
    exists and the owner holds write over it (roles.yaml) — the same grant
    the tool enforced, checked again mechanically.
    """
    from vault import grants

    target = vault_root / rel_path
    if not target.is_dir():
        raise FileNotFoundError(
            f"{rel_path} not under {vault_root} — run obsidian_scaffold "
            f"first (this subcommand rides it)")
    registry = grants.load_roles(vault_root)
    # The engine's operations, not grant kinds: scaffold creates, so the
    # owner needs the `create` operation (write grant) over the path.
    if not (registry.allows(owner, "create", rel_path)
            or registry.allows(owner, "edit", rel_path)):
        try:
            held = sorted(k for k in grants.GRANT_KINDS
                          if registry.any_grant(owner, rel_path))
        except grants.RolesError:
            held = []   # unknown agent — no grants at all
        raise PermissionError(
            f"{owner} holds no write over {rel_path!r} "
            f"(held: {held or 'none'})")

    owner_home = profile_home(hermes_home, owner)
    if not owner_home.is_dir():
        raise FileNotFoundError(f"profile '{owner}' does not exist")
    ensure_conventions_file(owner_home / "skills", vault_root,
                            dry_run=dry_run)
    line = (f"- `conventions/{vault_conventions_name(vault_root)}` — "
            f"{rel_path} conventions ({rel_path}/**)")
    append_manifest_entry(owner_home / "SOUL.md", line, dry_run=dry_run)


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

    # Growth protocol (P5c) — mutually exclusive modes.
    ap.add_argument("--vault", help="Vault root path (growth subcommands)")
    growth = ap.add_mutually_exclusive_group()
    growth.add_argument("--add-contributor", metavar="NAME",
                        help="(manager) create a contributor profile bound "
                             "to the vault: profile + overlay + SOUL + env")
    growth.add_argument("--add-domain", metavar="DOMAIN",
                        help="(manager) create work/<DOMAIN>/ + config + "
                             "roles.yaml grant + SOUL manifest entry")
    growth.add_argument("--add-subdomain", metavar="REL_PATH",
                        help="(owner) register a scaffolded subdomain in "
                             "the SOUL convention manifest")
    ap.add_argument("--owner", metavar="PROFILE",
                    help="Owner profile for --add-domain / --add-subdomain")
    ap.add_argument("--config", metavar="FILE",
                    help="Prepared .vault/config.yaml for --add-domain "
                         "(default: minimal stub)")
    args = ap.parse_args()

    hermes_home = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()

    if args.add_contributor or args.add_domain or args.add_subdomain:
        if not args.vault:
            ap.error("--vault is required with growth subcommands")
        vault_root = Path(args.vault).expanduser()
        if args.add_contributor:
            add_contributor(hermes_home, args.add_contributor, vault_root,
                            dry_run=args.dry_run)
        elif args.add_domain:
            if not args.owner:
                ap.error("--add-domain requires --owner PROFILE")
            add_domain(hermes_home, vault_root, args.add_domain,
                       args.owner, config_file=args.config or "",
                       dry_run=args.dry_run)
        else:
            if not args.owner:
                ap.error("--add-subdomain requires --owner PROFILE")
            add_subdomain(hermes_home, vault_root, args.add_subdomain,
                          args.owner, dry_run=args.dry_run)
        return 0

    if args.setup:
        return _run_setup(hermes_home, args.answer, args.reset,
                          args.dry_run)

    ap.print_help()
    return 1


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
