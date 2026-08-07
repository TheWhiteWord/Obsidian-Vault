"""Write operations — see docs/concepts/grants.md and docs/concepts/model.md.

Every mutation passes through here, and every mutation is checked in the same
order:

    1. resolve path (refuse escapes)      paths.safe_join
    2. check grant  (deny by default)     grants.RoleRegistry.check
    3. validate     (blocking vs advisory) validate.validate_frontmatter
    4. write

No path skips a step. A caller that wants to bypass validation may not; a
caller that wants to bypass permission may not. That is the boundary.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import ResolvedConfig, resolve_config
from .constants import CONFIG_DIRNAME, MARKDOWN_SUFFIX, STATE_DIRNAME, VOCABULARY_FLAG
from .grants import PermissionDenied, RoleRegistry
from .notes import Note, derive_tags, iter_notes, parse_note
from .paths import VaultPathError, relative_to_vault, safe_join
from .validate import ValidationResult, apply_defaults, validate_frontmatter
from . import audit

logger = logging.getLogger(__name__)


def _refresh_index(vault_root: Path, folder: Path) -> None:
    """Regenerate the containing folder's INDEX after a mutation (§6).

    Never raises: a note was written successfully, and a failure to regenerate
    a derived view must not be reported as a failed write. The next
    regeneration repairs it.

    Skips engine-reserved folders (`.vault`, `.state`): they are machinery,
    not content, and must never carry a content-derived INDEX of themselves.
    """
    try:
        if CONFIG_DIRNAME in folder.parts or STATE_DIRNAME in folder.parts:
            return
        from .generate import write_index
        write_index(vault_root, relative_to_vault(vault_root, folder))
    except Exception:
        logger.warning("index regeneration failed", exc_info=True)


class WriteRefused(Exception):
    """Raised when a write fails validation. Carries the structured result."""

    def __init__(self, message: str, result: ValidationResult):
        super().__init__(message)
        self.result = result


@dataclass
class WriteOutcome:
    path: str
    created: bool
    warnings: List[Dict[str, Any]]
    registered: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "ok": True,
            "path": self.path,
            "action": "created" if self.created else "updated",
        }
        if self.warnings:
            out["warnings"] = self.warnings
        if self.registered:
            out["registered"] = self.registered
        return out


def _dump_note(frontmatter: Dict[str, Any], body: str) -> str:
    """Serialise via python-frontmatter so round-tripping stays lossless."""
    import frontmatter as fm

    post = fm.Post(body or "", **frontmatter)
    return fm.dumps(post) + "\n"


def _replace_frontmatter_only(raw: str, frontmatter: Dict[str, Any]) -> str:
    """Swap a note's frontmatter block, leaving the body bytes untouched.

    ``frontmatter.dumps`` normalises whitespace around the delimiter, which
    would silently rewrite the body. The `meta` grant promises prose is never
    altered (§2.2) — that promise has to hold at byte level, so the body is
    spliced back verbatim rather than re-serialised.
    """
    import yaml

    block = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)

    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            body_start = raw.find("\n", end + 1)
            body = raw[body_start + 1:] if body_start != -1 else ""
            return f"---\n{block}---\n{body}"

    return f"---\n{block}---\n{raw}"


def _known_tags(vault_root: Path, folder: Path) -> List[str]:
    return [t["name"] for t in derive_tags(iter_notes(vault_root, scope=folder))]


def write_note(
    vault_root: Path,
    agent: str,
    roles: RoleRegistry,
    path: str,
    frontmatter: Dict[str, Any],
    body: str = "",
    *,
    register: Optional[Dict[str, str]] = None,
    overwrite: bool = False,
) -> WriteOutcome:
    """Create or update a note, enforcing grants then schema.

    ``register`` opts a new vocabulary value into the declared set (§3.7) —
    ``{"kind": "aphorism"}``. Deliberately explicit: an agent must *choose* to
    extend the vocabulary, which is the whole difference between a controlled
    vocabulary and a pile of strings.
    """
    root = Path(vault_root).resolve()
    target = safe_join(root, path)

    if CONFIG_DIRNAME in target.parts:
        raise VaultPathError(f"{CONFIG_DIRNAME}/ is config, not content: {path!r}")
    if target.suffix != MARKDOWN_SUFFIX:
        raise VaultPathError(f"not a markdown note: {path!r}")

    rel = relative_to_vault(root, target)
    exists = target.exists()

    # 1. permission -- create and edit are different grants (§2.1)
    roles.check(agent, "edit" if exists else "create", rel)
    if exists and not overwrite:
        raise WriteRefused(
            f"{rel} already exists; pass overwrite=true to replace it",
            ValidationResult(),
        )

    cfg = resolve_config(root, target.parent)

    # 2. registration -- extend the declared vocabulary before validating,
    #    so a registered value does not also report as observed.
    registered: Dict[str, str] = {}
    for field_name, value in (register or {}).items():
        _register_value(root, target.parent, cfg, agent, roles, field_name, value)
        registered[field_name] = value
    if registered:
        cfg = resolve_config(root, target.parent)

    # 3. validation
    filled = apply_defaults(frontmatter, cfg)
    result = validate_frontmatter(filled, cfg, _known_tags(root, target.parent))

    if not result.ok:
        raise WriteRefused(
            f"{rel} does not conform to the schema for {cfg.folder.name}/",
            result,
        )

    # 4. write
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_dump_note(filled, body), encoding="utf-8")

    audit.record(root, agent, "create" if not exists else "edit", rel,
                 registered=registered or None,
                 warnings=len(result.warnings) or None)
    _refresh_index(root, target.parent)

    return WriteOutcome(
        path=rel,
        created=not exists,
        warnings=[w.to_dict() for w in result.warnings],
        registered=registered,
    )


def _register_value(
    vault_root: Path,
    folder: Path,
    cfg: ResolvedConfig,
    agent: str,
    roles: RoleRegistry,
    field_name: str,
    value: str,
) -> None:
    """Add a value to the nearest config declaring ``field_name`` (§3.7)."""
    import yaml

    definition = cfg.fields.get(field_name)
    if not definition:
        raise WriteRefused(
            f"cannot register '{value}': no field '{field_name}' in this schema",
            ValidationResult(),
        )
    if not definition.get(VOCABULARY_FLAG):
        raise WriteRefused(
            f"field '{field_name}' does not carry a vocabulary; "
            f"registration does not apply",
            ValidationResult(),
        )
    if definition.get("restricted"):
        raise WriteRefused(
            f"field '{field_name}' is restricted here and cannot be extended",
            ValidationResult(),
        )

    # Write to the nearest ancestor config that declares this field, so a
    # creative kind lands in the creative tree rather than the root.
    config_path = _nearest_declaring_config(vault_root, folder, field_name)
    rel_config = relative_to_vault(vault_root, config_path)
    roles.check(agent, "edit_config", rel_config)

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    field_block = raw.setdefault("fields", {}).setdefault(field_name, {})
    key = "allowed_only" if "allowed_only" in field_block else "allowed"
    values = list(field_block.get(key) or [])

    if value not in values:
        values.append(value)
        field_block[key] = values
        config_path.write_text(
            yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        logger.info("registered %s=%s in %s", field_name, value, rel_config)


def _nearest_declaring_config(
    vault_root: Path, folder: Path, field_name: str
) -> Path:
    import yaml

    root = Path(vault_root).resolve()
    cursor = Path(folder).resolve()
    fallback = root / CONFIG_DIRNAME / "config.yaml"

    while True:
        candidate = cursor / CONFIG_DIRNAME / "config.yaml"
        if candidate.exists():
            raw = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
            if field_name in (raw.get("fields") or {}):
                return candidate
        if cursor == root:
            return fallback
        cursor = cursor.parent


def edit_metadata(
    vault_root: Path,
    agent: str,
    roles: RoleRegistry,
    path: str,
    changes: Dict[str, Any],
) -> WriteOutcome:
    """Update frontmatter only — body prose is left byte-identical (§2.2).

    This is the `meta` grant made real. The vault manager can repair links,
    normalise tags, and fix frontmatter across the whole vault while being
    *structurally incapable* of altering a word of what anyone wrote.
    """
    root = Path(vault_root).resolve()
    target = safe_join(root, path)
    rel = relative_to_vault(root, target)

    if not target.exists():
        raise WriteRefused(f"{rel} does not exist", ValidationResult())

    roles.check(agent, "edit_meta", rel)

    raw = target.read_text(encoding="utf-8")
    note = parse_note(target, root)
    if note.error:
        raise WriteRefused(f"{rel}: {note.error}", ValidationResult())

    updated = {**note.frontmatter, **changes}
    for key, value in changes.items():
        if value is None:
            updated.pop(key, None)

    cfg = resolve_config(root, target.parent)
    result = validate_frontmatter(updated, cfg, _known_tags(root, target.parent))
    if not result.ok:
        raise WriteRefused(f"{rel}: metadata change fails validation", result)

    target.write_text(_replace_frontmatter_only(raw, updated), encoding="utf-8")

    audit.record(root, agent, "edit_meta", rel, changes=sorted(changes))
    _refresh_index(root, target.parent)

    return WriteOutcome(
        path=rel,
        created=False,
        warnings=[w.to_dict() for w in result.warnings],
        registered={},
    )


def delete_note(
    vault_root: Path,
    agent: str,
    roles: RoleRegistry,
    path: str,
) -> Dict[str, Any]:
    """Delete a note. Requires `write` — `append` explicitly does not suffice."""
    root = Path(vault_root).resolve()
    target = safe_join(root, path)
    rel = relative_to_vault(root, target)

    roles.check(agent, "delete", rel)

    if not target.exists():
        return {"ok": False, "error": f"{rel} does not exist"}

    folder = target.parent
    target.unlink()

    audit.record(root, agent, "delete", rel)
    _refresh_index(root, folder)

    return {"ok": True, "path": rel, "action": "deleted"}
