"""Generated artifacts — see docs/concepts/model.md.

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
from .constants import (
    CONFIG_DIRNAME,
    GENERATED_MARKER,
    MARKDOWN_SUFFIX,
    SKIP_DIRS,
    STATE_DIRNAME,
    SUMMARY_FIELD_KEY,
)
from .notes import Note, derive_tags, derive_vocabulary, iter_notes, parse_note
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

def _immediate_notes(vault_root: Path, target: Path) -> List[Note]:
    """Notes whose file lives directly inside ``target`` (depth 1 only).

    An INDEX documents *its own* folder, not the whole subtree — each deeper
    folder carries its own INDEX, so descent is by wikilink, not by inlining.
    Subfolders are reported separately (see ``_child_folders``) so a folder's
    INDEX lists notes here plus pointers to its children, never its children's
    contents.
    """
    root = Path(vault_root).resolve()
    notes: List[Note] = []
    skip = SKIP_DIRS
    for entry in sorted(target.iterdir()):
        if not entry.is_file() or entry.suffix != MARKDOWN_SUFFIX:
            continue
        if entry.name == INDEX_FILENAME:
            continue
        if skip & set(entry.relative_to(root).parts):
            continue
        notes.append(parse_note(entry, root))
    return notes


def _child_folders(vault_root: Path, target: Path) -> List[str]:
    """Immediate subfolder names, in render order.

    Every direct subfolder is a pointer — descent through the tree happens by
    following each child's own INDEX, so a folder's INDEX must name *all* its
    children even when a child holds no notes of its own yet. Omitting
    "empty" subfolders would hide branches that exist but are sparsely
    populated, and (worse) depended on the child's INDEX.md already existing,
    which broke during a top-down bulk regen where parents are written first.
    """
    root = Path(vault_root).resolve()
    skip = SKIP_DIRS
    children: List[str] = []
    for entry in sorted(target.iterdir()):
        if not entry.is_dir():
            continue
        if skip & set(entry.relative_to(root).parts):
            continue
        children.append(entry.name)
    return children


def _format_note_line(note: Note, cfg) -> str:
    """The ``- [[title]] · *type* — summary`` line for one note."""
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
    return f"- [[{note.title}]]{suffix}"


def build_index(vault_root: Path, folder: str) -> str:
    """Render the INDEX for one folder. Pure — writes nothing.

    The index records only what is *in this folder*: the notes at its own
    level, and pointers to its immediate subfolders (each of which carries its
    own INDEX). It does not recurse — descent through the tree happens by
    following a child's INDEX, so a note appears in exactly one INDEX (its own
    folder's) instead of being duplicated into every ancestor.
    """
    root = Path(vault_root).resolve()
    target = safe_join(root, folder)
    rel = relative_to_vault(root, target)
    cfg = resolve_config(root, target)

    notes = _immediate_notes(root, target)
    subfolders = _child_folders(root, target)

    title = Path(rel).name if rel else root.name
    lines = _header(f"{title}")

    if not notes and not subfolders:
        lines += [f"*No notes yet.*", ""]
        return "\n".join(lines)

    lines += [f"**{len(notes)} notes**", ""]

    # Child folders first — the tree descends through them. Each folder is
    # expanded one level so the reader sees what it immediately contains
    # (its own notes and its subfolders) without the index recursing.
    if subfolders:
        lines += ["## Folders", ""]
        for name in subfolders:
            lines.append(f"- [[{name}]]")
            child_dir = target / name
            child_notes = _immediate_notes(root, child_dir)
            child_subs = _child_folders(root, child_dir)
            for cn in sorted(child_notes, key=lambda n: n.title.lower()):
                lines.append(f"    {_format_note_line(cn, cfg)}")
            for cs in child_subs:
                lines.append(f"    - [[{cs}]]")
        lines.append("")

    # Then the notes that physically live in this folder.
    if notes:
        lines += ["## Notes", ""]
        for note in sorted(notes, key=lambda n: n.title.lower()):
            lines.append(_format_note_line(note, cfg))
        lines.append("")

    # Derived tag cloud — this folder's own vocabulary, not a declared one.
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


def reindex_ancestors(vault_root: Path, folder: str) -> List[str]:
    """Regenerate the INDEX of ``folder`` and every ancestor up to the root.

    A new folder must be reflected in its parent's INDEX (the parent lists
    its children); that parent's change must reach *its* parent, and so on
    up to the vault root. No single write path regenerated ancestors before,
    so creating a nested folder left every ancestor's INDEX stale — the
    parent never listed the new child. This closes that gap for any creation
    site (scaffold, domain bind, and future out-of-band paths) in one call.

    Skips engine-reserved folders (``.vault``, ``.state``) as content trees:
    they must never carry a content-derived INDEX of themselves.

    Never raises: a derived view failing to regenerate must not fail the
    caller's operation. The next regeneration repairs whatever was missed.
    """
    root = Path(vault_root).resolve()
    target = safe_join(root, folder)
    if not target.is_dir():
        return []

    rel = relative_to_vault(root, target)
    # Folder itself, then each ancestor up to and including the root
    # (empty string). The root INDEX lists top-level folders too, so it must
    # be refreshed when a top-level folder appears.
    if rel:
        parts = Path(rel).parts
        chain: List[str] = [rel] + [
            str(Path(*parts[:i])) for i in range(len(parts) - 1, 0, -1)
        ]
        chain.append("")  # vault root
    else:
        chain = [""]

    written: List[str] = []
    for rel_folder in chain:
        try:
            target_dir = safe_join(root, rel_folder)
            if CONFIG_DIRNAME in target_dir.parts or STATE_DIRNAME in target_dir.parts:
                continue
            path = write_index(root, rel_folder)
            if path:
                written.append(path)
        except Exception:  # noqa: BLE001 — derived view; never fatal
            logger.warning("ancestor index regeneration failed for %s",
                           rel_folder, exc_info=True)
    return written


def regenerate_indexes(
    vault_root: Path,
    scope: Optional[str] = None,
) -> List[str]:
    """Regenerate INDEX for every folder under ``scope``.

    Enumerates *every* directory (not just those with direct notes): a folder
    that is purely a container of subfolders still needs a correct INDEX
    listing its child folders — and one that has gone content-free still needs
    its stale INDEX refreshed to "*No notes yet.*". Skipping such folders would
    leave the old recursive output (which inlined descendants) in place.
    """
    root = Path(vault_root).resolve()
    base = safe_join(root, scope) if scope else root

    folders = {
        p for p in base.rglob("*")
        if p.is_dir() and not (SKIP_DIRS & set(p.relative_to(root).parts))
    }
    folders.add(base)  # the scope root itself needs an INDEX too

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
