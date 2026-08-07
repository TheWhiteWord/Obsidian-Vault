"""Vault v2 — core library.

Filesystem-first, headless-capable. No dependency on a running Obsidian.
See docs/concepts/model.md.
"""

from .config import ConfigError, ResolvedConfig, resolve_config
from .context import build_context
from .notes import Note, derive_tags, derive_vocabulary, iter_notes, parse_note
from .paths import (
    VaultPathError,
    relative_to_vault,
    resolve_vault_root,
    safe_join,
    vault_root_or_none,
)

__all__ = [
    # config
    "ConfigError",
    "ResolvedConfig",
    "resolve_config",
    # context
    "build_context",
    # notes
    "Note",
    "parse_note",
    "iter_notes",
    "derive_tags",
    "derive_vocabulary",
    # paths
    "VaultPathError",
    "resolve_vault_root",
    "vault_root_or_none",
    "safe_join",
    "relative_to_vault",
]
