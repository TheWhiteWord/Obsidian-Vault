"""Protocol registry — see docs/guides/inter-agent.md.

Handoffs are *structured records with parties*, not notes. One small YAML
file per handoff under the state dir: ``<state>/protocols/<slug>.yaml``.
Current state only; every mutation is recorded in the audit trail
(``protocol_register``, ``protocol_update``) with ``path`` = the record's
name, so provenance is preserved without a second log.

The registry is engine machinery, like the issue ledger: it lives under the
state dir (in ``SKIP_DIRS``), so ``iter_notes`` / ``build_graph`` /
``generate`` / ``search`` never see it. Zero content pollution, by
construction.

Record shape (engine-fixed, layout-independent):

    {
      "name": "research-handoff",
      "version": 1,
      "requester": {"profiles": ["creative"], "domains": ["work/creative/**"]},
      "responder": {"profiles": ["researcher"], "domains": ["work/*/knowledge/**"]},
      "request_format": "task + intent + expected response form",
      "response_format": "findings + sources + summary; final message is the deliverable",
      "instructions": "REQUEST SIDE — ...\\nRESPONSE SIDE — ..."
    }

Access: **read** is grant-free for any registered agent (the
tool layer enforces identity via ``roles.get``); **write** is parties-only —
create requires the caller to be one of the sides (self-registration),
update requires the caller to be a party of the existing record. The engine
raises :class:`~vault.grants.PermissionDenied` otherwise. Delete is out of
scope this phase (append/update only).

The **slug is the dedupe unit**: deterministic from ``name``, and the
filename is derived from it. Re-registering the same name replaces the
record (parties re-negotiate by updating in place).
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from . import audit
from .config import resolve_config
from .constants import PROTOCOLS_DIRNAME
from .grants import PermissionDenied
from .paths import safe_join

logger = logging.getLogger(__name__)

#: Required record fields — engine-fixed. The *values* (profile names,
#: domains, formats, instructions) are per-vault policy.
REQUIRED_FIELDS = (
    "name",
    "requester",
    "responder",
    "request_format",
    "response_format",
    "instructions",
)

#: The two sides of a handoff; each is a dict with ``profiles`` (non-empty)
#: and optional ``domains``.
SIDE_FIELDS = ("profiles", "domains")


class ProtocolError(Exception):
    """Raised for invalid protocol records (missing fields, bad shape)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def protocols_dir(vault_root: Path) -> Optional[Path]:
    """The registry folder (``<state>/protocols``), or ``None`` if no state dir.

    Mirrors ``audit.audit_path`` / ``issues.issues_dir``: the state dir
    defaults to root ``.state/`` (``ResolvedConfig.state_path`` never returns
    empty), but the guard stays.
    """
    cfg = resolve_config(Path(vault_root), Path(vault_root))
    state = cfg.state_path()
    if not state:
        return None
    return safe_join(Path(vault_root), state) / PROTOCOLS_DIRNAME


