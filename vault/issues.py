"""Issue ledger — see docs/guides/maintenance.md.

Issues are *structured records with a lifecycle*, not notes. One small JSON
file per issue under the state dir: ``<state>/issues/<slug>.json``. Current
state only; every mutation is recorded in the audit trail (``issue_create``,
``issue_resolve``, ``issue_prune``) with ``path`` = the issue's target, so
provenance is preserved without a second log.

The ledger is engine machinery, like the audit trail: it lives under the
state dir (in ``SKIP_DIRS``), so ``iter_notes`` / ``build_graph`` /
``generate`` / ``search`` never see it. Zero content pollution, by
construction. Access is at call time, derived from grants — the tool layer
enforces who may raise / see / resolve, against the issue's ``target``.

Record shape (engine-fixed, layout-independent):

    {
      "key": "dangling|work/creative/projects/a.md",
      "state": "open",               # open | in_progress | resolved | declined
      "nature": "finding",           # finding (correctness) | suggestion (optimization)
      "priority": "medium",          # low | medium | high | critical
      "subject": "[dangling] work/creative/projects/a.md",
      "detail": "Links to [[Missing Note]]",
      "target": "work/creative/projects/a.md",   # path or scope glob ("system/**")
      "tags": ["maintenance"],
      "raised_by": "vault-manager",
      "assignee": null,              # who SHOULD resolve (profile name; SHOULD signal, never a CAN gate)
      "claimed_by": null,            # who moved open -> in_progress (the holder)
      "created_at": "...", "updated_at": "...",
      "resolved_by": null, "resolved_at": null, "reason": null
    }

The **key is the dedupe unit**: deterministic (``type|path`` for manager
findings), and the filename is derived from it. An open record with the same
key is skipped (dedupe); a resolved one is re-opened (re-escalation).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import resolve_config
from .constants import ISSUES_DIRNAME
from .paths import safe_join
from . import audit

logger = logging.getLogger(__name__)

#: Lifecycle states — engine-fixed, universal.
ISSUE_STATES = ("open", "in_progress", "resolved", "declined")
#: Distinguishes correctness findings (B1) from quality suggestions (B2);
#: the auto-close policy treats them differently.
ISSUE_NATURES = ("finding", "suggestion")
#: Priorities — engine-fixed.
ISSUE_PRIORITIES = ("low", "medium", "high", "critical")

#: Pruning TTL for closed records (engine constant; a future config knob).
PRUNE_TTL_DAYS = 30

#: Issue-operation outcome keys. Engine vocabulary — used by callers to
#: branch on what a mutation did (the portability guard forbids the literal
#: field-name words in engine logic, so they live here as constants).
RESULT_CREATED = "created"
RESULT_EXISTS = "exists"
RESULT_REOPENED = "reopened"
RESULT_NOT_FOUND = "not_found"
RESULT_ALREADY_CLOSED = "already_closed"
RESULT_CLOSED = "closed"


class IssueError(Exception):
    """Raised for invalid issue inputs (unknown state/nature/priority)."""


def _now() -> str:
    # Microsecond precision so same-second creates still order correctly.
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def issues_dir(vault_root: Path) -> Optional[Path]:
    """The ledger folder (``<state>/issues``), or ``None`` if no state dir.

    Mirrors ``audit.audit_path``: the state dir defaults to root ``.state/``
    (``ResolvedConfig.state_path`` never returns empty), but the guard stays.
    """
    cfg = resolve_config(Path(vault_root), Path(vault_root))
    state = cfg.state_path()
    if not state:
        return None
    return safe_join(Path(vault_root), state) / ISSUES_DIRNAME


def _slug(key: str) -> str:
    """Filename-safe slug of the issue key, with a short hash for uniqueness.

    Same key → same filename (deterministic dedupe). The hash disambiguates
    two keys whose slugs collide; the full key is stored inside the record.
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", key).strip("_").lower()[:80] or "issue"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}.json"


