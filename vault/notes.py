"""Note parsing and vocabulary derivation.

The ``Note`` dataclass deliberately mirrors the shape Obsidian's Local REST
API returns for a note (``path`` / ``content`` / ``frontmatter`` / ``tags``).
Same struct from either source, so a future MCP adapter (spec §8 phase 5)
fills the same object with no second data model.

Parsing is delegated to ``python-frontmatter`` rather than hand-rolled — YAML
delimiter handling has more edge cases than it appears (``---`` inside body
content, BOM, CRLF, empty frontmatter). Principle 6: borrow before building.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set

from .constants import MARKDOWN_SUFFIX, SKIP_DIRS
from .paths import relative_to_vault

logger = logging.getLogger(__name__)

#: ``[[Note Name]]`` / ``[[Note Name|alias]]`` / ``[[Note#heading]]``
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")

#: Fenced code blocks and inline code — stripped before link/tag extraction so
#: documentation examples don't pollute the graph.
CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def _strip_code(text: str) -> str:
    return INLINE_CODE_RE.sub("", CODE_FENCE_RE.sub("", text))


@dataclass
class Note:
    """One parsed note. Shape mirrors Obsidian's NoteJson."""

    path: str                                   # vault-relative, POSIX separators
    content: str                                # body, frontmatter stripped
    frontmatter: Dict[str, Any] = dc_field(default_factory=dict)
    tags: List[str] = dc_field(default_factory=list)
    links: List[str] = dc_field(default_factory=list)
    error: Optional[str] = None                 # set when frontmatter failed to parse

    @property
    def folder(self) -> str:
        parent = Path(self.path).parent.as_posix()
        return "" if parent == "." else parent

    @property
    def title(self) -> str:
        return Path(self.path).stem

    def field(self, name: str) -> Any:
        return self.frontmatter.get(name)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "path": self.path,
            "title": self.title,
            "frontmatter": self.frontmatter,
            "tags": self.tags,
            "links": self.links,
        }
        if self.error:
            d["error"] = self.error
        return d


def _normalise_tags(raw: Any) -> List[str]:
    """Frontmatter tags may be a list, a comma string, or a bare scalar."""
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.replace(",", " ").split()]
    elif isinstance(raw, (list, tuple, set)):
        parts = [str(p).strip() for p in raw]
    else:
        parts = [str(raw).strip()]
    return [p.lstrip("#") for p in parts if p]


def parse_note(abs_path: Path, vault_root: Path) -> Note:
    """Parse one markdown file into a :class:`Note`.

    Never raises on malformed frontmatter — returns a Note with ``error`` set
    so a single bad file cannot break a whole-vault scan. The vault manager
    picks these up as maintenance work (spec §1.3).
    """
    import frontmatter

    rel = relative_to_vault(vault_root, abs_path)

    try:
        raw = abs_path.read_text(encoding="utf-8")
    except Exception as exc:
        return Note(path=rel, content="", error=f"unreadable: {exc}")

    try:
        post = frontmatter.loads(raw)
        meta = dict(post.metadata)
        body = post.content
        err = None
    except Exception as exc:
        meta, body, err = {}, raw, f"invalid frontmatter: {exc}"

    clean = _strip_code(body)

    return Note(
        path=rel,
        content=body,
        frontmatter=meta,
        tags=_normalise_tags(meta.get("tags")),
        links=[m.group(1).strip() for m in WIKILINK_RE.finditer(clean)],
        error=err,
    )


def iter_notes(
    vault_root: Path,
    scope: Optional[Path] = None,
    skip_dirs: Optional[Iterable[str]] = None,
    include_generated: bool = False,
) -> Iterator[Note]:
    """Yield every markdown note under ``scope`` (default: whole vault).

    Generated files are excluded by default: an INDEX derived from the notes
    must not then be counted as one of them, or each regeneration feeds on the
    last (spec §6).
    """
    vault_root = vault_root.resolve()
    base = (scope or vault_root).resolve()
    skip = set(skip_dirs) if skip_dirs is not None else set(SKIP_DIRS)

    for path in sorted(base.rglob(f"*{MARKDOWN_SUFFIX}")):
        if skip & set(path.relative_to(vault_root).parts):
            continue
        if not include_generated and _is_generated_file(path):
            continue
        yield parse_note(path, vault_root)


def _is_generated_file(path: Path) -> bool:
    from .constants import GENERATED_MARKER
    try:
        with path.open("r", encoding="utf-8") as fh:
            return GENERATED_MARKER in fh.readline()
    except (OSError, UnicodeDecodeError):
        return False


# ---------------------------------------------------------------------------
# Vocabulary derivation — spec §3.7
# ---------------------------------------------------------------------------

@dataclass
class VocabEntry:
    name: str
    count: int
    state: str          # "declared" | "observed"


def derive_vocabulary(
    notes: Iterable[Note],
    field_name: str,
    declared: Optional[List[str]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Split a field's in-use values into declared and observed (spec §3.7).

    ``declared`` — value appears in a config's ``allowed`` list.
    ``observed`` — value is in use in notes but not declared anywhere.

    Declared values are always returned even at zero usage: an agent should
    see the settled vocabulary, and a zero-count declared value is a
    retirement candidate for the vault manager.
    """
    declared_set: Set[str] = set(declared or [])
    counts: Counter = Counter()

    for note in notes:
        raw = note.frontmatter.get(field_name)
        if raw is None:
            continue
        values = raw if isinstance(raw, (list, tuple, set)) else [raw]
        for value in values:
            text = str(value).strip()
            if text:
                counts[text] += 1

    return {
        "declared": [
            {"name": name, "count": counts[name]}
            for name in (declared or [])
            if counts.get(name)
        ] + [
            {"name": name, "count": 0, "unused": True}
            for name in (declared or [])
            if not counts.get(name)
        ],
        "observed": sorted(
            (
                {"name": name, "count": count}
                for name, count in counts.items()
                if name not in declared_set
            ),
            key=lambda e: (-e["count"], e["name"]),
        ),
    }


def derive_tags(notes: Iterable[Note]) -> List[Dict[str, Any]]:
    """Tag cloud for a scope, most-used first. Derived, never declared (spec §4)."""
    counts: Counter = Counter()
    for note in notes:
        counts.update(note.tags)
    return [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
