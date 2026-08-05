"""Config loading and inheritance resolution.

Implements spec 01-vault-v2-model.md §3.3.

A ``.vault/config.yaml`` may sit at any depth. The effective config for a
folder is the merge of every config from the vault root down to that folder,
applying per-key merge semantics:

===========================  ==========================================
Key                          Behaviour
===========================  ==========================================
``fields.*.allowed``         union — child extends parent vocabulary
``fields.*.allowed_only``    replace — child restricts (explicit opt-in)
``defaults``                 child overrides key-by-key
``fields.*.required``        union — child may add, never drop
``tags.mode``                child overrides wholly
===========================  ==========================================

The uniformity contract (§3.2) is enforced here: a child may constrain or
extend the *values* of a field, but may never rename one, remove one, or
change its meaning or format. Violations raise ``ConfigError`` at load time
rather than surfacing as a confusing validation failure later.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import (
    CONFIG_DIRNAME,
    CONFIG_FILENAME,
    DEFAULT_FIELD_VALIDATION,
    DEFAULT_TAG_MODE,
    DEFAULT_TAG_VALIDATION,
    IMMUTABLE_FIELD_KEYS,
    STATE_DIRNAME,
    STATE_PATH_KEY,
    VOCABULARY_FLAG,
)
from .paths import VaultPathError

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when a config file is malformed or breaks the uniformity contract."""


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml
    except ImportError:  # pragma: no cover
        raise ConfigError("PyYAML is required to load vault configs")

    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception as exc:
        raise ConfigError(f"{path}: could not parse YAML — {exc}") from exc

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping, got {type(data).__name__}")
    return data


def config_chain(vault_root: Path, target: Path) -> List[Path]:
    """Return every existing config file from vault root down to ``target``.

    Ordered root-first, so a later entry overrides an earlier one.
    """
    vault_root = vault_root.resolve()
    target = target.resolve()

    try:
        rel = target.relative_to(vault_root)
    except ValueError:
        raise VaultPathError(f"{target} is not inside vault {vault_root}")

    chain: List[Path] = []
    cursor = vault_root
    candidates = [cursor] + [cursor := cursor / part for part in rel.parts]

    for folder in candidates:
        cfg = folder / CONFIG_DIRNAME / CONFIG_FILENAME
        if cfg.is_file():
            chain.append(cfg)
    return chain


def _merge_field(
    name: str,
    parent: Dict[str, Any],
    child: Dict[str, Any],
    source: Path,
) -> Dict[str, Any]:
    """Merge one field definition. See module docstring for semantics."""
    merged = dict(parent)

    # -- uniformity contract: structural keys are immutable once set --------
    for key in IMMUTABLE_FIELD_KEYS:
        if key in child and key in parent and child[key] != parent[key]:
            raise ConfigError(
                f"{source}: field '{name}' may not redefine '{key}' "
                f"({parent[key]!r} -> {child[key]!r}). Children may constrain "
                f"or extend allowed values, never change the field itself."
            )

    for key, value in child.items():
        if key == "allowed":
            # union, order-preserving, deduplicated
            existing = list(merged.get("allowed", []))
            for item in value:
                if item not in existing:
                    existing.append(item)
            merged["allowed"] = existing
        elif key == "allowed_only":
            # explicit restriction — replaces the inherited vocabulary
            merged["allowed"] = list(value)
            merged["restricted"] = True
        elif key == "required":
            # union semantics: a child may add a requirement, never drop one
            if parent.get("required") and not value:
                raise ConfigError(
                    f"{source}: field '{name}' cannot drop an inherited "
                    f"'required: true'. Requirements only accumulate."
                )
            merged["required"] = bool(value) or bool(parent.get("required"))
        else:
            merged[key] = value

    return merged


def merge_configs(configs: List[Dict[str, Any]], sources: List[Path]) -> Dict[str, Any]:
    """Merge an ordered root-first list of raw configs into one resolved config."""
    resolved: Dict[str, Any] = {"fields": {}, "defaults": {}, "tags": {}, "validation": {}}

    for raw, source in zip(configs, sources):
        for field_name, child_def in (raw.get("fields") or {}).items():
            if not isinstance(child_def, dict):
                raise ConfigError(
                    f"{source}: fields.{field_name} must be a mapping"
                )
            parent_def = resolved["fields"].get(field_name, {})
            resolved["fields"][field_name] = _merge_field(
                field_name, parent_def, child_def, source
            )

        # defaults: key-by-key override
        resolved["defaults"].update(raw.get("defaults") or {})

        # tags / validation: shallow override
        resolved["tags"].update(raw.get("tags") or {})
        resolved["validation"].update(raw.get("validation") or {})

        # shallow-override dict sections
        for key in ("status_overrides", "value_overrides", "vocabulary",
                    "scopes", "paths"):
            if key in raw:
                resolved.setdefault(key, {}).update(raw[key] or {})

        # scalar overrides — last declaration wins (root first, so a child can
        # redefine which field is the summary field for its subtree)
        if "summary_field" in raw:
            resolved["summary_field"] = raw["summary_field"]

    return resolved


