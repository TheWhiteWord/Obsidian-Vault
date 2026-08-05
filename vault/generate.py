"""Generated artifacts — spec §6.

INDEX files and the config registry are *derived*: regenerated from the vault's
actual contents and overwritten without warning. Nothing here is ever
hand-edited, and every generated file says so in its first line.

This is principle 1 (derive, don't declare) made concrete. v1's failure was a
hand-maintained TAXONOMY.md that drifted from reality the moment anyone wrote a
note without updating it. A file that regenerates cannot drift.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .config import ResolvedConfig, resolve_config
from .constants import CONFIG_DIRNAME, GENERATED_MARKER, SKIP_DIRS, SUMMARY_FIELD_KEY
from .notes import Note, derive_tags, derive_vocabulary, iter_notes
from .paths import relative_to_vault, safe_join

logger = logging.getLogger(__name__)

INDEX_FILENAME = "INDEX.md"
REGISTRY_FILENAME = "registry.md"


def is_generated(path: Path) -> bool:
    """True if the file carries the generated marker — safe to overwrite."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            return GENERATED_MARKER in fh.readline()
    except (OSError, UnicodeDecodeError):
        return False


def _guard_overwrite(target: Path) -> None:
    """Refuse to clobber a hand-authored file that happens to share the name."""
    if target.exists() and not is_generated(target):
        raise FileExistsError(
            f"{target.name} exists and is not marked generated — refusing to "
            f"overwrite hand-authored content"
        )


def _header(title: str) -> List[str]:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return [
        GENERATED_MARKER,
        "",
        f"# {title}",
        "",
        f"*Generated {stamp}. Edits are lost on regeneration — "
        f"change the source, not this file.*",
        "",
    ]


# ---------------------------------------------------------------------------
# INDEX
# ---------------------------------------------------------------------------

def _group_by_subfolder(
    notes: List[Note], folder_rel: str
) -> Dict[str, List[Note]]:
    groups: Dict[str, List[Note]] = {}
    prefix = f"{folder_rel}/" if folder_rel else ""
    for note in notes:
        remainder = note.path[len(prefix):] if prefix else note.path
        parts = remainder.split("/")
        key = "" if len(parts) == 1 else parts[0]
        groups.setdefault(key, []).append(note)
    return groups


def build_index(vault_root: Path, folder: str) -> str:
    """Render the INDEX for one folder. Pure — writes nothing."""
    root = Path(vault_root).resolve()
    target = safe_join(root, folder)
    rel = relative_to_vault(root, target)
    cfg = resolve_config(root, target)

    notes = [n for n in iter_notes(root, scope=target)
             if Path(n.path).name != INDEX_FILENAME]

    title = Path(rel).name if rel else root.name
    lines = _header(f"{title}")

    if not notes:
        lines += ["*No notes yet.*", ""]
        return "\n".join(lines)

    lines += [f"**{len(notes)} notes**", ""]

    groups = _group_by_subfolder(notes, rel)

    for key in sorted(groups, key=lambda k: (k == "", k)):
        group = sorted(groups[key], key=lambda n: n.title.lower())
        if key:
            lines += [f"## {key}", ""]

        for note in group:
            extras = " ".join(
                f"· *{note.frontmatter[fn]}*"
                for fn in cfg.vocabulary_fields()
                if isinstance(note.frontmatter.get(fn), str)
                and not fn.endswith("tags")
            )
            summary = ""
            if cfg.summary_field:
                value = note.frontmatter.get(cfg.summary_field)
                if isinstance(value, str) and value.strip():
                    summary = f" — {value.strip()}"
            suffix = f" {extras}{summary}" if (extras or summary) else ""
            lines.append(f"- [[{note.title}]]{suffix}")
        lines.append("")

    # Derived tag cloud — the folder's actual vocabulary, not a declared one.
    tags = derive_tags(notes)
    if tags:
        lines += ["## Tags", "",
                  " · ".join(f"#{t['name']} ({t['count']})" for t in tags[:30]),
                  ""]

    malformed = [n.path for n in notes if n.error]
    if malformed:
        lines += ["## Needs attention", ""]
        lines += [f"- `{p}` — frontmatter could not be parsed" for p in malformed]
        lines.append("")

    return "\n".join(lines)