def _issue_path(vault_root: Path, key: str) -> Optional[Path]:
    d = issues_dir(vault_root)
    if d is None:
        return None
    return d / _slug(key)


def _atomic_write(path: Path, record: Dict[str, Any]) -> None:
    """Write via temp + rename so a crash never corrupts an open record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _read(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def read_issue(vault_root: Path, key: str) -> Optional[Dict[str, Any]]:
    """Current state of one issue, or ``None`` if it does not exist."""
    path = _issue_path(vault_root, key)
    if path is None or not path.exists():
        return None
    return _read(path)


def create_issue(
    vault_root: Path,
    agent: str,
    *,
    key: str,
    subject: str,
    detail: str,
    target: str,
    nature: str = "finding",
    priority: str = "medium",
    tags: Optional[List[str]] = None,
    assignee: Optional[str] = None,
) -> Dict[str, Any]:
    """Open an issue — or skip / re-open an existing one with the same key.

    Dedupe and re-escalation are the same mechanism: if a
    record with this key is ``open``/``in_progress``, return ``exists``; if
    it is ``resolved``/``declined``, re-open it (history stays attached);
    otherwise create it. Every mutation is audited with ``path`` = target.
    """
    if nature not in ISSUE_NATURES:
        raise IssueError(f"unknown nature {nature!r}; valid: {list(ISSUE_NATURES)}")
    if priority not in ISSUE_PRIORITIES:
        raise IssueError(f"unknown priority {priority!r}; valid: {list(ISSUE_PRIORITIES)}")
    if assignee is not None and (not isinstance(assignee, str) or not assignee.strip()):
        raise IssueError(f"assignee must be a non-empty profile name, got {assignee!r}")
    clean_assignee = assignee.strip() if assignee else None

    root = Path(vault_root).resolve()
    path = _issue_path(root, key)
    if path is None:
        return {"result": "no_state_dir", "key": key}

    now = _now()
    clean_tags = sorted({t.lstrip("#") for t in (tags or [])})

    existing = _read(path) if path.exists() else None
    if existing and existing.get("state") in ("open", "in_progress"):
        return {"result": "exists", "key": key, "state": existing["state"]}

    if existing:
        # Re-escalation: re-open the same key, keep the original created_at
        # and raiser, keep assignee/claimed_by, clear closure fields.
        record = {**existing, "state": "open", "updated_at": now,
                  "resolved_by": None, "resolved_at": None, "reason": None}
        if clean_assignee:
            record["assignee"] = clean_assignee
        _atomic_write(path, record)
        audit.record(root, agent, "issue_reopen", record.get("target") or target,
                     key=key, nature=nature)
        return {"result": "reopened", "key": key}

    record: Dict[str, Any] = {
        "key": key,
        "state": "open",
        "nature": nature,
        "priority": priority,
        "subject": subject,
        "detail": detail,
        "target": target,
        "tags": clean_tags,
        "raised_by": agent,
        "assignee": clean_assignee,
        "claimed_by": None,
        "created_at": now,
        "updated_at": now,
        "resolved_by": None,
        "resolved_at": None,
        "reason": None,
    }
    _atomic_write(path, record)
    audit.record(root, agent, "issue_create", target,
                 key=key, nature=nature, priority=priority)
    return {"result": "created", "key": key, "path": _rel(root, path)}


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def resolve_issue(
    vault_root: Path,
    agent: str,
    key: str,
    *,
    state: str = "resolved",
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Move an issue: claim (``in_progress``) or close (``resolved``/``declined``).

    Grant enforcement (``write``/``meta`` over the target) happens in the
    tool layer; this is the record mutation + audit. ``in_progress`` records
    the claiming agent in ``claimed_by``; closure keeps ``claimed_by`` (the
    holder) and sets ``resolved_by``/``resolved_at``.
    """
    if state not in ("in_progress", "resolved", "declined"):
        raise IssueError(f"state must be in_progress, resolved, or declined, got {state!r}")

    root = Path(vault_root).resolve()
    path = _issue_path(root, key)
    if path is None:
        return {"result": "no_state_dir", "key": key}
    if not path.exists():
        return {"result": "not_found", "key": key}

    record = _read(path)
    if record is None:
        return {"result": "not_found", "key": key}
    if record["state"] in ("resolved", "declined"):
        return {"result": "already_closed", "key": key, "state": record["state"]}

    now = _now()
    if state == "in_progress":
        record.update(state="in_progress", updated_at=now, claimed_by=agent)
    else:
        record.update(
            state=state, updated_at=now,
            resolved_by=agent, resolved_at=now, reason=reason,
        )
    _atomic_write(path, record)
    if state == "in_progress":
        audit.record(root, agent, "issue_claim", record["target"],
                     key=key, state=state)
        return {"result": "claimed", "key": key, "state": state}
    audit.record(root, agent, "issue_resolve", record["target"],
                 key=key, state=state, reason=reason)
    return {"result": "closed", "key": key, "state": state}


