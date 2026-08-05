"""Frontmatter validation — spec §3, §3.5, §3.7.

Separate from grants on purpose: *may this agent write here* and *is this note
well-formed* are independent questions, and conflating them makes both harder
to test.

Two severities, per config:
  blocking  — the write is refused
  advisory  — the write proceeds, warnings returned
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field as dc_field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .config import ResolvedConfig
from .constants import TODAY_TOKEN, VOCABULARY_FLAG

logger = logging.getLogger(__name__)

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Issue:
    field: str
    message: str
    severity: str                      # "blocking" | "advisory"
    suggestion: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {"field": self.field, "message": self.message}
        if self.suggestion:
            d["did_you_mean"] = self.suggestion
        return d


@dataclass
class ValidationResult:
    errors: List[Issue] = dc_field(default_factory=list)
    warnings: List[Issue] = dc_field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if self.errors:
            out["errors"] = [e.to_dict() for e in self.errors]
        if self.warnings:
            out["warnings"] = [w.to_dict() for w in self.warnings]
        return out


def _similar(value: str, candidates: List[str], limit: int = 3) -> List[str]:
    """Nearest known values, for a useful error rather than a bare refusal."""
    import difflib
    return difflib.get_close_matches(str(value), candidates, n=limit, cutoff=0.6)


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _allowed_for(
    cfg: ResolvedConfig,
    field_name: str,
    frontmatter: Dict[str, Any],
) -> Optional[List[str]]:
    """Allowed values for a field, honouring per-class overrides (§3.5).

    Which field is overridden, and which field keys the override, are both
    config (principle 7):

        value_overrides:
          field: status        # the field whose allowed values change
          by: kind             # the field whose value selects the override
          map:
            issue: [open, in-progress, resolved]
    """
    allowed = cfg.allowed_values(field_name)

    overrides = cfg.value_overrides()
    if not overrides or overrides.get("field") != field_name:
        return allowed

    mapping = overrides.get("map") or {}
    keyed_by = overrides.get("by")
    key_fields = [keyed_by] if keyed_by else cfg.vocabulary_fields()

    for key_field in key_fields:
        for value in _as_list(frontmatter.get(key_field)):
            override = mapping.get(str(value))
            if override:
                return [str(v) for v in override]

    return allowed


def validate_frontmatter(
    frontmatter: Dict[str, Any],
    cfg: ResolvedConfig,
    known_tags: Optional[List[str]] = None,
) -> ValidationResult:
    """Validate a note's frontmatter against its folder's resolved config."""
    result = ValidationResult()
    field_severity = cfg.validation_mode("fields")
    tag_severity = cfg.validation_mode("tags")

    def report(issue: Issue) -> None:
        bucket = result.errors if issue.severity == "blocking" else result.warnings
        bucket.append(issue)

    # -- required fields ----------------------------------------------------
    for name in cfg.required_fields:
        value = frontmatter.get(name)
        empty = value is None or (isinstance(value, (str, list, dict)) and not value)
        if empty:
            report(Issue(name, f"required field '{name}' is missing", field_severity))

    # -- per-field checks ---------------------------------------------------
    for name, definition in cfg.fields.items():
        if name not in frontmatter or frontmatter[name] is None:
            continue

        raw = frontmatter[name]
        values = _as_list(raw)

        if values and not definition.get("multi") and isinstance(raw, (list, tuple)):
            report(Issue(
                name,
                f"'{name}' accepts a single value, got a list",
                field_severity,
            ))

        if definition.get("format") == "date":
            for value in values:
                if not _is_date(value):
                    report(Issue(
                        name,
                        f"'{name}' must be an ISO date (YYYY-MM-DD), got {value!r}",
                        field_severity,
                    ))

        allowed = _allowed_for(cfg, name, frontmatter)
        if not allowed:
            continue

        for value in values:
            text = str(value)
            if text in allowed:
                continue

            if definition.get(VOCABULARY_FLAG) and not definition.get("restricted"):
                # §3.7: an unregistered vocabulary value is *observed*, not an
                # error. Reuse is encouraged by showing what exists, and
                # registration is an explicit opt-in — never a silent accident.
                report(Issue(
                    name,
                    f"'{text}' is not a registered {name}; it will be recorded as "
                    f"observed. Reuse an existing value, or pass "
                    f"register_{name}='{text}' to register it.",
                    "advisory",
                    suggestion=_similar(text, allowed),
                ))
            else:
                report(Issue(
                    name,
                    f"'{text}' is not permitted for '{name}'",
                    field_severity,
                    suggestion=_similar(text, allowed),
                ))

    # -- tags (§4) ----------------------------------------------------------
    mode = cfg.tag_mode()
    if mode != "open" and known_tags is not None:
        for tag in _as_list(frontmatter.get("tags")):
            text = str(tag).lstrip("#")
            if text in known_tags:
                continue
            severity = "blocking" if mode == "closed" else tag_severity
            report(Issue(
                "tags",
                f"tag '{text}' is new to this scope",
                severity,
                suggestion=_similar(text, known_tags),
            ))

    return result


def _is_date(value: Any) -> bool:
    if isinstance(value, (date, datetime)):
        return True
    text = str(value).strip()
    if not ISO_DATE_RE.match(text):
        return False
    try:
        datetime.strptime(text, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def apply_defaults(
    frontmatter: Dict[str, Any],
    cfg: ResolvedConfig,
) -> Dict[str, Any]:
    """Fill absent fields from config defaults. Never overwrites."""
    filled = dict(frontmatter)
    for name, value in cfg.defaults.items():
        if filled.get(name) not in (None, "", [], {}):
            continue
        filled[name] = date.today().isoformat() if value == TODAY_TOKEN else value
    return filled