def write_index(vault_root: Path, folder: str) -> Optional[str]:
    """Generate and write one folder's INDEX. Returns its vault-relative path."""
    root = Path(vault_root).resolve()
    target = safe_join(root, folder)
    if not target.is_dir():
        return None

    index_file = target / INDEX_FILENAME
    _guard_overwrite(index_file)
    index_file.write_text(build_index(root, folder), encoding="utf-8")
    return relative_to_vault(root, index_file)


def regenerate_indexes(
    vault_root: Path,
    scope: Optional[str] = None,
) -> List[str]:
    """Regenerate INDEX for every folder containing notes, under ``scope``."""
    root = Path(vault_root).resolve()
    base = safe_join(root, scope) if scope else root

    folders = {
        p.parent for p in base.rglob("*.md")
        if not (SKIP_DIRS & set(p.relative_to(root).parts))
        and p.name != INDEX_FILENAME
    }

    written: List[str] = []
    for folder in sorted(folders):
        try:
            path = write_index(root, relative_to_vault(root, folder))
            if path:
                written.append(path)
        except FileExistsError as exc:
            logger.warning("skipped index: %s", exc)
    return written


# ---------------------------------------------------------------------------
# Registry — a readable view of the merged configs
# ---------------------------------------------------------------------------

def _config_folders(vault_root: Path) -> List[Path]:
    root = Path(vault_root).resolve()
    return sorted(
        p.parent.parent
        for p in root.rglob(f"{CONFIG_DIRNAME}/config.yaml")
    )


def build_registry(vault_root: Path) -> str:
    """Render the config registry — every folder's effective schema.

    Replaces v1's hand-written SCHEMA.md and TAXONOMY.md. Those described what
    the vault was *supposed* to look like; this describes what it *is*.
    """
    root = Path(vault_root).resolve()
    lines = _header("Vault registry")

    lines += [
        "Effective schema for every folder that declares one, plus the "
        "vocabulary actually in use. Derived from `.vault/config.yaml` files "
        "and the notes themselves.",
        "",
    ]

    for folder in _config_folders(root):
        rel = relative_to_vault(root, folder) or "(vault root)"
        cfg = resolve_config(root, folder)
        notes = list(iter_notes(root, scope=folder))

        lines += [f"## `{rel}`", ""]

        chain = " → ".join(
            relative_to_vault(root, p.parent.parent) or "root" for p in cfg.sources
        )
        lines += [f"*Inherits:* {chain}", ""]

        if cfg.required_fields:
            lines += [f"*Required:* {', '.join(f'`{f}`' for f in cfg.required_fields)}", ""]

        for name in cfg.vocabulary_fields():
            vocab = derive_vocabulary(notes, name, cfg.allowed_values(name))
            used = [f"`{e['name']}` ({e['count']})"
                    for e in vocab["declared"] if not e.get("unused")]
            unused = [f"`{e['name']}`" for e in vocab["declared"] if e.get("unused")]
            observed = [f"`{e['name']}` ({e['count']})" for e in vocab["observed"]]

            lines.append(f"**{name}**")
            if used:
                lines.append(f"- in use: {', '.join(used)}")
            if unused:
                lines.append(f"- declared, unused: {', '.join(unused)}")
            if observed:
                lines.append(f"- ⚠ observed (unregistered): {', '.join(observed)}")
            lines.append("")

        lines += [f"*Notes here:* {len(notes)}", ""]

    return "\n".join(lines)


def write_registry(vault_root: Path, destination: str) -> Optional[str]:
    """Write the registry to ``destination`` (a vault-relative folder)."""
    root = Path(vault_root).resolve()
    folder = safe_join(root, destination)
    folder.mkdir(parents=True, exist_ok=True)

    target = folder / REGISTRY_FILENAME
    _guard_overwrite(target)
    target.write_text(build_registry(root), encoding="utf-8")
    return relative_to_vault(root, target)
