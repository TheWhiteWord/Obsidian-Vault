"""Obsidian-vault installer + growth protocol (P3.7 → P5c).

Overlays the bundled skill into profile skills areas (symlinked base +
real conventions/), writes the role-aware SOUL.md sections, scaffolds a
vault from the starter preset (or blank), and — via the growth
subcommands — adds contributors, domains, and subdomains to a live vault.

Pure functions are separated from the interactive questionnaire so the
installer is testable against a scratch HERMES_HOME.

Usage:
    python3 scripts/setup.py --vault /path/to/vault [--preset default|blank]
                             [--manager create|reuse] [--yes] [--dry-run]

    # Growth protocol (P5c) — manager:
    python3 scripts/setup.py --vault /path/to/vault \\
        --add-contributor NAME                  # profile + overlay + SOUL + env
    python3 scripts/setup.py --vault /path/to/vault \\
        --add-domain DOMAIN --owner PROFILE [--config FILE]
                                                # tree + config + grant + manifest
    # Growth protocol (P5c) — domain owner:
    python3 scripts/setup.py --vault /path/to/vault \\
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
import os
import shutil
import sys
from pathlib import Path

# --- paths ----------------------------------------------------------------

PLUGIN_DIR = Path(os.environ.get(
    "OBSIDIAN_VAULT_PLUGIN",
    str(Path(__file__).resolve().parents[1]),
))
BUNDLED_SKILL = PLUGIN_DIR / "skills" / "obsidian-vault"
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
    §3.1, corrected 2026-08-04): Vault operations, Issues, Convention
    maintenance, Convention manifest. Every bullet names a tool or a
    reference — never prose instruction. The manifest starts
    empty-but-directed; the growth protocol (P5c) appends entries.

    Conventions model (2026-08-04 correction): `contributor.md` and
    `manager.md` are immutable ROLE DIRECTIVES, not maintained files. The
    maintained, growing file is `conventions/<vault>-conventions.md`,
    created per vault/domain from `templates/vault-conventions.md` and
    registered in the manifest. The manager does NOT maintain conventions —
    it holds manager.md only (and is not a contributor; its grants
    meta/config/read need none of the authoring discipline).
    """
    if role == "manager":
        issues = (
            "### Issues\n"
            "- Raise / list / resolve ledger issues: `obsidian_issue`, "
            "`obsidian_issue_list`, `obsidian_issue_resolve`.\n"
            "- Run the maintenance sweep: `obsidian_maintain` "
            "(delta / maintain / optimize). See `references/maintenance.md`.\n"
        )
        conventions = (
            "### Convention maintenance\n"
            "- `conventions/manager.md` is an immutable role directive. "
            "Conventions are maintained by contributors, not the manager. "
            "No per-vault convention files here.\n"
        )
        manifest_extra = "- `conventions/manager.md` — role directive (immutable)\n"
        add_line = "<!-- conventions are contributor-maintained; none to add here -->\n"
    elif role == "combined":
        issues = (
            "### Issues\n"
            "- Raise / list / resolve ledger issues: `obsidian_issue`, "
            "`obsidian_issue_list`, `obsidian_issue_resolve`.\n"
            "- Run the maintenance sweep: `obsidian_maintain`. See "
            "`references/issues.md`, `references/maintenance.md`.\n"
        )
        conventions = (
            "### Convention maintenance\n"
            "- `conventions/contributor.md` and `conventions/manager.md` are "
            "immutable role directives. Maintained conventions live in "
            "`conventions/<vault>-conventions.md`, created per vault/domain "
            "from `templates/vault-conventions.md` and registered below.\n"
        )
        manifest_extra = (
            "- `conventions/contributor.md` — role directive (immutable)\n"
            "- `conventions/manager.md` — role directive (immutable)\n"
        )
        add_line = "<!-- add: - `conventions/<vault>-conventions.md` — description (domain) -->\n"
    else:  # contributor
        issues = (
            "### Issues\n"
            "- Raise and track ledger issues: `obsidian_issue`, "
            "`obsidian_issue_list`. You raise; resolution is grant-gated — "
            "the maintenance sweep is the manager's job. See "
            "`references/issues.md`.\n"
        )
        conventions = (
            "### Convention maintenance\n"
            "- `conventions/contributor.md` is an immutable role directive. "
            "Your maintained conventions live in "
            "`conventions/<vault>-conventions.md`, created per vault/domain "
            "from `templates/vault-conventions.md` and registered below. See "
            "`conventions/contributor.md` for the process.\n"
        )
        manifest_extra = "- `conventions/contributor.md` — role directive (immutable)\n"
        add_line = "<!-- add: - `conventions/<vault>-conventions.md` — description (domain) -->\n"

    return (
        f"{SOUL_ANCHOR}\n"
        "## Vault\n"
        "- Operating this vault — tools, conventions, issues, and "
        "maintenance. Each subsection points at what governs it.\n"
        "### Vault operations\n"
        "- For any task touching an Obsidian vault, load the `obsidian-vault` "
        "skill first — it routes to the right tools and conventions.\n"
        f"{issues}"
        f"{conventions}"
        "### Convention manifest\n"
        "<!-- maintained by the growth protocol; one line per convention file -->\n"
        f"{manifest_extra}"
        f"{add_line}"
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


#: Role → convention fragments. contributor.md and manager.md are immutable
#: role directives (06-growth-design §2.1, corrected 2026-08-04): a manager
#: is NOT a contributor — its grants (meta/config/read, no content write) and
#: duties need none of the authoring discipline — so a manager profile holds
#: manager.md ONLY. combined (one-profile setup) holds both. The maintained,
#: growing per-vault file is `<vault>-conventions.md`, created from the
#: template by the growth protocol — never seeded here.
ROLE_FRAGMENTS = {
    "contributor": ["contributor.md"],
    "manager": ["manager.md"],
    "combined": ["contributor.md", "manager.md"],
}


def install_skill(profile_skills: Path, role: str) -> Path:
    """Overlay the bundled skill into a profile's skills area (P5a).

    `SKILL.md`, `references/` and `templates/` become symlinks to the
    bundle — the immutable base, update-propagating, never rewritten.
    `conventions/` is a real per-profile dir holding the immutable role
    directives for `role` (contributor | manager | combined), seeded
    copy-if-missing. Stale directives from a former role are removed
    (role alignment). The maintained per-vault file
    `<vault>-conventions.md` is created by the growth protocol, never here.

    A profile that deliberately edited a reference or template (broke the
    symlink into a real dir, copy-on-write — 06-growth-design §2.3) is
    preserved; only content-identical stale copies from a pre-P5a install
    are replaced by symlinks. `SKILL.md` is engine-owned: any real file
    there is a stale composed variant and is always replaced.
    """
    if role not in ROLE_FRAGMENTS:
        raise ValueError(f"unknown role: {role!r} (contributor|manager|combined)")
    target = profile_skills / "obsidian-vault"
    target.mkdir(parents=True, exist_ok=True)

    _ensure_symlink(target / "SKILL.md", BUNDLED_SKILL / "SKILL.md")
    for sub in ("references", "templates"):
        _ensure_symlink(target / sub, BUNDLED_SKILL / sub)

    conv = target / "conventions"
    conv.mkdir(exist_ok=True)
    want = set(ROLE_FRAGMENTS[role])
    for frag in ("contributor.md", "manager.md"):
        dst = conv / frag
        src = BUNDLED_SKILL / "conventions" / frag
        if frag in want:
            # Role directives are IMMUTABLE (2026-08-04): refresh from the
            # bundle on every run. The maintained, growing file is
            # <vault>-conventions.md, created by the growth protocol from the
            # template — never touched here.
            if src.is_file():
                shutil.copy(src, dst)
        elif dst.exists():
            dst.unlink()  # role alignment — stale directive from a former role
    return target


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


def scaffold_vault(vault_root: Path, preset: str) -> list[Path]:
    """Create the vault root: .vault/ config + roles, and the tree.

    preset="default"  → starter tree + per-domain configs (standard install).
    preset="blank"    → bare root: neutral config + deny-by-default roles
                        (custom installation; no domains until the manager
                        adds them).
    Returns the created directories. Config files are written only on first
    scaffold — existing ones (customised policy) are preserved.
    """
    source = STARTER if preset == "default" else BLANK
    vault_root.mkdir(parents=True, exist_ok=True)
    created = [vault_root]

    vault_cfg = vault_root / ".vault"
    vault_cfg.mkdir(exist_ok=True)
    _copy_if_missing(source / ".vault" / "config.yaml", vault_cfg / "config.yaml")
    _copy_if_missing(source / ".vault" / "roles.yaml", vault_cfg / "roles.yaml")
    # Orientation doc — copy-if-missing so a customised README survives re-runs.
    _copy_if_missing(source / "README.md", vault_root / "README.md")

    if preset == "default":
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


# --- interactive flow ------------------------------------------------------

def _ask(prompt: str, default: str, yes: bool) -> str:
    if yes:
        return default
    try:
        return input(f"{prompt} [{default}]: ").strip() or default
    except EOFError:
        return default


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

    One per profile per vault (06-growth-design §2.1, 2026-08-04): the
    immutable role directives (contributor.md / manager.md) ship with the
    bundle; THIS file is the one that grows through interaction. Subdomains
    share it unless their rulesets genuinely diverge — the split is a
    documented LLM step, not a mechanical branch.
    """
    return f"{vault_root.name}-conventions.md"


def ensure_conventions_file(profile_skills: Path, vault_root: Path,
                            dry_run: bool = False) -> Path:
    """Copy-if-missing the maintained conventions file into a profile.

    ``conventions/<vault>-conventions.md`` from ``templates/vault-conventions.md``,
    with the vault name substituted. Never overwrites an existing file (it
    grows through interaction — the installer's survival guarantee).
    """
    conv_dir = profile_skills / "obsidian-vault" / "conventions"
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
    """Append an owner grant block over ``work/<domain>/**`` in roles.yaml.

    Text-level surgery on purpose: roles.yaml is POLICY with comments, so
    the block is appended at the end of the ``agents:`` section, never a
    yaml round-trip (comments would die). Refuses when:
      - ``agents:`` is not the last top-level key (ambiguous placement)
      - the owner already has grants (extend by hand — manager-only)
      - the appended block fails to parse as YAML
    Idempotent: owner + globs already present → False, no change.
    """
    import re as _re
    import yaml

    if not roles_path.is_file():
        raise FileNotFoundError(f"roles.yaml not found: {roles_path}")
    text = roles_path.read_text(encoding="utf-8")

    lines = text.splitlines(keepends=True)
    agents_idx = next((i for i, ln in enumerate(lines)
                       if ln.startswith("agents:")), None)
    if agents_idx is None:
        raise ValueError(f"{roles_path}: no 'agents:' section")

    # Any top-level key after agents: would make append placement ambiguous.
    for ln in lines[agents_idx + 1:]:
        if ln.strip() and not ln[:1].isspace() and not ln.startswith("#"):
            raise ValueError(
                f"{roles_path}: top-level key after 'agents:' — refusing "
                f"blind append; add the grant by hand")

    if _re.search(rf"^  {_re.escape(owner)}:\s*$", text, _re.M):
        if f'"work/{domain}/**"' in text:
            return False  # already granted
        raise ValueError(
            f"{owner} already has grants in roles.yaml; add the "
            f"work/{domain}/** globs by hand (manager-only policy edit)")

    block = (
        f"  {owner}:\n"
        f'    write:  ["work/{domain}/**"]\n'
        f'    config: ["work/{domain}/**"]\n'
        f'    read:   ["work/{domain}/**", "work/*/knowledge/**"]\n'
    )
    if dry_run:
        print(f"[dry-run] roles.yaml + grant block for {owner} "
              f"(work/{domain}/**)")
        return True
    if not text.endswith("\n"):
        text += "\n"
    text += block
    # Never ship broken YAML: the append must re-parse.
    yaml.safe_load(text)  # raises YAMLError on failure
    roles_path.write_text(text, encoding="utf-8")
    return True


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
    install_skill(contrib_skills, role="contributor")
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
    ap.add_argument("--vault", help="Vault root path (default: prompt)")
    ap.add_argument("--preset", choices=["default", "blank"], default="default")
    ap.add_argument("--manager", choices=["create", "reuse"], default="create")
    ap.add_argument("--yes", action="store_true",
                    help="Accept all defaults, non-interactive")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print actions without performing them")

    # Growth protocol (P5c) — mutually exclusive modes. Absent → the
    # interactive install flow below.
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

    vault_root = Path(args.vault or _ask("Vault location", "~/VAULT", args.yes)
                      ).expanduser()

    print(f"Plugin:  {PLUGIN_DIR}")
    print(f"Hermes:  {hermes_home}")
    print(f"Vault:   {vault_root}  (preset: {args.preset})")

    if args.dry_run:
        print("[dry-run] scaffold vault tree + .vault configs (root, domains, knowledge)")
        print("[dry-run] create/select manager profile, install skill")
        print("[dry-run] append SOUL.md directive to each target profile")
        print("[dry-run] seed profile configs from default (model/memory/plugins)")
        print("[dry-run] enable obsidian-vault plugin per profile + write profile .env")
        return 0

    # 1. Vault scaffold.
    created = scaffold_vault(vault_root, args.preset)
    print(f"Vault scaffolded: {len(created)} directories")

    # 2. Manager profile + skill install.
    manager_name = _ask("Manager profile name", "vault-manager", args.yes)
    touched: list[tuple[str, bool]] = []   # (profile, is_manager)
    if args.manager == "create":
        _create_profile(manager_name,
                        "Vault maintenance: meta/config/read, "
                        "no content ownership")
    touched.append((manager_name, True))

    # The manager must be GRANTED, not just created. The blank preset ships
    # its manager block commented out (deny-by-default until a manager
    # exists); a created/reused manager profile with no grants can't run a
    # single maintenance operation. The starter preset's block is already
    # active, so this is a no-op there (idempotent).
    if _ensure_manager_grant(vault_root / ".vault" / "roles.yaml",
                             manager_name, dry_run=args.dry_run):
        print(f"Manager grants active in roles.yaml: {manager_name}")

    profile_skills = profile_home(hermes_home, manager_name) / "skills"
    if args.manager == "reuse" and not profile_skills.exists():
        print(f"[setup] note: {profile_skills} does not exist; creating it")

    installed = install_skill(profile_skills, role="manager")
    print(f"Manager skill:  {installed}")

    # Default profile — the system owner (D8). A contributor in vault terms:
    # contributor role directives, never the manager section. The default
    # profile already exists (it is where the plugin lives), so no creation.
    default_skills = profile_home(hermes_home, "default") / "skills"
    install_skill(default_skills, role="contributor")
    touched.append(("default", False))
    print(f"Default skill:  {default_skills / 'obsidian-vault'}")

    # 3. Contributor profiles — for each domain the user names.
    print("[setup] contributors: one profile per work/<domain> (e.g. "
          "creative → profile 'creative', coding → 'dev').")
    while True:
        domain = _ask("Domain (empty to finish)", "", args.yes)
        if not domain:
            break
        prof = _ask(f"Profile for {domain}", domain, args.yes)
        contrib_skills = profile_home(hermes_home, prof) / "skills"
        if not profile_home(hermes_home, prof).is_dir():
            _create_profile(prof, f"Vault contributor for {domain}")
        install_skill(contrib_skills, role="contributor")
        touched.append((prof, False))
        print(f"Contributor skill: {contrib_skills / 'obsidian-vault'}")

    # 4. SOUL.md sections on every touched profile (role-aware, P5b).
    for prof, is_mgr in touched:
        soul = profile_home(hermes_home, prof) / "SOUL.md"
        role = "manager" if is_mgr else "contributor"
        if ensure_soul_sections(soul, role):
            print(f"SOUL.md sections written ({role}): {soul}")

    # 5. Per-profile config seed + plugin enablement + env (issue #1: a
    # profile session needs the obsidian_* tools and the right agent
    # identity; new profiles start from default's config as a baseline).
    for prof, _is_mgr in touched:
        seed_profile_config(hermes_home, prof)
        enable_plugin_for_profile(hermes_home, prof, vault_root)

    print("\nDone. Restart Hermes to activate the new profiles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
