"""``obsidian_context`` — the one call an agent makes before writing.

Spec §5. Returns the merged schema for a folder, its derived tag vocabulary,
sibling notes for linking, and a ready-to-fill template. Everything needed to
write a conforming note *in this folder*, and nothing about any other folder.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import ResolvedConfig, resolve_config
from .constants import (CONFIG_DIRNAME, STATE_DIRNAME, TODAY_TOKEN,
                        VOCABULARY_FLAG)
from .grants import GRANT_KINDS, RoleRegistry
from .notes import Note, derive_tags, derive_vocabulary, iter_notes
from .paths import relative_to_vault, safe_join
from .reference import describe

logger = logging.getLogger(__name__)

#: The bundled skill that owns writing procedure for this plugin. A vault may
#: override the pointer via root config ``conventions: {skill: ...}``; the
#: engine only ever returns the pointer (D7), never the content.
DEFAULT_CONVENTIONS_SKILL = "plugin:obsidian-vault"


def _vocab_compact(vocab: Dict[str, Any]) -> Dict[str, Any]:
    """Render vocabulary compactly: "name (n)" in use, bare name when unused.

    The verbose {"name":..,"count":..} form costs ~8x the tokens for the same
    information. An agent reads "essay (4)" faster than a JSON object, and the
    whole point of the context call is that it is cheap (§5).
    """
    out: Dict[str, Any] = {}
    declared = vocab.get("declared", [])
    used = [f"{e['name']} ({e['count']})" for e in declared if e["count"]]
    unused = [e["name"] for e in declared if not e["count"]]
    if used:
        out["declared"] = used
    if unused:
        out["declared_unused"] = unused
    observed = vocab.get("observed", [])
    if observed:
        out["observed"] = [f"{e['name']} ({e['count']})" for e in observed]
    return out


def _template(cfg: ResolvedConfig) -> str:
    """Build a frontmatter scaffold from required fields + defaults.

    Placeholders only — never sample values from a sibling note. Copying
    another note's tags into the template invites the agent to inherit them
    wholesale, which is how tag drift starts.
    """
    lines = ["---"]
    for name in cfg.required_fields:
        definition = cfg.fields.get(name, {})
        multi = bool(definition.get("multi"))

        if name in cfg.defaults:
            value = cfg.defaults[name]
            if value == TODAY_TOKEN:
                from datetime import date
                value = date.today().isoformat()
            if isinstance(value, list):
                lines.append(f"{name}: [{', '.join(str(i) for i in value)}]")
                continue
        else:
            allowed = cfg.allowed_values(name)
            if allowed and len(allowed) == 1:
                value = allowed[0]                  # restricted to one — fill it
            elif definition.get("format") == "date":
                value = "<YYYY-MM-DD>"
            else:
                value = f"<{name}>"

        lines.append(f"{name}: [{value}]" if multi else f"{name}: {value}")

    # The designated summary field, if this vault configured one. Advisory, so
    # it is prompted in the template even when not required — the agent is
    # nudged to give readers a one-line triage hook.
    if cfg.summary_field:
        lines.append(f'{cfg.summary_field}: "one-line summary of the note"')

    lines.append("---")
    return "\n".join(lines)


def _is_machinery_only(pattern: str) -> bool:
    """True when a grant pattern can only ever match engine machinery.

    Machinery dirs are ``.state`` (audit ledger, state dirname) and
    ``.vault`` (config discovery). A pattern scoped to either is
    maintenance plumbing, not content authorship — the manager's
    ``write: [".state/**"]`` (ledger maintenance) must not label it a
    contributor, while ``write: ["work/creative/**"]`` is real authorship.
    """
    p = pattern.strip("/")
    return (p in (STATE_DIRNAME, CONFIG_DIRNAME)
            or p.startswith(STATE_DIRNAME + "/")
            or p.startswith(CONFIG_DIRNAME + "/"))


def _role_directives(roles: Any, agent: str) -> List[str]:
    """Which role-directive files apply to this agent, derived from grants.

    The reference must be *derived from what the profile actually holds*,
    never blanket-listed: a profile gets a directive only for the roles its
    grants prove (2026-08-05, Davide: ``conventions_ref`` must reference
    both directives only when the calling profile holds both roles).

    - contributor.md — the agent authors and maintains content: holds
      ``write`` over a non-machinery path (machinery-only patterns are
      excluded — see :func:`_is_machinery_only`). ``append`` (create-only
      record-raising) is not authorship and does not qualify.
    - manager.md — the agent holds ``meta``/``config`` at the vault ROOT.
      Scope is the discriminator: a contributor's ``config`` is scoped to
      its own tree (D-5, e.g. ``work/creative/**``) and never matches the
      root; the manager's ``**`` patterns always do. A one-profile setup
      acting as both holds content write *and* root meta/config, so it
      gets both.
    """
    try:
        grants = roles.get(agent)
    except Exception:
        return []
    out: List[str] = []
    if any(not _is_machinery_only(p) for p in grants.globs("write")):
        out.append("conventions/contributor.md")
    if grants.matches("meta", ".") or grants.matches("config", "."):
        out.append("conventions/manager.md")
    return out


def _conventions_ref(cfg: ResolvedConfig,
                     agent: Optional[str] = None,
                     roles: Optional[Any] = None) -> Dict[str, Any]:
    """Where the writing rules for this vault live (D7 — pointer, not content).

    Defaults to the plugin's bundled skill; a vault may redirect via
    ``conventions: {skill: ...}`` in root config. When the caller's identity
    is known (agent + roles), the pointer also names the role-directive
    files that apply to *this* profile — one, the other, or both, derived
    from its grants. The tool never inlines the conventions themselves —
    the agent loads the skill it already knows.
    """
    ref: Dict[str, Any] = {
        "skill": (cfg.conventions or {}).get("skill")
        or DEFAULT_CONVENTIONS_SKILL,
    }
    if agent is not None and roles is not None:
        directives = _role_directives(roles, agent)
        if directives:
            ref["directives"] = directives
    return ref


def _grants_row(roles: RoleRegistry, agent: str, rel: str) -> Dict[str, bool]:
    """The caller's effective grants in one folder, as booleans.

    An agent learns whether it may act *before* being refused (§5 of `01`).
    The five grant kinds are universal; only the booleans vary per folder.
    A vault with no roles file grants nothing (deny by default), so the
    row is all-false rather than an error.
    """
    try:
        grants = roles.get(agent)
    except Exception:
        return {kind: False for kind in GRANT_KINDS}
    target = rel.strip("/") or "."
    return {kind: grants.matches(kind, target) for kind in GRANT_KINDS}


def build_context(
    vault_root: Path,
    folder: str,
    agent: Optional[str] = None,
    roles: Optional[RoleRegistry] = None,
    max_siblings: int = 25,
) -> Dict[str, Any]:
    """Assemble the context payload for ``folder``.

    When ``agent`` + ``roles`` are given, the payload also carries the
    caller's ``grants`` row (write/read/meta/config/append booleans for this
    folder) and the ``conventions_ref`` pointer (D7).
    """
    vault_root = Path(vault_root).resolve()
    target = safe_join(vault_root, folder)

    if not target.exists():
        return {
            "error": f"folder does not exist: {folder}",
            "hint": "use obsidian_scaffold to create it (spec §10)",
        }

    cfg = resolve_config(vault_root, target)
    notes: List[Note] = list(iter_notes(vault_root, scope=target))

    # -- schema: fields, with vocabulary split for type/kind ----------------
    schema: Dict[str, Any] = {"fields": {}}
    for name, definition in cfg.fields.items():
        entry: Dict[str, Any] = {
            "required": bool(definition.get("required")),
        }
        if definition.get("multi"):
            entry["multi"] = True
        if definition.get("format"):
            entry["format"] = definition["format"]

        if definition.get(VOCABULARY_FLAG):
            entry.update(_vocab_compact(
                derive_vocabulary(notes, name, cfg.allowed_values(name))
            ))
            if definition.get("restricted"):
                entry["restricted"] = True
        elif cfg.allowed_values(name):
            entry["allowed"] = cfg.allowed_values(name)

        schema["fields"][name] = entry

    if cfg.status_overrides:
        schema["status_overrides"] = cfg.status_overrides

    payload: Dict[str, Any] = {
        "folder": folder or ".",
        "note_count": len(notes),
        "schema": schema,
        "defaults": cfg.defaults,
        "tags": {
            "mode": cfg.tag_mode(),
            "in_use": [
                f"{t['name']} ({t['count']})" for t in derive_tags(notes)
            ],
        },
        "validation": {
            "fields": cfg.validation_mode("fields"),
            "tags": cfg.validation_mode("tags"),
        },
        "siblings": [n.path for n in notes[:max_siblings]],
        "template": _template(cfg),
        "config_sources": [
            str(p.relative_to(vault_root)) for p in cfg.sources
        ],
        "engine_options": describe(),
    }

    if agent is not None and roles is not None:
        rel = relative_to_vault(vault_root, target)
        payload["grants"] = _grants_row(roles, agent, rel)
    payload["conventions_ref"] = _conventions_ref(cfg, agent, roles)

    if len(notes) > max_siblings:
        payload["siblings_truncated"] = len(notes) - max_siblings

    malformed = [n.path for n in notes if n.error]
    if malformed:
        payload["malformed_notes"] = malformed[:10]

    return payload
