"""
Vault operations library: installer machinery + role mutation (P6).

The mechanical core shared by the setup questionnaire (scripts/setup.py)
and the daily role verb family (scripts/roles.py). Everything here is a
pure function of (hermes_home, vault_root) state — no CLI, no interactive
protocol. Grants are the truth: a profile's role/surface derive from its
live roles.yaml block; the SOUL `## Vault` block is the bind marker.

    from vault_ops import role_bind, role_unbind, role_transfer, role_list
Environment:
    HERMES_HOME   override the Hermes home (default: ~/.hermes).
    OBSIDIAN_VAULT_PLUGIN   override the plugin dir (default: repo root).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import TypedDict

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

#: Engine-synced copy of the Hermes default SOUL seed
#: (hermes_cli/default_soul.py ``DEFAULT_SOUL_MD``). A profile SOUL whose
#: content equals this — or one of the legacy comment scaffolds below —
#: carries zero user intent, provably safe to replace with a full role
#: SOUL (P8.1). The plugin cannot import ``hermes_cli``; keep this text
#: in sync with the engine.
DEFAULT_SOUL_MD = (
    "You are Hermes Agent, an intelligent AI assistant created by Nous "
    "Research. You are helpful, knowledgeable, and direct. You assist users "
    "with a wide range of tasks including answering questions, writing and "
    "editing code, analyzing information, creative work, and executing "
    "actions via your tools. You communicate clearly, admit uncertainty "
    "when appropriate, and prioritize being genuinely useful over being "
    "verbose unless otherwise directed below. Be targeted and efficient in "
    "your exploration and investigations."
)

#: Engine-synced legacy comment-only scaffolds (hermes_cli/default_soul.py
#: ``_LEGACY_TEMPLATE_SOULS``) seeded by old installers; also zero user
#: intent. Comparison is normalized, exactly like Hermes.
_LEGACY_TEMPLATE_SOULS = (
    (
        "# Hermes Agent Persona\n"
        "\n"
        "<!--\n"
        "This file defines the agent's personality and tone.\n"
        "The agent will embody whatever you write here.\n"
        "Edit this to customize how Hermes communicates with you.\n"
        "\n"
        "Examples:\n"
        '  - "You are a warm, playful assistant who uses kaomoji occasionally."\n'
        '  - "You are a concise technical expert. No fluff, just facts."\n'
        '  - "You speak like a friendly coworker who happens to know everything."\n'
        "\n"
        "This file is loaded fresh each message -- no restart needed.\n"
        "Delete the contents (or this file) to use the default personality.\n"
        "-->"
    ),
    (
        "# Hermes Agent Persona\n"
        "\n"
        "<!--\n"
        "This file defines the agent's personality and tone.\n"
        "The agent will embody whatever you write here.\n"
        "Edit this to customize how Hermes communicates with you.\n"
        "\n"
        "This file is loaded fresh each message -- no restart needed.\n"
        "Delete the contents (or this file) to use the default personality.\n"
        "-->"
    ),
)


def _normalize_soul(text: str) -> str:
    """Normalize SOUL content for template comparison (mirrors Hermes)."""
    return text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff").strip()


def _is_pristine_soul(text: str) -> bool:
    """True when SOUL content matches a known Hermes-shipped template.

    The same guarantee ``is_legacy_template_soul`` relies on: a file
    matching a shipped template carries zero user intent, so replacing it
    wholesale cannot destroy user work.
    """
    normalized = _normalize_soul(text)
    return normalized == _normalize_soul(DEFAULT_SOUL_MD) or any(
        normalized == _normalize_soul(t) for t in _LEGACY_TEMPLATE_SOULS)


#: Identity template keys (P8.1) — file names under ``souls/``. ``manager``
#: is the one identity directly connected to the vault (its role IS the
#: vault's health); the contributor identities are decoupled personas
#: (2026-08-06 review). Lives at repo root, NOT under a preset: the
#: manager template is used by BOTH presets, and these are profile
#: templates, not vault content (examples/ = vault presets only).
SOUL_IDENTITIES = ("manager", "system-owner", "creative", "researcher", "dev")
#: Contributor identities — valid for a ``contributor``-role full soul.
#: ``manager`` is its own role and its own identity.
SOUL_CONTRIBUTOR_IDENTITIES = ("system-owner", "creative", "researcher", "dev")
SOULS_DIR = PLUGIN_DIR / "souls"


def _soul_template(identity: str) -> str:
    """The identity prose for a template key (empty when unknown/missing).

    Templates hold prose only — `# Identity` + `# Style` — never the
    vault block; the engine composes prose + block so the block cannot
    drift from ``_soul_block``.
    """
    template = SOULS_DIR / f"{identity}.md"
    if not template.is_file():
        return ""
    return template.read_text(encoding="utf-8").rstrip()


def _full_soul(identity: str, block: str) -> str | None:
    """Composed full role SOUL: template prose + the managed block.

    None when the identity has no shipped template (caller falls back to
    block-only).
    """
    prose = _soul_template(identity)
    if not prose:
        return None
    return prose + "\n\n" + block


def _soul_identity(roles: set[str]) -> str:
    """Identity template key for a vault-role set (setup path).

    A single role with a shipped identity template → its key; everything
    else (combined, system-only, blank contributor, multi-role) → ""
    (block-only). ``system`` is never mapped here: the standard preset's
    system owner is ``default`` (S-3 carve-out) and a dedicated
    ``--system`` bind passes its identity explicitly in ``role_bind``.
    The manager maps to ``manager`` (P8.1 review: the manager has a full
    soul too, applied only when a NEW profile is created for the role).
    """
    if roles == {"manager"}:
        return "manager"
    if roles == {"creative"}:
        return "creative"
    if roles == {"dev"}:
        return "dev"
    if roles == {"researcher"}:
        return "researcher"
    return ""


def _soul_block(role: str) -> str:
    """The SOUL sections for a role: contributor | manager | combined.

    Two top-level managed sections under one anchor (2026-08-07):
    `## Inter-agent awareness` first — the universal peer/role awareness
    every profile carries (discovery, the memory contract, transport),
    with role-aware depth for the handoff registry — then the `## Vault`
    umbrella with lean `###` subsections. Every
    bullet names a tool or a reference — never prose instruction.
    Contributor and combined carry the convention sections and the
    manifest; the manifest starts empty-but-directed and the growth
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
            "- Session start: run `obsidian_issue_list assigned_to=me`, "
            "surface your assigned issues, and propose whether to handle "
            "each now or later (ask the user when present).\n"
            "- File issues as you find them — as a reminder to yourself "
            "when fixing would derail the current task, or assigned to "
            "the owning agent (`assignee`: write/meta over the target; "
            "else unassigned for triage).\n"
        ),
        "manager": (
            "### Issues\n"
            "- Triage the ledger and run the sweep: "
            "`obsidian_issue_list`, `obsidian_issue_resolve`, "
            "`obsidian_maintain`. See `references/issues.md`, "
            "`references/maintenance.md`.\n"
            "- Session start: run `obsidian_issue_list assigned_to=me` "
            "and scan the unassigned backlog; route what you can, claim "
            "what you handle (`in_progress`).\n"
            "- File issues as you find them — content problems to the "
            "owning agent; structural/meta problems you may resolve "
            "yourself (your `meta` covers every target).\n"
        ),
        "combined": (
            "### Issues\n"
            "- Raise like a contributor, triage like the manager: "
            "`obsidian_issue`, `obsidian_issue_list`, "
            "`obsidian_issue_resolve`, `obsidian_maintain`. See "
            "`references/issues.md`, `references/maintenance.md`.\n"
            "- Session start: run `obsidian_issue_list assigned_to=me` "
            "and scan the unassigned backlog; surface what's yours and "
            "propose now-or-later (ask the user when present); route "
            "what you can, claim what you handle (`in_progress`).\n"
            "- File issues as you find them — reminders to yourself when "
            "fixing would derail the current task, content problems to "
            "the owning agent, structural/meta problems you may resolve "
            "yourself (your `meta` covers every target).\n"
            "- Dual role: sweep findings about your own domains are "
            "yours to fix; about other domains, raise them.\n"
        ),
    }
    conventions = (
        "### Convention maintenance\n"
        "- Vault conventions live in-tree as `.vault/conventions.md` — one "
        "at the root (vault-wide rules), optionally per scope (the owning "
        "agent's); the file nearest a folder governs it. Edit the governing "
        "file when a user preference about writing rules lands (read via "
        "`obsidian_conventions`; writes are grant-gated).\n"
    )
    # Inter-agent awareness — universal, role-aware depth. Communication is
    # a Hermes capability (`hermes -p X -z` via the terminal tool), not a
    # vault one; the SOUL is the carrier every profile sees regardless of
    # skill loading. Discovery covers EVERY profile (`hermes profile list`,
    # vault-bound or not) plus domains for those that own one (`--role
    # list` / roles.yaml) — no profile name is ever hardcoded in shipped
    # files. The memory contract (verify at session start, keep current,
    # never erase) pairs with the installer's universal memory seed
    # (`ensure_peer_memory`). Contributors/combined hold the full protocol
    # reference; the manager carries the essentials inline (no contributor
    # file in the manager skill — no dangling pointer) (2026-08-07).
    awareness = {
        "contributor": (
            "## Inter-agent awareness\n"
            "- Peer discovery: `hermes profile list` (every profile — "
            "vault-bound or not), `--role list` (roles.yaml) — domain + "
            "grants for those that own one.\n"
            "- Memory: keep the peer/role list current — verify at session "
            "start with the discovery calls; the note is essential, never "
            "erase it.\n"
            "- Peer requests: `hermes -p <profile> -z \"<request>\"` through "
            "the terminal tool — one at a time, blocks until the peer's "
            "final message returns.\n"
            "- Handoff registry: `obsidian_protocol_list`, "
            "`obsidian_protocol` — see `references/inter-agent-protocol.md`.\n"
        ),
        "manager": (
            "## Inter-agent awareness\n"
            "- Peer discovery: `hermes profile list` (every profile — "
            "vault-bound or not), `--role list` (roles.yaml) — domain + "
            "grants for those that own one.\n"
            "- Memory: keep the peer/role list current — verify at session "
            "start with the discovery calls; the note is essential, never "
            "erase it.\n"
            "- Peer requests: `hermes -p <profile> -z \"<request>\"` through "
            "the terminal tool — task + intent + expected response form; "
            "one at a time, blocks until the peer's final message returns.\n"
            "- Handoff registry (read grant-free): `obsidian_protocol_list` "
            "— parties update their own handoffs (growth-protocol.md).\n"
        ),
        "combined": (
            "## Inter-agent awareness\n"
            "- Peer discovery: `hermes profile list` (every profile — "
            "vault-bound or not), `--role list` (roles.yaml) — domain + "
            "grants for those that own one.\n"
            "- Memory: keep the peer/role list current — verify at session "
            "start with the discovery calls; the note is essential, never "
            "erase it.\n"
            "- Peer requests: `hermes -p <profile> -z \"<request>\"` through "
            "the terminal tool — one at a time, blocks until the peer's "
            "final message returns.\n"
            "- Handoff registry: `obsidian_protocol_list`, "
            "`obsidian_protocol` — see `references/inter-agent-protocol.md`.\n"
        ),
    }

    if role == "manager":
        return (
            f"{SOUL_ANCHOR}\n"
            f"{awareness[role]}"
            "## Vault\n"
            "- Operating this vault — tools, issues, and maintenance. "
            "Each subsection points at what governs it.\n"
            "### Vault operations\n"
            f"{ops[role]}"
            f"{issues[role]}"
        )
    return (
        f"{SOUL_ANCHOR}\n"
        f"{awareness[role]}"
        "## Vault\n"
        "- Operating this vault — tools, conventions, issues, and "
        "maintenance. Each subsection points at what governs it.\n"
        "### Vault operations\n"
        f"{ops[role]}"
        f"{issues[role]}"
        f"{conventions}"
    )

