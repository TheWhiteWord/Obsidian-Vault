"""Per-scope conventions — the in-tree scope directives (spec 07 §4, P7).

**Mechanism only.** A conventions file may sit at any depth:
``<scope>/.vault/conventions.md``. Discovery mirrors config (walk up from
the working folder): the **nearest** file wins on conflict (override);
absent rules fall back up the chain. The files are machinery — inside
``.vault/``, so ``SKIP_DIRS`` keeps them out of note-walks, INDEX and
search.

Read is open to any agent. Write is the **derived owner of the containing
scope** only: ``roles.check(agent, "edit", rel)`` enforces the write grant
and P7 shadowing in one call — the manager never writes conventions (it
never writes prose).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .audit import record as audit_record
from .constants import CONFIG_DIRNAME, CONVENTIONS_FILENAME
from .grants import RoleRegistry
from .paths import VaultPathError, relative_to_vault, safe_join

logger = logging.getLogger(__name__)


def conventions_path(folder: Path) -> Path:
    """The conventions file for one scope folder."""
    return folder / CONFIG_DIRNAME / CONVENTIONS_FILENAME


def conventions_chain(vault_root: Path, target: Path) -> List[Path]:
    """Every existing conventions file from vault root down to ``target``, root-first.

    A later entry is closer to the target and wins on conflict.
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
        path = conventions_path(folder)
        if path.is_file():
            chain.append(path)
    return chain


def nearest_conventions(vault_root: Path, target: Path) -> Optional[Path]:
    """The closest conventions file for ``target``, or ``None`` when none exists."""
    chain = conventions_chain(vault_root, target)
    return chain[-1] if chain else None


def resolved_conventions(vault_root: Path, target: Path) -> Dict[str, Any]:
    """The resolved chain for a scope: files root-first, with their content.

    An agent reads the whole chain — nearest wins, the rest is fallback.
    """
    chain = conventions_chain(vault_root, target)
    return {
        "files": [str(p.relative_to(vault_root)) for p in chain],
        "chain": [p.read_text(encoding="utf-8") for p in chain],
        "nearest": (
            str(chain[-1].relative_to(vault_root)) if chain else None
        ),
    }


def fingerprint(text: str) -> str:
    """Short content fingerprint — the declined-by-convention dedupe key
    (spec 07 §6.4): a suggestion declined because conventions cover it is
    re-suggested only when the fingerprint changes."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def write_conventions(
    vault_root: Path,
    agent: str,
    roles: RoleRegistry,
    path: str,
    content: str,
) -> Dict[str, Any]:
    """Write a conventions file (spec 07 §4.5).

    Gated on ``write`` over the containing scope: ``roles.check(agent,
    "edit", rel)`` enforces the grant AND P7 shadowing — the derived owner
    of the scope is the only writer. Audited; no INDEX regeneration; never
    note-validated (it is not a note).
    """
    root = Path(vault_root).resolve()
    target = safe_join(root, path)
    rel = relative_to_vault(root, target)

    if target.name != CONVENTIONS_FILENAME or CONFIG_DIRNAME not in target.parts:
        raise VaultPathError(
            f"{path!r} is not a {CONFIG_DIRNAME}/{CONVENTIONS_FILENAME} file"
        )

    roles.check(agent, "edit", rel)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    audit_record(root, agent, "edit_conventions", rel)
    logger.info("%s wrote %s", agent, rel)
    return {"ok": True, "path": rel}
