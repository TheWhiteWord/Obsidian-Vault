"""Audit trail — see docs/concepts/model.md.

Append-only JSONL. Every mutation the plugin performs is recorded with who,
what, where, and when.

JSONL rather than a JSON array so an append is one line write with no
read-modify-write cycle: a crashed run cannot corrupt earlier entries, and
concurrent appends interleave safely.

Location comes from ``paths: { state: ... }`` in root config. A vault that
configures no state path simply keeps no audit trail — logging is opt-in, and
the engine must not invent a folder in someone else's vault (principle 7).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import resolve_config
from .paths import safe_join

logger = logging.getLogger(__name__)

AUDIT_FILENAME = "audit-log.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def audit_path(vault_root: Path) -> Optional[Path]:
    """Where the audit log lives, or ``None`` if this vault configures no state dir."""
    cfg = resolve_config(vault_root, vault_root)
    state = cfg.state_path()
    if not state:
        return None
    return safe_join(vault_root, state) / AUDIT_FILENAME


def record(
    vault_root: Path,
    agent: str,
    action: str,
    path: str,
    **details: Any,
) -> None:
    """Append one entry. Never raises — a failed log must not fail a write.

    An audit trail that can break the operation it observes is worse than no
    audit trail: it turns a bookkeeping fault into data loss.
    """
    try:
        log = audit_path(Path(vault_root))
        if log is None:
            return

        entry: Dict[str, Any] = {
            "ts": _now(),
            "agent": agent,
            "action": action,
            "path": path,
        }
        entry.update({k: v for k, v in details.items() if v not in (None, {}, [])})

        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")

    except Exception:
        logger.warning("audit log write failed (operation unaffected)", exc_info=True)


def read_entries(
    vault_root: Path,
    limit: int = 100,
    agent: Optional[str] = None,
    action: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Most recent entries first, optionally filtered."""
    log = audit_path(Path(vault_root))
    if log is None or not log.exists():
        return []

    entries: List[Dict[str, Any]] = []
    for line in reversed(log.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if agent and entry.get("agent") != agent:
            continue
        if action and entry.get("action") != action:
            continue
        entries.append(entry)
        if len(entries) >= limit:
            break

    return entries