def _apply_soul_prose(soul_path: Path, prose_file: str, role: str) -> bool:
    """Replace a profile SOUL's identity prose with the given file's
    content (manager-drafted, user-confirmed — S-7/note c), preserving
    the managed vault block and anything after it.

    The file holds the full identity prose (`# Identity` + `# Style`),
    same shape as the shipped templates. When the SOUL has an anchored
    block, everything before the anchor is replaced; when it is missing
    or pristine (fresh bind), the prose is written ahead of the block.
    Refuses on a customized, unmanaged SOUL (no anchor, non-pristine) —
    never claims an identity the installer did not create.
    """
    prose = Path(prose_file).read_text(encoding="utf-8").rstrip()
    if not prose:
        raise ValueError(f"soul file empty: {prose_file}")
    if not soul_path.is_file():
        soul_path.parent.mkdir(parents=True, exist_ok=True)
        soul_path.write_text(prose + "\n\n" + _soul_block(role), encoding="utf-8")
        return True
    text = soul_path.read_text(encoding="utf-8")
    idx = text.find(SOUL_ANCHOR)
    if idx == -1:
        if _is_pristine_soul(text) or not text.strip():
            soul_path.write_text(prose + "\n\n" + _soul_block(role),
                                 encoding="utf-8")
            return True
        raise ValueError(
            f"{soul_path} has no managed vault block and is customized — "
            f"refusing to claim its identity (bind without --soul first)")
    head = text[:idx].rstrip()
    tail = text[idx:]
    new_text = prose + "\n\n" + tail
    if new_text == text:
        return False
    soul_path.write_text(new_text, encoding="utf-8")
    return True


def _soul_has_identity(soul_path: Path) -> bool:
    """True when a profile SOUL carries identity prose ahead of the anchor
    (a full role soul or a user-customised identity — anything beyond the
    pristine Hermes seed).

    Deliberately format-agnostic (2026-08-06 review): it checks content,
    not a specific heading — a user who re-formats their identity prose
    (renames `# Identity`, restructures headings) must not break the
    check. A block-only SOUL (pristine seed + managed block) is False.
    """
    if not soul_path.is_file():
        return False
    text = soul_path.read_text(encoding="utf-8")
    idx = text.find(SOUL_ANCHOR)
    if idx == -1:
        return False
    prefix = text[:idx].strip()
    if not prefix:
        return False
    return not _is_pristine_soul(prefix)


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
    and is left alone. SKILL.md is engine-owned:
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
#: management skill, a one-profile setup (combined) gets both. Conventions
#: moved in-tree (P7): the vault's conventions live at `.vault/conventions.md`
#: (`ensure_root_conventions`) — the skill surface carries no conventions dir.
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
    Role alignment is symmetric at the skill level: a skill the role no
    longer holds loses its bundle-derived surface (the symlinks). Real
    content — copy-on-write customisations — is preserved (the survival
    guarantee).

    A profile that deliberately edited a reference or template (broke the
    symlink into a real dir, copy-on-write) is
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


def ensure_soul_sections(soul_path: Path, role: str, *,
                         profile_name: str = "", identity: str = "") -> bool:
    """Write/refresh the managed SOUL sections for a profile's role.

    Role: contributor | manager | combined (one-profile setup). Returns
    True if the file changed. Idempotent: an anchored block is replaced in
    place; the pre-P5b single-paragraph directive is upgraded in place
    (removed and replaced by the block); otherwise the block is appended.

    Full-SOUL path (P8.1): when ``identity`` names a shipped template and
    the profile is a non-default contributor — or the manager role with
    the ``manager`` identity (2026-08-06 review) — a pristine SOUL.md
    (missing, exactly ``DEFAULT_SOUL_MD``, or a legacy template) is
    replaced wholesale with the template prose + the managed block. A
    ``default`` profile (S-3) or a role without an identity template
    (combined, bare contributor — S-4) always takes the block-only path.
    User content is never touched: an anchored block in a customized SOUL
    is replaced in place, the rest preserved.
    """
    block = _soul_block(role)
    full = None
    if identity and profile_name != "default":
        if role == "contributor" and identity in SOUL_CONTRIBUTOR_IDENTITIES:
            full = _full_soul(identity, block)
        elif role == "manager" and identity == "manager":
            full = _full_soul(identity, block)
    if not soul_path.exists():
        soul_path.parent.mkdir(parents=True, exist_ok=True)
        soul_path.write_text(full or block, encoding="utf-8")
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
        if full and (not prefix or _is_pristine_soul(prefix)):
            # Prefix is empty (the file is entirely our block —
            # engine-written on a missing soul) or a pristine Hermes
            # seed: upgrade to the full role SOUL.
            new_text = full
        else:
            new_text = (prefix + "\n\n" + block) if prefix else block
    elif old_directive in text:
        # Pre-P5b single paragraph — replace it with the full block.
        start = text.index(old_directive)
        end = start + len(old_directive)
        prefix = text[:start].rstrip()
        suffix = text[end:].lstrip()
        new_text = "\n\n".join(part for part in (prefix, block, suffix) if part)
    elif full and _is_pristine_soul(text):
        # Fresh Hermes seed / legacy template → full role SOUL replaces
        # it wholesale (zero user intent, provably safe).
        new_text = full
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


