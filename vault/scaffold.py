"""Folder scaffolding — see docs/guides/growth.md.

The mechanism that makes growth cheap. A new folder should cost one
conversation and one command; if it costs more, structure gets created
prematurely or not at all.

Central behaviour: **propose the delta, not the schema.** Most new folders need
no config at all, and saying so plainly is the correct outcome — padding a
proposal to look useful is how vaults accumulate config nobody needs.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import audit
from .config import ConfigError, ResolvedConfig, config_chain, resolve_config
from .constants import CONFIG_DIRNAME, CONFIG_FILENAME, ROLES_FILENAME, VOCABULARY_FLAG
from .generate import write_index
from .grants import RoleRegistry
from .paths import VaultPathError, relative_to_vault, safe_join

logger = logging.getLogger(__name__)


class ScaffoldRefused(Exception):
    """Raised when a scaffold request cannot proceed."""


#: Delta keys that change what validates for future notes, so they need the
#: user's assent rather than the agent's judgement (§10.4).
STRUCTURAL_KEYS = ("fields", "validation")


def _inherited_summary(cfg) -> Dict[str, Any]:
    """What this folder already gets for free."""
    summary: Dict[str, Any] = {
        "required_fields": list(cfg.required_fields),
        "tag_mode": cfg.tag_mode(),
        "validation": {
            "fields": cfg.validation_mode("fields"),
            "tags": cfg.validation_mode("tags"),
        },
        "config_chain": [str(p.parent.parent.name or "root") for p in cfg.sources],
    }
    for name in cfg.vocabulary_fields():
        summary.setdefault("vocabularies", {})[name] = cfg.allowed_values(name)
    return summary


def _delta_against_inherited(proposed: Dict[str, Any], cfg) -> Dict[str, Any]:
    """Strip anything the parent already provides. What remains is the delta."""
    if not proposed:
        return {}

    delta: Dict[str, Any] = {}

    for name, definition in (proposed.get("fields") or {}).items():
        inherited = cfg.fields.get(name, {})
        field_delta: Dict[str, Any] = {}

        for key, value in (definition or {}).items():
            if key in ("allowed", "allowed_only"):
                already = set(cfg.allowed_values(name) or [])
                new_values = [v for v in value if v not in already]
                if key == "allowed_only" or new_values:
                    field_delta[key] = value if key == "allowed_only" else new_values
            elif inherited.get(key) != value:
                field_delta[key] = value

        if field_delta:
            delta.setdefault("fields", {})[name] = field_delta

    for key, value in (proposed.get("defaults") or {}).items():
        if cfg.defaults.get(key) != value:
            delta.setdefault("defaults", {})[key] = value

    for section in ("tags", "validation"):
        for key, value in (proposed.get(section) or {}).items():
            current = getattr(cfg, section, {}).get(key)
            if current != value:
                delta.setdefault(section, {})[key] = value

    # maintenance: only the two authorable modes are ever carried into a
    # delta — ``restricted`` is a derived merge marker (set by ``exempt_only``),
    # never authored, so it is neither proposed nor written. A check key
    # appears in the delta only when its proposed globs differ from the
    # inherited value, so the user sees only real changes (like the other
    # sections above).
    proposed_mnt = proposed.get("maintenance") or {}
    inherited_mnt = cfg.maintenance or {}
    for mode in ("exempt", "exempt_only"):
        proposed_section = proposed_mnt.get(mode) or {}
        inherited_section = inherited_mnt.get(mode) or {}
        section_delta = {}
        for check, globs in proposed_section.items():
            if list(globs) != list(inherited_section.get(check, []) or []):
                section_delta[check] = list(globs)
        if section_delta:
            delta.setdefault("maintenance", {})[mode] = section_delta

    return delta


def _needs_confirmation(delta: Dict[str, Any]) -> bool:
    """§10.4 — structure requires assent; values do not."""
    return any(key in delta for key in STRUCTURAL_KEYS)


def scaffold_folder(
    vault_root: Path,
    agent: str,
    roles: RoleRegistry,
    path: str,
    intent: str = "",
    proposed: Optional[Dict[str, Any]] = None,
    confirm: bool = False,
) -> Dict[str, Any]:
    """Propose or create a folder (§10.2).

    With ``confirm=false`` nothing is written: the return value is a proposal
    to discuss. With ``confirm=true`` the folder is created, a config file is
    written **only if the delta is non-empty**, the parent index is
    regenerated, and the action is logged.
    """
    import yaml

    root = Path(vault_root).resolve()
    target = safe_join(root, path)
    rel = relative_to_vault(root, target)

    if CONFIG_DIRNAME in target.parts:
        raise VaultPathError(f"{CONFIG_DIRNAME}/ is config, not a content folder")
    if target.suffix:
        raise ScaffoldRefused(f"{rel!r} looks like a file; scaffold creates folders")

    # Scaffolding is a write (§10.3) — vault_manager holds no write grant in
    # content trees and therefore cannot create structure.
    roles.check(agent, "create", f"{rel}/.placeholder")

    existed = target.is_dir()
    parent_cfg = resolve_config(root, target.parent if not existed else target)
    delta = _delta_against_inherited(proposed or {}, parent_cfg)
    requires_user = _needs_confirmation(delta)

    if not confirm:
        return {
            "ok": True,
            "proposal": True,
            "folder": rel,
            "exists": existed,
            "intent": intent,
            "inherits": _inherited_summary(parent_cfg),
            "delta": delta,
            "writes_config": bool(delta),
            "requires_user_confirmation": requires_user,
            "note": (
                "No config needed — this folder inherits everything it requires. "
                "Confirm to create it as a plain folder."
                if not delta else
                "Confirm to create the folder and write this config delta."
            ),
        }

    if requires_user and not _user_confirmed(proposed):
        raise ScaffoldRefused(
            f"{rel}: this delta changes what validates for future notes "
            f"({', '.join(k for k in STRUCTURAL_KEYS if k in delta)}); "
            f"it needs explicit user confirmation, not agent judgement"
        )

    target.mkdir(parents=True, exist_ok=True)

    config_written = None
    if delta:
        config_dir = target / CONFIG_DIRNAME
        config_dir.mkdir(exist_ok=True)
        config_file = config_dir / CONFIG_FILENAME
        if config_file.exists():
            raise ScaffoldRefused(f"{rel} already has a config; edit it directly")
        config_file.write_text(
            yaml.safe_dump(delta, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        config_written = relative_to_vault(root, config_file)

    index = None
    try:
        index = write_index(root, rel)
    except FileExistsError as exc:
        logger.warning("index not written: %s", exc)

    audit.record(root, agent, "scaffold", rel,
                 intent=intent, delta=delta, config=config_written)

    return {
        "ok": True,
        "folder": rel,
        "created": not existed,
        "config": config_written,
        "index": index,
        "inherits_only": not delta,
    }


def _user_confirmed(proposed: Optional[Dict[str, Any]]) -> bool:
    """Structural changes carry an explicit acknowledgement flag.

    Separate from ``confirm`` on purpose: ``confirm`` is the agent saying "go",
    this is the agent asserting the *user* approved a structural change. Two
    different claims, so they are two different flags.
    """
    return bool((proposed or {}).get("user_confirmed"))


# --- config editing (P5b) --------------------------------------------------

def _merge_delta_into_raw(raw: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
    """Apply a computed delta to a config file's current raw content.

    Same merge semantics as ``merge_configs``: ``allowed`` unions, an
    ``allowed_only`` replaces the vocabulary, everything else is set. The
    uniformity contract is enforced by re-resolving the chain afterwards, not
    here — this is pure dict surgery with the engine's semantics.
    """
    import copy

    merged = copy.deepcopy(raw)
    for name, defn in (delta.get("fields") or {}).items():
        block = merged.setdefault("fields", {}).setdefault(name, {})
        for key, value in defn.items():
            if key == "allowed":
                existing = list(block.get("allowed", []))
                for item in value:
                    if item not in existing:
                        existing.append(item)
                block["allowed"] = existing
            elif key == "allowed_only":
                block["allowed_only"] = list(value)
                block.pop("allowed", None)  # allowed_only replaces the vocabulary
            else:
                block[key] = value
    for section in ("defaults", "tags", "validation", "vocabulary",
                    "paths"):
        for key, value in (delta.get(section) or {}).items():
            merged.setdefault(section, {})[key] = value

    # maintenance: persist the two authorable modes. ``exempt`` unions with
    # what this file already declares (the delta carries the full proposed
    # glob list for a changed check); ``exempt_only`` replaces — its list IS
    # the exemption set for that check. ``restricted`` is derived at resolve
    # time and is never written.
    for mode, replace in (("exempt", False), ("exempt_only", True)):
        for check, globs in (delta.get("maintenance", {}).get(mode) or {}).items():
            block = merged.setdefault("maintenance", {}).setdefault(mode, {})
            if replace:
                block[check] = list(globs)
            else:
                existing = list(block.get(check, []))
                for g in globs:
                    if g not in existing:
                        existing.append(g)
                block[check] = existing

    if "summary_field" in delta:
        merged["summary_field"] = delta["summary_field"]
    return merged


def _validate_merged_chain(root: Path, target: Path, merged: Dict[str, Any]) -> None:
    """Re-resolve the config chain with ``merged`` in place of ``target``.

    Runs the real loader over the whole chain, so the uniformity contract
    (redefined ``format``/``multi``) raises ``ConfigError`` before anything
    is written — the edit is refused, not applied-then-broken. Dropping an
    inherited ``required`` is legal since P7 (nearest declaration wins).
    """
    import yaml

    from .config import merge_configs

    sources = config_chain(root, target.parent)
    raws = []
    for src in sources:
        if src == target:
            raws.append(merged)
        else:
            raws.append(yaml.safe_load(src.read_text(encoding="utf-8")) or {})
    merge_configs(raws, sources)  # raises ConfigError on contract violation


def edit_config(
    vault_root: Path,
    agent: str,
    roles: RoleRegistry,
    path: str,
    proposed: Optional[Dict[str, Any]] = None,
    confirm: bool = False,
) -> Dict[str, Any]:
    """Edit an existing ``.vault/config.yaml`` (P5b §3.6).

    The config-gated sibling of scaffold: same delta semantics, applied to a
    file that already exists (scaffold refuses those). The ``proposed``
    argument is the desired change; the response shows only what actually
    changes beyond the folder's current effective config. Structural keys
    (``fields``, ``validation``) need explicit user confirmation; vocabulary
    values do not.

    Refusals: ``roles.yaml`` (grants are never edited by tools), non-config
    targets, missing files (scaffold creates those), and any edit that
    breaks the uniformity contract — redefining ``format``/``multi`` is
    refused via the real loader (dropping an inherited ``required`` is legal
    since P7: nearest declaration wins).
    """
    import yaml

    root = Path(vault_root).resolve()
    target = safe_join(root, path)
    rel = relative_to_vault(root, target)

    if target.name == ROLES_FILENAME:
        raise VaultPathError(
            f"{ROLES_FILENAME} is grants policy — never edited by tools")
    if CONFIG_DIRNAME not in target.parts or target.name != CONFIG_FILENAME:
        raise VaultPathError(f"{path!r} is not a {CONFIG_DIRNAME}/"
                             f"{CONFIG_FILENAME} config file")
    if not target.is_file():
        raise ScaffoldRefused(
            f"{rel} does not exist — use obsidian_scaffold to create a new config")

    # Editing an existing config is a `config`-grant operation (P5b D-5: a
    # domain owner holds config on its own tree; root stays manager-only).
    roles.check(agent, "edit_config", rel)

    current_raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    cfg = resolve_config(root, target.parent)
    delta = _delta_against_inherited(proposed or {}, cfg)
    requires_user = _needs_confirmation(delta)

    if not confirm:
        return {
            "ok": True,
            "proposal": True,
            "config": rel,
            "inherits": _inherited_summary(cfg),
            "delta": delta,
            "requires_user_confirmation": requires_user,
            "note": (
                "No change needed — the config already provides this."
                if not delta else
                "Confirm to apply this config delta."
            ),
        }

    if requires_user and not _user_confirmed(proposed):
        raise ScaffoldRefused(
            f"{rel}: this delta changes what validates for future notes "
            f"({', '.join(k for k in STRUCTURAL_KEYS if k in delta)}); "
            f"it needs explicit user confirmation, not agent judgement"
        )

    if not delta:
        return {"ok": True, "config": rel, "changed": False}

    merged = _merge_delta_into_raw(current_raw, delta)
    try:
        _validate_merged_chain(root, target, merged)  # ConfigError → refusal
    except ConfigError as exc:
        raise ScaffoldRefused(
            f"{rel}: refused — the edit breaks the uniformity contract: {exc}"
        ) from exc

    target.write_text(
        yaml.safe_dump(merged, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    audit.record(root, agent, "edit_config", rel, delta=delta)

    return {
        "ok": True,
        "config": rel,
        "changed": True,
        "delta": delta,
    }