def list_issues(
    vault_root: Path,
    *,
    state: Optional[str] = None,
    nature: Optional[str] = None,
    priority: Optional[str] = None,
    tags: Optional[List[str]] = None,
    target: Optional[str] = None,
    raised_by: Optional[str] = None,
    assigned_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Current state of every issue matching the filters, newest first.

    No grant filtering here — that is the tool layer's job (intersect with
    the caller's read grants on each record's ``target``).
    """
    d = issues_dir(vault_root)
    if d is None or not d.exists():
        return []

    wanted_tags = {t.lstrip("#") for t in (tags or [])}
    out: List[Dict[str, Any]] = []
    for path in sorted(d.glob("*.json")):
        if path.name.endswith(".tmp"):
            continue
        rec = _read(path)
        if rec is None:
            continue
        if state and rec.get("state") != state:
            continue
        if nature and rec.get("nature") != nature:
            continue
        if priority and rec.get("priority") != priority:
            continue
        if wanted_tags and not wanted_tags <= set(rec.get("tags") or []):
            continue
        if target and not _target_matches(target, rec.get("target", "")):
            continue
        if raised_by and rec.get("raised_by") != raised_by:
            continue
        if assigned_to and rec.get("assignee") != assigned_to:
            continue
        out.append(rec)

    out.sort(key=lambda r: (r.get("created_at", ""), r.get("key", "")),
             reverse=True)
    return out


def _target_matches(pattern: str, target: str) -> bool:
    """Does ``target`` (path or glob) fall under ``pattern``?

    ``system/**`` matches both a concrete path ``system/handbook/x.md`` and
    the glob ``system/**`` itself — a vault-wide issue is findable by the
    same filter an agent would use for its own scope.
    """
    from .grants import path_matches
    return path_matches(pattern, target) or path_matches(pattern, target + "/x.md")


def prune_issues(
    vault_root: Path,
    agent: str,
    *,
    ttl_days: int = PRUNE_TTL_DAYS,
) -> List[str]:
    """Delete closed records older than the TTL. Returns pruned keys.

    The audit trail keeps the full history, so deleting the current-state
    file loses nothing.
    """
    d = issues_dir(vault_root)
    if d is None or not d.exists():
        return []

    cutoff = datetime.now(timezone.utc).timestamp() - ttl_days * 86400
    pruned: List[str] = []
    for path in sorted(d.glob("*.json")):
        if path.name.endswith(".tmp"):
            continue
        rec = _read(path)
        if rec is None:
            continue
        if rec.get("state") not in ("resolved", "declined"):
            continue
        closed_at = rec.get("resolved_at") or rec.get("updated_at") or ""
        try:
            closed_ts = datetime.fromisoformat(closed_at).timestamp()
        except ValueError:
            continue
        if closed_ts >= cutoff:
            continue
        key = rec.get("key", path.stem)
        path.unlink()
        audit.record(root := Path(vault_root).resolve(), agent, "issue_prune",
                     rec.get("target", ""), key=key)
        pruned.append(key)
    return pruned