@dataclass
class ResolvedConfig:
    """The effective config for one folder, plus provenance."""

    folder: Path
    vault_root: Path
    fields: Dict[str, Any] = dc_field(default_factory=dict)
    defaults: Dict[str, Any] = dc_field(default_factory=dict)
    tags: Dict[str, Any] = dc_field(default_factory=dict)
    validation: Dict[str, Any] = dc_field(default_factory=dict)
    status_overrides: Dict[str, Any] = dc_field(default_factory=dict)
    value_overrides_raw: Dict[str, Any] = dc_field(default_factory=dict)
    vocabulary: Dict[str, Any] = dc_field(default_factory=dict)
    scopes: Dict[str, Any] = dc_field(default_factory=dict)
    paths: Dict[str, Any] = dc_field(default_factory=dict)
    summary_field: Optional[str] = None
    sources: List[Path] = dc_field(default_factory=list)

    @property
    def required_fields(self) -> List[str]:
        return [n for n, d in self.fields.items() if d.get("required")]

    def allowed_values(self, field_name: str) -> Optional[List[str]]:
        """Declared vocabulary for a field, or None when unconstrained."""
        return self.fields.get(field_name, {}).get("allowed")

    def tag_mode(self) -> str:
        return self.tags.get("mode", DEFAULT_TAG_MODE)

    def validation_mode(self, what: str) -> str:
        default = (
            DEFAULT_FIELD_VALIDATION if what == "fields" else DEFAULT_TAG_VALIDATION
        )
        return self.validation.get(what, default)

    def vocabulary_fields(self) -> List[str]:
        """Fields flagged ``vocabulary: true`` — declared/observed applies (§3.7).

        Which fields these are is the user's choice, not the engine's.
        """
        return [
            name for name, definition in self.fields.items()
            if definition.get(VOCABULARY_FLAG)
        ]

    def state_path(self) -> Optional[str]:
        """Vault-relative folder for machine-written state.

        Defaults to ``STATE`` at the vault root. The audit trail (and, later,
        the manager pass) depend on it, so a vault using this plugin always has
        one — no manual config required. A vault may relocate it via
        ``paths: { state: SOME/FOLDER }`` in root config, but it cannot disable
        the trail by omission (Principle: the engine must not silently lose the
        bookkeeping the maintenance agent needs).
        """
        value = self.paths.get(STATE_PATH_KEY)
        if value:
            return str(value).strip("/")
        return STATE_DIRNAME

    def value_overrides(self) -> Dict[str, Any]:
        """Per-class allowed-value overrides (§3.5), normalised.

        Accepts the shorthand ``status_overrides: {issue: [...]}`` and expands
        it to the general form. The shorthand is convenient; the general form
        is what keeps the engine free of field names (principle 7).
        """
        if self.value_overrides_raw:
            return self.value_overrides_raw
        if self.status_overrides:
            return {"field": "status", "by": None, "map": self.status_overrides}
        return {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "folder": str(self.folder),
            "fields": self.fields,
            "defaults": self.defaults,
            "tags": self.tags,
            "validation": self.validation,
            "status_overrides": self.status_overrides,
            "vocabulary": self.vocabulary,
            "scopes": self.scopes,
            "sources": [str(p) for p in self.sources],
        }


def resolve_config(vault_root: Path, target: Path) -> ResolvedConfig:
    """Resolve the effective config for ``target`` within ``vault_root``."""
    sources = config_chain(vault_root, target)
    raws = [_load_yaml(p) for p in sources]
    merged = merge_configs(raws, sources)

    return ResolvedConfig(
        folder=Path(target).resolve(),
        vault_root=Path(vault_root).resolve(),
        fields=merged.get("fields", {}),
        defaults=merged.get("defaults", {}),
        tags=merged.get("tags", {}),
        validation=merged.get("validation", {}),
        status_overrides=merged.get("status_overrides", {}),
        value_overrides_raw=merged.get("value_overrides", {}),
        vocabulary=merged.get("vocabulary", {}),
        scopes=merged.get("scopes", {}),
        paths=merged.get("paths", {}),
        summary_field=merged.get("summary_field"),
        sources=sources,
    )
