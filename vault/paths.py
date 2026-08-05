"""Vault path resolution.

Single source of truth for "where is the vault, and is this path inside it".
Every tool needs this — the write tool (P1), search (P3), and the maintenance
cron (P4) — so it does not live in the plugin entrypoint.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

ENV_VAR = "OBSIDIAN_VAULT_PATH"


class VaultPathError(Exception):
    """Raised when a vault root cannot be resolved, or a path escapes it."""


def resolve_vault_root(explicit: Optional[str] = None) -> Path:
    """Resolve the vault root from an explicit path or ``$OBSIDIAN_VAULT_PATH``.

    Raises :class:`VaultPathError` with an actionable message rather than
    returning ``None`` — a missing vault is a configuration fault, and callers
    should not have to invent their own error text.
    """
    raw = (explicit or os.environ.get(ENV_VAR, "")).strip()
    if not raw:
        raise VaultPathError(
            f"no vault root: set {ENV_VAR} in $HERMES_HOME/.env "
            f"or pass an explicit path"
        )

    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        raise VaultPathError(f"vault root is not a directory: {root}")
    return root


def vault_root_or_none(explicit: Optional[str] = None) -> Optional[Path]:
    """Non-raising variant, for availability checks (``check_fn``)."""
    try:
        return resolve_vault_root(explicit)
    except VaultPathError:
        return None


def safe_join(vault_root: Path, relative: str) -> Path:
    """Resolve ``relative`` inside ``vault_root``, refusing escapes.

    Guards against ``../`` traversal and absolute paths. This is the chokepoint
    every path from an agent passes through — the permission model (P1) is only
    as good as the guarantee that a path stays inside the vault.
    """
    root = Path(vault_root).resolve()
    raw = (relative or "").strip()

    # An absolute path is a caller error, not something to silently reinterpret
    # as vault-relative. Refuse it rather than quietly rewriting the meaning.
    if raw.startswith("/") and raw != "/":
        raise VaultPathError(
            f"path escapes the vault: {relative!r} is absolute; "
            f"pass a vault-relative path"
        )

    cleaned = raw.strip("/")
    if not cleaned or cleaned == ".":
        return root

    candidate = (root / cleaned).resolve()
    if candidate != root and root not in candidate.parents:
        raise VaultPathError(
            f"path escapes the vault: {relative!r} resolves outside {root}"
        )
    return candidate


def relative_to_vault(vault_root: Path, path: Path) -> str:
    """POSIX-style vault-relative path, for stable output across platforms."""
    return Path(path).resolve().relative_to(Path(vault_root).resolve()).as_posix()