#: The universal peer/role memory seed (2026-08-07). True in EVERY setup:
#: a one-agent system has no peers (the statement holds), a multi-agent
#: system converges at first session when the agent runs the discovery
#: calls. Never names a profile — names are user-customizable at install
#: (`existing:NAME`) and domains grow post-install, so a pre-populated
#: list would be wrong or stale. The SOUL's `## Inter-agent awareness`
#: block carries the instruction (verify at session start, keep current,
#: never erase); this note is the fact that converges.
PEER_MEMORY_SEED = (
    "Peers and roles: none available yet — discover with `hermes profile "
    "list` / `--role list` (roles.yaml) at session start; keep this note "
    "current (essential, never erase)."
)


def ensure_peer_memory(hermes_home: Path, name: str) -> bool:
    """Seed a profile's peer/role memory note (copy-if-missing).

    Writes ``PEER_MEMORY_SEED`` into ``<profile>/memories/MEMORY.md`` on
    first install only. Copy-if-missing like `seed_profile_config`: an
    existing note is the agent's maintained fact — never clobber it.
    Returns True if the note was written.
    """
    mem_file = profile_home(hermes_home, name) / "memories" / "MEMORY.md"
    if mem_file.is_file():
        return False
    mem_file.parent.mkdir(parents=True, exist_ok=True)
    mem_file.write_text(PEER_MEMORY_SEED + "\n", encoding="utf-8")
    return True


def detect_soul_role(soul_text: str) -> str | None:
    """The role a profile's SOUL managed block encodes (refresh path).

    Reads the role back from the live block — the durable record after
    setup (the questionnaire state is wiped at finalize). Markers are
    the role-keyed ops bullets from `_soul_block`: combined states the
    dual role once, manager names the management skill, contributor
    names the writing skill. None when the block is unrecognized
    (pre-P5b directive or an unknown future version) — refresh must not
    guess.
    """
    if "Dual role" in soul_text:
        return "combined"
    if "sweep, triage, and growth flows" in soul_text:
        return "manager"
    if "writing loop and the conventions" in soul_text:
        return "contributor"
    return None


def _env_value(env_path: Path, key: str) -> str | None:
    """Value of KEY in a .env file (None when missing)."""
    if not env_path.is_file():
        return None
    prefix = f"{key}="
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def refresh_profiles(hermes_home: Path, dry_run: bool = False) -> list[str]:
    """Re-apply the installer's per-profile state to a live install.

    After `hermes plugins update` brings new code, the per-profile
    COPIES the installer wrote once can go stale: SOUL managed blocks
    (new sections land here), the peer/role memory seed, skill overlays,
    config seeds, plugin enablement, manager cron. This re-runs the same
    idempotent ensures setup's finalize runs, for every vault-bound
    profile discovered from the live install — no questionnaire, no
    profile creation, no grant changes (roles.yaml is vault policy, not
    installer state).

    Vault-bound = the profile's .env declares OBSIDIAN_VAULT_PATH, or
    its SOUL.md carries the anchor. Role is read back from the live
    block via `detect_soul_role` (the setup state file is wiped at
    finalize, so the block is the durable record). User identity prose
    is preserved: the block-only path (identity="") never rewrites
    prose. Returns recap lines.
    """
    out: list[str] = []
    homes = [("default", hermes_home)]
    prof_dir = hermes_home / "profiles"
    if prof_dir.is_dir():
        homes += sorted((p.name, p) for p in prof_dir.iterdir() if p.is_dir())

    for name, home in homes:
        soul = home / "SOUL.md"
        env = home / ".env"
        vault_path = _env_value(env, "OBSIDIAN_VAULT_PATH")
        bound = vault_path is not None
        text = ""
        if soul.is_file():
            text = soul.read_text(encoding="utf-8")
            if SOUL_ANCHOR in text:
                bound = True
        if not bound:
            continue
        role = detect_soul_role(text)
        if role is None:
            out.append(f"refresh {name}: SKIPPED (unrecognized SOUL "
                       "block — run setup to re-bind)")
            continue
        if dry_run:
            out.append(f"[dry-run] refresh {name}: role={role}")
            continue
        install_skills(home / "skills", role=role)
        ensure_soul_sections(soul, role, profile_name=name, identity="")
        ensure_peer_memory(hermes_home, name)
        seed_profile_config(hermes_home, name)
        if vault_path is None:
            out.append(f"refresh {name}: WARNING no OBSIDIAN_VAULT_PATH "
                       "in .env — plugin enable skipped")
        else:
            enable_plugin_for_profile(hermes_home, name, Path(vault_path))
        if role in ("manager", "combined"):
            # Sync (not just create): a plugin update may have changed a
            # job's schedule/prompt/skills in CRON_JOBS, and the live job
            # keyed by the same name must be brought back in line.
            out.extend(sync_cron_jobs(name))
            # P-429: the manager/combined profile runs the maintenance cron
            # jobs; disable MoA so each turn is one sequential LLM call
            # (parallel fanout would stack across co-firing jobs → HTTP 429).
            out.extend(disable_profile_moa(name))
        out.append(f"refresh {name}: role={role}")

    return out


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


# --- scheduled maintenance cron (2026-08-06) ------------------------------

#: The standard maintenance jobs, installed at setup on the profile the
#: manager role is bound to — role-dependent, never a hardcoded name
#: (one-agent installs land on `default`; `existing:NAME` lands on NAME).
#: Job NAME is the idempotency key: an existing job with the same name is
#: left untouched, never clobbered. The hermes CLI is the interface (it owns
#: the jobs.json store format; stores are per-profile by design). Jobs fire
#: only while the gateway runs.
class CronJobSpec(TypedDict):
    name: str
    schedule: str
    skills: list[str]
    prompt: str


CRON_JOBS: list[CronJobSpec] = [
    {
        "name": "vault-maintain-daily",
        "schedule": "0 5 * * *",
        "skills": ["obsidian-vault-management"],
        "prompt": (
            "Run the vault management loop from the loaded "
            "obsidian-vault-management skill (context, verify, triage, act), "
            "with these specifics:\n"
            "- Sweep: obsidian_maintain mode=maintain, distribute=true "
            "(full correctness census).\n"
            "- Verify also covers the README Tree drift check and the "
            "grant-anchor check; raise [maintenance] issues as the skill "
            "directs.\n"
            "- Route the unassigned backlog: for each open [maintenance] "
            "issue with no assignee, find the profile whose write/meta "
            "grant covers its target (roles.yaml / peer memory) and set it "
            "via obsidian_issue_resolve assignee=<profile>; leave unclear "
            "or multi-owner ones for explicit triage.\n"
            "- Act within your remit only; escalate content judgments as "
            "ledger issues.\n"
            "Report in 3-5 lines: findings per check, issues "
            "created/skipped/resolved/declined/assigned, anything needing "
            "a human. If the sweep reports zero findings, say so in one line."
        ),
    },
    {
        "name": "vault-optimize-weekly",
        "schedule": "0 6 * * 1",
        "skills": ["obsidian-vault-management"],
        "prompt": (
            "Run the vault management loop from the loaded "
            "obsidian-vault-management skill (context, verify, triage, act), "
            "with these specifics:\n"
            "- Sweep: obsidian_maintain mode=optimize, distribute=true "
            "(correctness census PLUS quality suggestions: duplicates, "
            "missed connections, tag normalisation, thin notes).\n"
            "- Verify also covers the README Tree drift check and the "
            "grant-anchor check; raise [maintenance] issues as the skill "
            "directs.\n"
            "- Route the unassigned backlog: for each open [maintenance] "
            "issue with no assignee, find the profile whose write/meta "
            "grant covers its target (roles.yaml / peer memory) and set it "
            "via obsidian_issue_resolve assignee=<profile>; leave unclear "
            "or multi-owner ones for explicit triage.\n"
            "- Suggestions are never auto-applied: route them to the "
            "owning agent as ledger issues.\n"
            "Report in 3-5 lines: findings, suggestions, issues "
            "created/skipped/resolved/declined/assigned; flag anything "
            "needing a human decision."
        ),
    },
]