def _slug(name: str) -> str:
    """Filename-safe slug of the handoff name, with a short hash.

    Same name → same filename (deterministic replacement). The hash
    disambiguates two names whose slugs collide; the full name is stored
    inside the record.
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()[:60] or "protocol"
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}.yaml"


def _protocol_path(vault_root: Path, name: str) -> Optional[Path]:
    d = protocols_dir(vault_root)
    if d is None:
        return None
    return d / _slug(name)


def _atomic_write(path: Path, record: Dict[str, Any]) -> None:
    """Write via temp + rename so a crash never corrupts a record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".yaml.tmp")
    tmp.write_text(
        yaml.safe_dump(record, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _read(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, yaml.YAMLError):
        return None


def _validate_record(record: Dict[str, Any]) -> None:
    """Reject malformed records before any write (validate at the door)."""
    if not isinstance(record, dict):
        raise ProtocolError("record must be a mapping")
    for field in REQUIRED_FIELDS:
        if not record.get(field):
            raise ProtocolError(f"missing required field {field!r}")
    if not isinstance(record["name"], str) or not record["name"].strip():
        raise ProtocolError("name must be a non-empty string")
    for side in ("requester", "responder"):
        side_dict = record[side]
        if not isinstance(side_dict, dict):
            raise ProtocolError(f"{side} must be a mapping with 'profiles'")
        profiles = side_dict.get("profiles")
        if not isinstance(profiles, list) or not profiles:
            raise ProtocolError(f"{side}.profiles must be a non-empty list")
        if not all(isinstance(p, str) and p.strip() for p in profiles):
            raise ProtocolError(f"{side}.profiles must contain non-empty strings")
        domains = side_dict.get("domains")
        if domains is not None and not isinstance(domains, list):
            raise ProtocolError(f"{side}.domains must be a list when present")


def _is_party(record: Dict[str, Any], agent: str) -> bool:
    """Is ``agent`` a requester or responder of this handoff?"""
    for side in ("requester", "responder"):
        profiles = record.get(side, {}).get("profiles", [])
        if agent in profiles:
            return True
    return False


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _summary(record: Dict[str, Any]) -> Dict[str, Any]:
    """List view — no instructions (the agent loads one record when needed)."""
    return {
        "name": record["name"],
        "version": record.get("version", 1),
        "requester": record["requester"],
        "responder": record["responder"],
        "request_format": record["request_format"],
        "response_format": record["response_format"],
    }


def list_protocols(
    vault_root: Path,
    agent: str,
    peer: Optional[str] = None,
) -> Dict[str, Any]:
    """All handoffs where ``agent`` is a party, optionally narrowed by peer.

    Practical visibility is party-filtered: an agent sees
    only the handoffs it participates in by default; ``peer`` narrows to the
    handoffs between exactly these two profiles (either direction).
    """
    root = Path(vault_root).resolve()
    d = protocols_dir(root)
    if d is None or not d.is_dir():
        return {"protocols": [], "count": 0}

    out: List[Dict[str, Any]] = []
    for path in sorted(d.glob("*.yaml")):
        record = _read(path)
        if record is None or not _is_party(record, agent):
            continue
        if peer:
            requester = record.get("requester", {}).get("profiles", [])
            responder = record.get("responder", {}).get("profiles", [])
            if not (
                (agent in requester and peer in responder)
                or (agent in responder and peer in requester)
            ):
                continue
        out.append(_summary(record))
    return {"protocols": out, "count": len(out)}


def get_protocol(vault_root: Path, name: str) -> Optional[Dict[str, Any]]:
    """The full record (both sides' instructions), or ``None``."""
    path = _protocol_path(Path(vault_root).resolve(), name)
    if path is None or not path.exists():
        return None
    return _read(path)


def register_protocol(
    vault_root: Path,
    agent: str,
    record: Dict[str, Any],
    *,
    confirm: bool = False,
) -> Dict[str, Any]:
    """Create a handoff — caller must be one of the sides (self-registration).

    Without ``confirm`` this validates + gates and returns the would-be
    record without writing (propose mode, like ``obsidian_edit_config``).
    With ``confirm`` it writes and audits. Re-registering an existing name
    replaces the record in place (parties re-negotiate by updating).
    """
    _validate_record(record)
    if not _is_party(record, agent):
        raise PermissionDenied(
            f"{agent} may not register a handoff it is not a party of: "
            f"create requires the caller to be requester or responder"
        )

    root = Path(vault_root).resolve()
    path = _protocol_path(root, record["name"])
    if path is None:
        return {"ok": False, "error": "no_state_dir", "name": record["name"]}

    if not confirm:
        return {
            "ok": True,
            "action": "register",
            "proposed": record,
            "confirm_required": True,
            "message": "Validated and gated; pass confirm=true to write.",
        }

    _atomic_write(path, record)
    audit.record(root, agent, "protocol_register", record["name"])
    logger.info("%s registered protocol %s", agent, record["name"])
    return {"ok": True, "action": "registered", "name": record["name"],
            "path": _rel(root, path)}


def update_protocol(
    vault_root: Path,
    agent: str,
    name: str,
    record: Dict[str, Any],
    *,
    confirm: bool = False,
) -> Dict[str, Any]:
    """Replace a handoff — caller must be a party of the EXISTING record.

    The new record may change sides/domains (re-negotiation, e.g. a party
    leaves and the remaining party updates). ``name`` selects the record;
    the record's own ``name`` field is kept from the argument (the slug is
    the identity, so a rename is delete+create — out of scope this phase).
    """
    root = Path(vault_root).resolve()
    path = _protocol_path(root, name)
    if path is None:
        return {"ok": False, "error": "no_state_dir", "name": name}
    existing = _read(path) if path.exists() else None
    if existing is None:
        return {"ok": False, "error": "not_found", "name": name}

    if not _is_party(existing, agent):
        raise PermissionDenied(
            f"{agent} may not update {name!r}: only its parties may — "
            f"update requires requester or responder membership in the "
            f"existing record"
        )

    _validate_record(record)
    record = dict(record)
    record["name"] = name  # the slug is the identity; never drift it

    if not confirm:
        return {
            "ok": True,
            "action": "update",
            "proposed": record,
            "confirm_required": True,
            "message": "Validated and gated; pass confirm=true to write.",
        }

    _atomic_write(path, record)
    audit.record(root, agent, "protocol_update", name)
    logger.info("%s updated protocol %s", agent, name)
    return {"ok": True, "action": "updated", "name": name,
            "path": _rel(root, path)}