def _cron_cmd(profile: str, *args: str) -> list[str]:
    """The hermes CLI invocation scoped to a profile.

    `default` is the HERMES_HOME root — the bare command (mirrors
    enable_plugin_for_profile); named profiles get --profile.
    """
    if profile == "default":
        return ["hermes", *args]
    return ["hermes", "--profile", profile, *args]


def _cron_job_exists(profile: str, name: str) -> bool:
    """Whether a job with this name already exists on the profile.

    Reads `hermes cron list` output (the CLI owns the store format). A
    failed list is treated as "unknown" — the caller fails safe (skips
    creation rather than risking a duplicate).
    """
    import re
    import subprocess

    try:
        res = subprocess.run(_cron_cmd(profile, "cron", "list"),
                             check=False, capture_output=True, text=True,
                             timeout=120)
    except FileNotFoundError:
        return False
    if res.returncode != 0:
        return False
    return bool(re.search(rf"(?m)^\s*Name:\s+{re.escape(name)}\s*$",
                          res.stdout))


def install_cron_jobs(profile: str, dry_run: bool = False) -> list[str]:
    """Create the standard maintenance cron jobs on a profile, idempotently.

    The profile is the one the manager role is bound to — role-dependent,
    never hardcoded. Jobs are created through the hermes CLI so the gateway
    owns the store format; a job whose name already exists is left untouched
    (the user may have customised it). Returns recap lines.
    """
    import subprocess

    out: list[str] = []
    for spec in CRON_JOBS:
        name = spec["name"]
        if dry_run:
            out.append(f"[dry-run] cron create {name} on {profile} "
                       f"({spec['schedule']})")
            continue
        if _cron_job_exists(profile, name):
            out.append(f"cron: {name} already exists on {profile} "
                       "(left untouched)")
            continue
        cmd = _cron_cmd(profile, "cron", "create",
                        spec["schedule"], spec["prompt"],
                        "--name", name, "--deliver", "local")
        for skill in spec["skills"]:
            cmd += ["--skill", skill]
        try:
            res = subprocess.run(cmd, check=False, capture_output=True,
                                 text=True, timeout=120)
        except FileNotFoundError:
            out.append(f"WARNING: cron create failed for {name} on "
                       f"{profile}: hermes CLI not found")
            continue
        if res.returncode == 0:
            out.append(f"cron: {name} created on {profile} "
                       f"({spec['schedule']})")
        else:
            detail = (res.stderr or res.stdout).strip()
            out.append(f"WARNING: cron create failed for {name} on "
                       f"{profile}: {detail}")
    return out


def _parse_cron_list(stdout: str) -> list[dict]:
    """Parse `hermes cron list` table output into job dicts.

    The CLI has no --json flag, so the table is the interface. Each job
    block starts with an indented `<job_id> [<state>]` line, followed by
    indented `Key: value` lines (`Name:`, `Schedule:`, `Skills:`,
    `Deliver:`, ...). Unknown keys are ignored; a block without a Name is
    dropped (nothing to key on). Skills are comma-separated in the table
    and come back as a list.
    """
    import re

    jobs: list[dict] = []
    cur: dict | None = None
    head = re.compile(r"^\s*([0-9a-fA-F]{6,})\s+\[")
    field = re.compile(r"^\s+([A-Za-z][A-Za-z ]*?):\s*(.*?)\s*$")
    for line in stdout.splitlines():
        m = head.match(line)
        if m:
            cur = {"job_id": m.group(1), "name": None,
                   "schedule": None, "skills": [], "deliver": None}
            jobs.append(cur)
            continue
        m = field.match(line)
        if not m:
            continue
        key, val = m.group(1).strip().lower(), m.group(2)
        if cur is None:
            # A Name line with no preceding id header (older/partial
            # output): synthesise a block so name lookups still work.
            cur = {"job_id": None, "name": None,
                   "schedule": None, "skills": [], "deliver": None}
            jobs.append(cur)
        if key == "name":
            cur["name"] = val
        elif key == "schedule":
            cur["schedule"] = val
        elif key == "deliver":
            cur["deliver"] = val
        elif key == "skills":
            cur["skills"] = [s.strip() for s in val.split(",") if s.strip()]
    return [j for j in jobs if j["name"]]


def _cron_list_jobs(profile: str) -> tuple[list[dict], str | None]:
    """The profile's live cron jobs, plus an error string when unreadable.

    Returns ([], "<detail>") when the CLI is missing or exits non-zero —
    the caller surfaces that as a WARNING and does nothing else (failing
    safe: never create a duplicate, never edit blind).
    """
    import subprocess

    try:
        res = subprocess.run(_cron_cmd(profile, "cron", "list"),
                             check=False, capture_output=True, text=True,
                             timeout=120)
    except FileNotFoundError:
        return [], "hermes CLI not found"
    if res.returncode != 0:
        return [], ((res.stderr or res.stdout).strip() or "cron list failed")
    return _parse_cron_list(res.stdout), None


def sync_cron_jobs(profile: str, dry_run: bool = False) -> list[str]:
    """Bring the profile's maintenance cron jobs in line with CRON_JOBS.

    The update path for `setup.py --refresh` (run after `hermes plugins
    update`). `install_cron_jobs` is create-only: a live job whose NAME
    already exists is left untouched, so a changed schedule/prompt/skills
    in CRON_JOBS never reached an installed profile. This subsumes it:

    * name MISSING          → `cron create` (same command as install)
    * name EXISTS, drifted  → `cron edit <job_id> --schedule ... --prompt
      ... --skill ...` (schedule and/or skills differ from the repo spec)
    * name EXISTS, matches  → no-op ("in sync")

    Comparison uses the live `Schedule` and `Skills` read back from
    `hermes cron list` (the table is the only interface — no --json). The
    prompt is NOT compared: it can be truncated in the table, so on the
    edit path it is always re-sent, which makes the live prompt match the
    repo. Failure-tolerant: every subprocess error becomes a `WARNING:`
    recap line, never an exception. dry_run shells out nothing.
    Returns recap lines.
    """
    import subprocess

    out: list[str] = []
    if dry_run:
        for spec in CRON_JOBS:
            out.append(f"[dry-run] cron sync {spec['name']} on {profile} "
                       f"({spec['schedule']})")
        return out

    jobs, err = _cron_list_jobs(profile)
    if err is not None:
        out.append(f"WARNING: cron sync failed on {profile}: cron list: {err}")
        return out
    by_name = {j["name"]: j for j in jobs}

    for spec in CRON_JOBS:
        name = spec["name"]
        live = by_name.get(name)
        if live is None:
            cmd = _cron_cmd(profile, "cron", "create",
                            spec["schedule"], spec["prompt"],
                            "--name", name, "--deliver", "local")
            for skill in spec["skills"]:
                cmd += ["--skill", skill]
            verb, past = "create", "created"
        else:
            drift = []
            if (live["schedule"] or "") != spec["schedule"]:
                drift.append(f"schedule {live['schedule']!r}→"
                             f"{spec['schedule']!r}")
            if live["skills"] != spec["skills"]:
                drift.append(f"skills {live['skills']}→{spec['skills']}")
            if not drift:
                out.append(f"cron: {name} in sync on {profile} "
                           f"({spec['schedule']})")
                continue
            if not live["job_id"]:
                out.append(f"WARNING: cron sync failed for {name} on "
                           f"{profile}: drifted ({'; '.join(drift)}) but no "
                           "job id parsed from cron list")
                continue
            cmd = _cron_cmd(profile, "cron", "edit", live["job_id"],
                            "--schedule", spec["schedule"],
                            "--prompt", spec["prompt"])
            for skill in spec["skills"]:
                cmd += ["--skill", skill]
            verb, past = "edit", f"updated ({'; '.join(drift)})"

        try:
            res = subprocess.run(cmd, check=False, capture_output=True,
                                 text=True, timeout=120)
        except FileNotFoundError:
            out.append(f"WARNING: cron {verb} failed for {name} on "
                       f"{profile}: hermes CLI not found")
            continue
        if res.returncode == 0:
            out.append(f"cron: {name} {past} on {profile} "
                       f"({spec['schedule']})")
        else:
            detail = (res.stderr or res.stdout).strip()
            out.append(f"WARNING: cron {verb} failed for {name} on "
                       f"{profile}: {detail}")
    return out


def disable_profile_moa(profile: str, dry_run: bool = False) -> list[str]:
    """Disable MoA (mixture-of-agents fanout) for a profile's agent turns.

    Why: a manager-profile turn with MoA enabled (fanout: user_turn) fires
    several parallel LLM calls per turn against one API key. When the
    maintenance cron jobs fire together (incl. a gateway catch-up burst) the
    parallel fanout from each job stacks into ~6 simultaneous calls and hits
    HTTP 429, erroring the run. Disabling MoA makes every turn a single
    sequential call — the manager role has no interactive fanout need.

    This is a SETUP/refresh step (not a one-off edit) so a fresh install of
    the manager role gets it automatically. Only the manager/combined role
    profile is touched (the caller decides — contributors may keep MoA for
    interactive work).

    Interface: the hermes CLI, matching the existing pattern
    (`enable_plugin_for_profile` uses `hermes --profile NAME plugins enable`;
    `_cron_cmd` uses `hermes --profile NAME cron ...`). The command is::

        hermes [--profile NAME] config set moa.enabled false

    Idempotent: a key already set false is a no-op CLI write. Failure-
    tolerant: any subprocess error (CLI missing, non-zero exit) is surfaced
    as a WARNING recap line and never raises — setup must not crash on it.
    dry_run shells out nothing (mirrors install_cron_jobs): it only appends
    a `[dry-run]` recap line. Returns recap lines.
    """
    import subprocess

    out: list[str] = []
    if dry_run:
        out.append(f"[dry-run] config set moa.enabled false on {profile}")
        return out
    cmd = _cron_cmd(profile, "config", "set", "moa.enabled", "false")
    try:
        res = subprocess.run(cmd, check=False, capture_output=True,
                             text=True, timeout=120)
    except FileNotFoundError:
        out.append(f"WARNING: MoA disable failed for {profile}: "
                   f"hermes CLI not found")
        return out
    if res.returncode == 0:
        out.append(f"moa: disabled for {profile} (moa.enabled=false)")
    else:
        detail = (res.stderr or res.stdout).strip()
        out.append(f"WARNING: MoA disable failed for {profile}: {detail}")
    return out


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

#: Per-domain .vault configs. Each domain declares its
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
    # P7: the root conventions file — seeded once from the template, grows
    # through interaction; never a preset artifact.
    ensure_root_conventions(vault_root)
    return created



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
                ("meta", ["work/creative/**"]),      # the backstop grant (P7)
                ("read", ["work/creative/**", "work/*/knowledge/**"])]
    if role == "dev":
        return [("write", ["work/coding/**"]),
                ("config", ["work/coding/**"]),
                ("meta", ["work/coding/**"]),        # the backstop grant (P7)
                ("read", ["work/coding/**", "work/*/knowledge/**"])]
    if role == "researcher":
        # Literal subdomain globs (P7): knowledge folders are
        # OWNED — the wildcard write glob is a capability and never owns.
        # The wildcard survives as read-only (research reads every domain).
        return [("write", ["work/creative/knowledge/**",
                           "work/coding/knowledge/**"]),
                ("config", ["work/creative/knowledge/**",
                            "work/coding/knowledge/**"]),
                ("meta", ["work/creative/knowledge/**",
                          "work/coding/knowledge/**"]),
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
    block_end = end  # frozen scan bound — `end` below is the RUNNING insert
    # position and must not grow the range a later kind scans (two missing
    # kinds in a row used to walk past the line list — IndexError; meta in
    # the role grant sets exposed it).
    for kind, globs in needed:
        found = None
        for i in range(start, block_end):
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

def ensure_root_conventions(vault_root: Path, dry_run: bool = False) -> Path:
    """Seed the vault's root conventions file (P7 §4.2).

    ``.vault/conventions.md`` from ``templates/vault-conventions.md``, with
    the vault name substituted. Copy-if-missing — never overwrites an
    existing file: it grows through interaction (the installer's survival
    guarantee). Per-scope files are the scope owner's to create via
    ``obsidian_conventions``; the installer only seeds the root. The root
    file is vault-wide in scope (rules that bind every domain); ``default``
    holds the write glob for it, like ``README.md``, but that is a grant,
    not a scope — a domain's own rules go in that domain's
    ``.vault/conventions.md``. The manager never writes conventions.
    """
    dst = vault_root / ".vault" / "conventions.md"
    if dst.exists():
        return dst
    if dry_run:
        print(f"[dry-run] create {dst} from template")
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    text = (BUNDLED_SKILL / "templates" / "vault-conventions.md"
            ).read_text(encoding="utf-8")
    text = text.replace("<Vault name>", vault_root.name)
    dst.write_text(text, encoding="utf-8")
    return dst


def _validate_domain_bind(roles_path: Path, profile: str, domain: str) -> None:
    """Refuse a ``bind --domain`` that is malformed, content, or a duplicate (P7).

    Shape: a domain (``creative``) or a one-level subdomain path
    (``creative/knowledge``); deeper paths are content, not ownership
    boundaries. A subdomain bind is refused when the profile already owns
    the parent (same owner ⇒ content — use ``obsidian_scaffold``) and when
    the ownership glob is already held by another agent (a subdomain needs
    a single owner). Raises before any write — the caller runs this before
    creating anything.
    """
    from vault.grants import load_roles
    from vault.ownership import duplicate_ownership_globs

    parts = [p for p in domain.strip("/").split("/") if p]
    if not 1 <= len(parts) <= 2 or any(
            any(c in p for c in "*?[") for p in parts):
        raise ValueError(
            "--domain must be a domain or a one-level subdomain path "
            f"(e.g. 'creative' or 'creative/knowledge'), got {domain!r}")
    if len(parts) == 1:
        return

    parent, sub = parts
    roles = load_roles(roles_path.parent.parent)
    if roles.allows(profile, "edit", f"work/{parent}/.placeholder"):
        raise ValueError(
            f"{profile} already owns work/{parent}/ — a subfolder with the "
            f"same owner is content, not a subdomain; use obsidian_scaffold "
            f"instead of --domain")
    new_glob = f"work/{parent}/{sub}/**"
    others = {name: g.globs("write")
              for name, g in roles.agents.items() if name != profile}
    conflicts = duplicate_ownership_globs({**others, profile: [new_glob]})
    if conflicts:
        raise ValueError(
            f"refusing --domain {domain}: {conflicts[0]} — a subdomain "
            f"needs a single owner")


def _append_agent_grant(roles_path: Path, owner: str, domain: str,
                        dry_run: bool = False) -> bool:
    """Ensure an owner's grant block covers ``work/<domain>/**``.

    ``domain`` is a slashed path: ``creative`` (domain) or
    ``creative/knowledge`` (subdomain, P7). A domain bind grants
    write/config/meta on the tree + the shared-knowledge read; a subdomain
    bind grants write/config/meta on the subdomain + read over the PARENT
    (N-4 — the parent owner's meta backstop already covers it). Validation
    happens in role_bind before any write.
    """
    if not roles_path.is_file():
        raise FileNotFoundError(f"roles.yaml not found: {roles_path}")
    parts = [p for p in domain.strip("/").split("/") if p]
    if len(parts) == 1:
        needed = [
            ("write", [f"work/{domain}/**"]),
            ("config", [f"work/{domain}/**"]),
            ("meta", [f"work/{domain}/**"]),      # the backstop grant (P7)
            ("read", [f"work/{domain}/**", "work/*/knowledge/**"]),
        ]
    else:
        parent = parts[0]
        needed = [
            ("write", [f"work/{domain}/**"]),
            ("config", [f"work/{domain}/**"]),
            ("meta", [f"work/{domain}/**"]),
            ("read", [f"work/{parent}/**"]),      # read over the parent (N-4)
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


def _system_config_stub() -> str:
    """Minimal honest config for the system tree — extends the root schema
    with no vocabulary of its own. The owner evolves fields afterwards via
    obsidian_edit_config (mechanical, tool-mediated); the starter preset
    ships the full system-records vocabulary instead (spec/record/...)."""
    return (
        "# system — system-records config (growth protocol)\n"
        "# Extends the root schema via union. Declare what this tree adds\n"
        "# or changes; never re-declare root fields.\n"
        "# E.g.:\n"
        "#   fields:\n"
        "#     kind:\n"
        "#       allowed: [spec, decision, log]\n"
    )


def _validate_system_bind(roles_path: Path, profile: str) -> None:
    """Refuse a ``--system`` bind whose ownership glob is already held.

    The system tree has a single owner, like any domain: another agent
    holding ``system/**`` makes ownership ambiguous (P7). Raises before
    any write — the caller runs this before creating anything.
    """
    from vault.grants import load_roles
    from vault.ownership import duplicate_ownership_globs

    roles = load_roles(roles_path.parent.parent)
    others = {name: g.globs("write")
              for name, g in roles.agents.items() if name != profile}
    conflicts = duplicate_ownership_globs({**others, profile: ["system/**"]})
    if conflicts:
        raise ValueError(
            f"refusing --system: {conflicts[0]} — the system tree needs a "
            f"single owner")


def _append_system_grant(roles_path: Path, owner: str,
                         dry_run: bool = False) -> bool:
    """Ensure the owner's grant block covers the system tree (``system/**``).

    The system tree is the reserved root content tree (handbook, logs,
    decisions — the standard preset's shape). A ``--system`` bind grants
    write + config on it, exactly like the starter preset's ``default``
    block; the tree + config are created in role_bind before this runs.
    """
    if not roles_path.is_file():
        raise FileNotFoundError(f"roles.yaml not found: {roles_path}")
    needed = [
        ("write", ["system/**"]),
        ("config", ["system/**"]),
    ]
    return _ensure_agent_block(roles_path, owner, needed,
                               dry_run=dry_run, label="system")


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


# --- role mutation (P6) ------------------------------
#
# Grants are the truth: a profile's role is derived from its live roles.yaml
# block (active meta/config/read-`**` ⇒ manager; any write/append globs ⇒
# contributor; both ⇒ combined; none ⇒ unbound). The SOUL block is the bind
# marker. Every write here is comment-preserving, idempotent, dry-run-aware.

def _active_agent_names(roles_path: Path) -> list[str]:
    """Profile names with an ACTIVE (non-commented) grant block."""
    import re as _re
    text = roles_path.read_text(encoding="utf-8")
    return _re.findall(r"(?m)^  ([a-zA-Z0-9_-]+):\s*$", text)


def _block_span(lines: list[str], profile: str) -> tuple[int, int]:
    """(start, end) line span of a profile's grant block.

    The block is its two-space header plus ``    kind:`` lines; the first
    non-blank line that is neither ends it (a sibling comment or the next
    agent key). StopIteration when the profile has no active block.
    """
    import re as _re
    start = next(i for i, ln in enumerate(lines)
                 if _re.match(rf"^  {_re.escape(profile)}:\s*$", ln))
    end = len(lines)
    for i in range(start + 1, len(lines)):
        ln = lines[i]
        if not ln.strip():
            continue
        if _re.match(r"^    [a-zA-Z0-9_-]+:", ln):
            continue
        end = i
        break
    return start, end


def _block_text(roles_path: Path, profile: str) -> str:
    """Raw text of a profile's active grant block ('' when none)."""
    try:
        lines = roles_path.read_text(encoding="utf-8").splitlines(keepends=True)
        start, end = _block_span(lines, profile)
        return "".join(lines[start:end])
    except (FileNotFoundError, StopIteration):
        return ""


def _is_manager_block(block: str) -> bool:
    """True when a grant block holds the ROOT meta glob ``\"**\"``.

    Since P7 a combined profile's meta line is ``[\"work/<d>/**\", \"**\"]``
    (the domain backstop) — the manager is the agent whose meta list
    contains the root glob, not one holding only it.
    """
    import re as _re
    return bool(_re.search(r'^    meta:\s*\[[^\]]*"\*\*"', block, _re.M))


def _manager_profile(roles_path: Path) -> str | None:
    """The profile holding the active manager block (meta: [\"**\"])."""
    import re as _re
    if not roles_path.is_file():
        return None
    for name in _active_agent_names(roles_path):
        if _is_manager_block(_block_text(roles_path, name)):
            return name
    return None


def _roles_from_grants(roles_path: Path, profile: str) -> set[str]:
    """Derive a profile's vault roles from its live grant block (§4.5)."""
    import re as _re
    block = _block_text(roles_path, profile)
    if not block:
        return set()
    roles: set[str] = set()
    if _is_manager_block(block):
        roles.add("manager")
    if _re.search(r"^    (write|append):", block, _re.M):
        roles.add("contributor")
    return roles


def _revoke_globs(roles_path: Path, profile: str,
                  pairs: list[tuple[str, list[str]]],
                  dry_run: bool = False) -> bool:
    """Remove (kind, globs) from a profile's grant block.

    The mutation core (§4.5): exact-glob removal per kind line; kind lines
    that empty are dropped; a block left with no kind lines is COMMENTED
    OUT (comment-preserving, deny-by-default — the blank preset's manager
    stub pattern; the text survives for re-binding). Idempotent.
    """
    import re as _re
    import yaml
    if not roles_path.is_file():
        raise FileNotFoundError(f"roles.yaml not found: {roles_path}")
    lines = roles_path.read_text(encoding="utf-8").splitlines(keepends=True)
    try:
        start, end = _block_span(lines, profile)
    except StopIteration:
        return False  # no active block — nothing to revoke
    orig_block = lines[start:end]
    wanted = {kind: set(globs) for kind, globs in pairs}
    changed = False
    for i in range(start, end):
        m = _re.match(r"^    ([a-zA-Z0-9_-]+):\s*\[(.*?)\]\s*$",
                      lines[i].strip("\n"))
        if not m or m.group(1) not in wanted:
            continue
        globs = _re.findall(r'"([^"]+)"', m.group(2))
        keep = [g for g in globs if g not in wanted[m.group(1)]]
        if len(keep) != len(globs):
            lines[i] = f"    {m.group(1)}: {_fmt_globs(keep)}\n"
            changed = True
    if not changed:
        return False
    if dry_run:
        print(f"[dry-run] roles.yaml − revoke from {profile}: {pairs}")
        return True
    # drop emptied kind lines
    out: list[str] = []
    kept_kind = False
    for i, ln in enumerate(lines):
        if start <= i < end:
            if _re.match(r"^    [a-zA-Z0-9_-]+:\s*\[\]", ln):
                continue  # emptied kind line
            if _re.match(r"^    [a-zA-Z0-9_-]+:", ln):
                kept_kind = True
            out.append(ln)
        else:
            out.append(ln)
    if not kept_kind:
        # block emptied — comment it out, preserving the ORIGINAL text
        # (deny-by-default stub, the blank preset's manager style)
        out = []
        for i, ln in enumerate(lines):
            if start <= i < end:
                orig_ln = orig_block[i - start]
                out.append(("  # " + orig_ln.lstrip()) if orig_ln.strip()
                           else orig_ln)
            else:
                out.append(ln)
    text = "".join(out)
    yaml.safe_load(text)  # never ship broken YAML
    roles_path.write_text(text, encoding="utf-8")
    return True


def _domain_owned_globs(roles_path: Path, profile: str,
                        domain: str) -> list[tuple[str, list[str]]]:
    """Globs a profile actually holds under ``work/<domain>/``, by kind."""
    import re as _re
    prefix = f"work/{domain}/"
    folded_prefix = prefix.casefold()
    block = _block_text(roles_path, profile)
    pairs: list[tuple[str, list[str]]] = []
    for m in _re.finditer(r"(?m)^    ([a-zA-Z0-9_-]+):\s*\[(.*?)\]",
                          block):
        kind, raw = m.group(1), m.group(2)
        owned = [g for g in _re.findall(r'"([^"]+)"', raw)
                 if g.casefold().startswith(folded_prefix)]
        if owned:
            pairs.append((kind, owned))
    return pairs


def remove_soul_sections(soul_path: Path) -> bool:
    """Remove the anchored managed block from a profile SOUL.

    The managed region starts at the vault-soul anchor comment and spans
    TWO top-level sections (2026-08-07): `## Inter-agent awareness` then
    the `## Vault` umbrella — the Vault umbrella is always the block's
    last `##` section. The block ends at the next level-1 heading after
    it (user content) or EOF; a preceding blank separator is collapsed.
    A full role SOUL (P8.1) whose remaining prose is exactly a shipped
    template — engine-written, zero user intent — is restored to
    ``DEFAULT_SOUL_MD`` (the pre-bind seed) instead of being left as a
    stale identity after unbind. User content is always preserved.
    Returns True if anything was removed.
    """
    import re as _re
    if not soul_path.is_file():
        return False
    text = soul_path.read_text(encoding="utf-8")
    idx = text.find(SOUL_ANCHOR)
    if idx == -1:
        return False
    line_start = text.rfind("\n", 0, idx) + 1
    after_anchor = text.find("\n", idx) + 1  # first char past the anchor line
    vault_pos = text.find("## Vault", after_anchor)
    if vault_pos == -1:
        # Corrupted/mismatched block — refuse rather than half-remove.
        return False
    # The block's own `## Vault` closes the managed region; anything after
    # it that is another level-1 heading is user content.
    vault_line_end = text.find("\n", vault_pos) + 1
    m = _re.search(r"(?m)^## [^#]", text[vault_line_end:])
    end = len(text)
    if m:
        end = vault_line_end + m.start()
    head = text[:line_start]
    if head.endswith("\n\n"):
        head = head[:-1]
    remainder = head + text[end:]
    # P8.1: a full soul whose prose is exactly a shipped template is
    # engine-written — restore the pre-bind seed rather than leave a
    # stale identity (the same "a stale block lies" rule, applied to the
    # identity layer).
    normalized = _normalize_soul(remainder)
    if normalized and normalized != _normalize_soul(DEFAULT_SOUL_MD):
        for identity in SOUL_IDENTITIES:
            prose = _soul_template(identity)
            if prose and normalized == _normalize_soul(prose):
                remainder = DEFAULT_SOUL_MD
                break
    if remainder == text:
        return False
    soul_path.write_text(remainder, encoding="utf-8")
    return True


def uninstall_skills(profile_skills: Path, vault_root: Path) -> None:
    """Remove a profile's vault skill overlay + this vault's conventions file.

    Symlink surfaces (SKILL.md, references/, templates/) are unlinked for
    both role skills; real copy-on-write content is preserved; empty dirs
    are pruned up the chain. (The vault's conventions file is in-tree
    since P7 — never a profile artifact.)
    """
    # conventions moved in-tree (P7) — the vault's .vault/conventions.md is
    # the vault's, never unlinked with a profile
    for name in ("obsidian-vault", "obsidian-vault-management"):
        target = profile_skills / "note-taking" / name
        if not target.is_dir():
            continue
        for sub in ("SKILL.md", "references", "templates"):
            link = target / sub
            if link.is_symlink():
                link.unlink()
        if not any(target.iterdir()):
            target.rmdir()
    root = profile_skills / "note-taking"
    if root.is_dir() and not any(root.iterdir()):
        root.rmdir()


def remove_profile_env(prof_home: Path) -> bool:
    """Drop the vault env vars from a profile .env (unbind)."""
    env_path = prof_home / ".env"
    if not env_path.is_file():
        return False
    before = env_path.read_text(encoding="utf-8")
    lines = [ln for ln in before.splitlines()
             if not ln.startswith(("OBSIDIAN_VAULT_PATH=",
                                   "OBSIDIAN_VAULT_AGENT="))]
    after = "\n".join(lines) + ("\n" if lines else "")
    if after == before:
        return False
    env_path.write_text(after, encoding="utf-8")
    return True


def _surface_for_roles(hermes_home: Path, profile: str, roles: set[str],
                       vault_root: Path, dry_run: bool) -> None:
    """Align a profile's skill overlay + SOUL block with its live roles.

    Empty roles ⇒ full cleanup: SOUL block removed, skills uninstalled,
    vault env dropped (the profile is unbound).
    """
    prof_home = profile_home(hermes_home, profile)
    if not roles:
        if not dry_run:
            remove_soul_sections(prof_home / "SOUL.md")
            uninstall_skills(prof_home / "skills", vault_root)
            remove_profile_env(prof_home)
        print(f"profile {profile}: unbound (surface removed)")
        return
    skill_role = _role_skill(roles)
    if not dry_run:
        install_skills(prof_home / "skills", role=skill_role)
        # Re-alignment carries no identity (generic grants): block-only
        # refresh — an existing full-soul prose is preserved by the
        # anchor-replace path.
        ensure_soul_sections(prof_home / "SOUL.md", skill_role,
                             profile_name=profile)
    print(f"profile {profile}: {skill_role} "
          f"({', '.join(sorted(roles))})")


def role_bind(hermes_home: Path, vault_root: Path, profile: str,
              new: bool = False, manager_role: bool = False,
              domain: str = "", config_file: str = "",
              system_tree: bool = False, soul_file: str = "",
              dry_run: bool = False) -> None:
    """Bind a profile to the vault (§4.5): ability surface + grants.

    Without ``--domain``/``--system``: profile-level bind (skill overlay +
    SOUL variant + config seed + plugin enable + env) as contributor or
    ``--manager``.
    With ``--domain`` (contributor-only): also create ``work/<name>/`` +
    ``.vault/config.yaml`` (stub or ``--config``) when missing and grant
    it.
    With ``--system`` (contributor-only): also create the reserved system
    tree ``system/`` + its config (stub or ``--config``) and grant
    write/config over ``system/**`` — the standard preset's ``default``
    block, made reachable as a growth action.
    With ``--soul FILE``: write the file's identity prose as the profile
    SOUL's identity (manager-drafted, user-confirmed — S-7/note c),
    preserving the managed block. Supersedes the identity templates.
    Idempotent. Refuses: ``--manager`` with ``--domain`` or ``--system``;
    a domain/system bind on the manager profile (managers hold no content
    grants).
    """
    if manager_role and (domain or system_tree):
        raise ValueError("--manager and --domain/--system are mutually "
                         "exclusive (managers hold no content grants)")
    if domain and system_tree:
        raise ValueError("--domain and --system are mutually exclusive")
    import yaml
    roles_path = vault_root / ".vault" / "roles.yaml"
    if not roles_path.is_file():
        raise FileNotFoundError(
            f"{roles_path} missing — scaffold the vault first")
    prof_home = profile_home(hermes_home, profile)
    created = new and not prof_home.is_dir()
    if new:
        if not prof_home.is_dir():
            _create_profile(profile, "Vault manager" if manager_role
                            else "Vault contributor")
    elif not prof_home.is_dir():
        raise FileNotFoundError(
            f"profile '{profile}' does not exist — use --new to create it")
    if manager_role:
        _grant_role(roles_path, profile, "manager", dry_run=dry_run)
    elif domain:
        if _manager_profile(roles_path) == profile:
            raise ValueError(
                f"{profile} is the manager — managers hold no content "
                f"grants; bind a contributor profile instead")
        # P7: refuse before any write — shape, content-not-subdomain, and
        # duplicate-ownership violations must not create a directory first.
        _validate_domain_bind(roles_path, profile, domain)
        # Case-correcting resolution (vault.paths.safe_join): a renamed
        # `work`/parent container is reused, never shadow-created; the new
        # domain keeps the caller's spelling.
        from vault.paths import safe_join as _safe_join
        domain_dir = _safe_join(vault_root, f"work/{domain}")
        if not domain_dir.is_dir() and not dry_run:
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
        if dry_run:
            print(f"[dry-run] mkdir {domain_dir} + .vault/config.yaml")
        _append_agent_grant(roles_path, profile, domain, dry_run=dry_run)
    elif system_tree:
        if _manager_profile(roles_path) == profile:
            raise ValueError(
                f"{profile} is the manager — managers hold no content "
                f"grants; bind a contributor profile instead")
        # Refuse before any write — duplicate ownership must not create a
        # directory first.
        _validate_system_bind(roles_path, profile)
        from vault.paths import safe_join as _safe_join
        sys_dir = _safe_join(vault_root, "system")
        if not sys_dir.is_dir() and not dry_run:
            (sys_dir / ".vault").mkdir(parents=True, exist_ok=True)
            if config_file:
                cfg = Path(config_file)
                if not cfg.is_file():
                    raise FileNotFoundError(f"config file not found: {cfg}")
                raw = cfg.read_text(encoding="utf-8")
                yaml.safe_load(raw)  # refuse to ship broken YAML
                (sys_dir / ".vault" / "config.yaml").write_text(
                    raw, encoding="utf-8")
            else:
                (sys_dir / ".vault" / "config.yaml").write_text(
                    _system_config_stub(), encoding="utf-8")
        if dry_run:
            print(f"[dry-run] mkdir {sys_dir} + .vault/config.yaml")
        _append_system_grant(roles_path, profile, dry_run=dry_run)
    # surface aligned to the (now) live grants — combined when the profile
    # already held content grants and is now also the manager
    existing = _roles_from_grants(roles_path, profile)
    roles = existing | ({"manager"} if manager_role else {"contributor"})
    skill_role = _role_skill(roles)
    if not dry_run:
        install_skills(prof_home / "skills", role=skill_role)
        # P8.1: identity selection. `--soul FILE` supersedes the templates
        # (manager-drafted, user-confirmed). Otherwise: a `--system` bind
        # carries the system-owner identity; a `--manager --new` bind
        # carries the manager identity (a NEW profile created for the
        # manager role — existing manager profiles keep their own
        # identity, block-only). Domain binds leave identity empty
        # (generation is the `--soul FILE` step, S-6/S-7). `default`
        # never gets a full soul (S-3 — enforced inside
        # ensure_soul_sections).
        if soul_file:
            _apply_soul_prose(prof_home / "SOUL.md", soul_file, skill_role)
            identity = ""
        else:
            identity = "system-owner" if (system_tree and created) else (
                "manager" if (manager_role and created) else "")
        ensure_soul_sections(prof_home / "SOUL.md", skill_role,
                             profile_name=profile, identity=identity)
        ensure_peer_memory(hermes_home, profile)
        seed_profile_config(hermes_home, profile)
        enable_plugin_for_profile(hermes_home, profile, vault_root)
    # Note c (2026-08-06): adding a domain to a profile that already has a
    # full role SOUL may stale its identity — the manager should review.
    if domain and not dry_run and _soul_has_identity(
            prof_home / "SOUL.md"):
        print(f"note: {profile} has a full role SOUL; its identity may "
              f"need review after adding domain '{domain}' — the manager "
              f"drafts an update, user confirms, `bind --soul FILE` writes.")
    print(f"bound {profile}: {skill_role}"
          + (f" + domain work/{domain}/**" if domain else "")
          + (" + system tree (system/**)" if system_tree else ""))


def role_unbind(hermes_home: Path, vault_root: Path, profile: str,
                domain: str = "", dry_run: bool = False) -> None:
    """Unbind a profile from the vault (§4.5).

    Without ``--domain``: full unbind — grant block commented out, SOUL
    ``## Vault`` block removed, skill overlay uninstalled, vault env vars
    dropped; notice that owned domain trees remain. With ``--domain``:
    unown just that domain (globs revoked, tree kept). Refuses: unbinding
    the manager (a vault must keep a manager — use ``transfer``); a domain
    unown on the manager.
    """
    roles_path = vault_root / ".vault" / "roles.yaml"
    if not roles_path.is_file():
        raise FileNotFoundError(f"roles.yaml not found: {roles_path}")
    prof_home = profile_home(hermes_home, profile)
    if domain:
        if _roles_from_grants(roles_path, profile) == {"manager"}:
            raise ValueError(
                f"{profile} is a pure manager — managers hold no content "
                f"grants to revoke")
        pairs = _domain_owned_globs(roles_path, profile, domain)
        if not pairs:
            raise ValueError(
                f"{profile} holds no grants under work/{domain}/")
        _revoke_globs(roles_path, profile, pairs, dry_run=dry_run)
        # P7: a subdomain bind also granted read over the parent — revoke
        # it when no other subdomain under the same parent remains (a
        # remaining write glob there, e.g. the parent itself, keeps it).
        parts = [p for p in domain.strip("/").split("/") if p]
        if len(parts) == 2:
            remaining_write = [
                g for kind, globs in _domain_owned_globs(
                    roles_path, profile, parts[0])
                for g in globs if kind == "write"]
            if not remaining_write:
                _revoke_globs(roles_path, profile,
                              [("read", [f"work/{parts[0]}/**"])],
                              dry_run=dry_run)
        print(f"domain work/{domain}/**: unowned from {profile}\n"
              "  notice: the tree remains — remove it manually if wanted")
        return
    if _manager_profile(roles_path) == profile:
        raise ValueError(
            f"{profile} is the manager — a vault must keep a manager; "
            f"use --role transfer {profile} --to NEW")
    block = _block_text(roles_path, profile)
    if not block:
        print(f"{profile}: no active grants — nothing to revoke")
    else:
        import re as _re2
        pairs = [(m.group(1), _re2.findall(r'"([^"]+)"', m.group(2)))
                 for m in _re2.finditer(
                     r"(?m)^    ([a-zA-Z0-9_-]+):\s*\[(.*?)\]", block)]
        _revoke_globs(roles_path, profile, pairs, dry_run=dry_run)
    if not dry_run and not _active_agent_names(roles_path):
        raise ValueError(
            "refusing: the vault would have no bound profiles at all")
    if profile == "default":
        print("  warning: default was the system owner — the skill stays "
              "reachable as plugin:obsidian-vault")
    if not dry_run:
        remove_soul_sections(prof_home / "SOUL.md")
        uninstall_skills(prof_home / "skills", vault_root)
        remove_profile_env(prof_home)
    print(f"unbound {profile} from {vault_root}\n"
          "  notice: owned domain trees remain — remove them manually "
          "if wanted")


def role_transfer(hermes_home: Path, vault_root: Path, profile: str,
                  to: str, domain: str = "", dry_run: bool = False) -> None:
    """Move a role or domain ownership A → B (§4.5).

    Without ``--domain``: manager handoff — B gains the manager grant and
    its surface is refreshed (combined when B already holds content
    grants); A is re-derived from its remaining grants (contributor
    surface, or full unbind when nothing remains). With ``--domain``:
    domain ownership moves A → B (B must be a bound contributor).
    """
    roles_path = vault_root / ".vault" / "roles.yaml"
    if not roles_path.is_file():
        raise FileNotFoundError(f"roles.yaml not found: {roles_path}")
    if to == profile:
        raise ValueError("transfer source and target are the same profile")
    target_home = profile_home(hermes_home, to)
    if not target_home.is_dir():
        raise FileNotFoundError(
            f"profile '{to}' does not exist — bind it first")
    if domain:
        if _roles_from_grants(roles_path, profile) == {"manager"}:
            raise ValueError(
                "the manager holds no content grants — --domain transfer "
                "is for contributors")
        pairs = _domain_owned_globs(roles_path, profile, domain)
        if not pairs:
            raise ValueError(
                f"{profile} holds no grants under work/{domain}/")
        _revoke_globs(roles_path, profile, pairs, dry_run=dry_run)
        _append_agent_grant(roles_path, to, domain, dry_run=dry_run)
        print(f"domain work/{domain}/**: {profile} → {to}")
        return
    if _manager_profile(roles_path) != profile:
        raise ValueError(
            f"{profile} is not the manager — a role transfer without "
            f"--domain hands off the manager role")
    _revoke_globs(roles_path, profile,
                  [("meta", ["**"]), ("config", ["**"]),
                   ("read", ["**"])], dry_run=dry_run)
    _grant_role(roles_path, to, "manager", dry_run=dry_run)
    src_roles = (_roles_from_grants(roles_path, profile)
                 if not dry_run else set())
    dst_roles = (_roles_from_grants(roles_path, to)
                 if not dry_run else {"manager"})
    _surface_for_roles(hermes_home, profile, src_roles, vault_root, dry_run)
    _surface_for_roles(hermes_home, to, dst_roles, vault_root, dry_run)
    print(f"manager role: {profile} → {to}")


def role_list(hermes_home: Path, vault_root: Path) -> None:
    """Who is bound to this vault: role, surface, grants, domains."""
    import re as _re
    roles_path = vault_root / ".vault" / "roles.yaml"
    if not roles_path.is_file():
        raise FileNotFoundError(f"roles.yaml not found: {roles_path}")
    print(f"vault: {vault_root}")
    print(f"manager: {_manager_profile(roles_path) or 'NONE'}")
    for name in _active_agent_names(roles_path):
        roles = _roles_from_grants(roles_path, name)
        prof_home = profile_home(hermes_home, name)
        soul = prof_home / "SOUL.md"
        soul_ok = soul.is_file() and SOUL_ANCHOR in soul.read_text(
            encoding="utf-8", errors="replace")
        skills_root = prof_home / "skills" / "note-taking"
        skills = sorted(p.name for p in skills_root.glob("obsidian-vault*")
                        if p.is_dir()) if skills_root.is_dir() else []
        block = _block_text(roles_path, name)
        domains = sorted(set(_re.findall(r'"work/([^/]+)/\*\*"', block)))
        print(f"  {name}: role={','.join(sorted(roles)) or 'unbound'}"
              f"  soul={'yes' if soul_ok else 'no'}"
              f"  skills={skills or 'none'}"
              f"  domains={domains}")


