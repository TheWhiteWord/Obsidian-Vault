"""Wikilink graph — derived on demand (Principle 1).

The graph is *derived*, not stored as a source of truth. It is computed from
note bodies on demand, so it cannot drift from reality (there is no cached copy
to go stale). At vault scale (thousands of notes) a full recompute is sub-second;
that is simpler and more correct than an incremental cache that must be kept in
sync with every write. The spec says "incremental" — deriving per call is the
stronger form of that guarantee.

Nodes are notes (by vault-relative path). Edges are `[[wikilinks]]`. Link
targets are resolved by title (case-insensitive); a label carrying ``/`` or
``..`` is treated as a *path-qualified* link and resolved Obsidian-style
(folder-relative, vault-root-relative, then suffix match), so cross-folder
``[[../comfyui/00-overview]]`` / ``[[folder/note]]`` links resolve correctly.
An edge that resolves to nothing is kept as a dangling edge so the
maintenance pass (P4) can flag it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .notes import Note, iter_notes


class Graph:
    """An in-memory wikilink graph for one vault."""

    def __init__(self, notes: Iterable[Note], vault_root: Optional[Path] = None):
        self.vault_root = Path(vault_root).resolve() if vault_root else None
        self.notes: List[Note] = [n for n in notes if not n.error]
        self._by_title: Dict[str, List[Note]] = {}
        for n in self.notes:
            self._by_title.setdefault(n.title.lower(), []).append(n)
        self._by_path: Dict[str, Note] = {n.path: n for n in self.notes}

        self.nodes: Set[str] = {n.path for n in self.notes}
        # outgoing[path] = list of (target_path_or_None, raw_label)
        self.outgoing: Dict[str, List[Tuple[Optional[str], str]]] = {p: [] for p in self.nodes}
        self.incoming: Dict[str, List[str]] = {p: [] for p in self.nodes}
        self.dangling: List[Tuple[str, str]] = []
        # (source_path, label, candidate_paths) triples where a title-link is
        # ambiguous: multiple same-title notes exist and none sits in the
        # source's own folder. Deterministic target chosen, but recorded so the
        # collision is visible rather than silently wrong.
        self.ambiguous: List[Tuple[str, str, List[str]]] = []

        for n in self.notes:
            for label in n.links:
                candidates = self._by_title.get(label.strip().lower(), [])
                # missing title → try path-qualified resolution before
                # declaring dangling (Obsidian-style [[folder/note]] links).
                if not candidates:
                    target = self._resolve_path(n.path, label.strip())
                else:
                    target = candidates[0]
                    if len(candidates) > 1:
                        src_dir = Path(n.path).parent
                        same = [c for c in candidates if Path(c.path).parent == src_dir]
                        if same:
                            target = same[0]
                        else:
                            # pick nearest by longest common path prefix with the source
                            def _score(c: Note) -> int:
                                try:
                                    return len(os.path.commonpath(
                                        [str(Path(n.path).parent),
                                         str(Path(c.path).parent)]))
                                except ValueError:
                                    return 0
                            target = max(candidates, key=_score)
                            self.ambiguous.append(
                                (n.path, label.strip(),
                                 sorted(c.path for c in candidates)))
                target_path = target.path if target else None
                self.outgoing[n.path].append((target_path, label.strip()))
                if target_path:
                    self.incoming[target_path].append(n.path)
                elif not self._dangling_target_exists(n.path, label.strip()):
                    # The graph excludes generated files (INDEX) as nodes, so
                    # a link to one reads as dangling even though the file is
                    # real on disk. Don't flag a link whose target resolves to
                    # an actual file — it is not a broken link. Mirrors the
                    # maintenance census guard (maintain._dangling_target_exists).
                    self.dangling.append((n.path, label.strip()))

    def _dangling_target_exists(self, src_path: str, label: str) -> bool:
        """True if a dangling link's target resolves to a real file on disk.

        The graph builds its node set only from notes, so generated/derived
        files (``INDEX.md``, the registry) are absent and any link to them
        looks broken. A link that resolves to an on-disk ``.md`` is not a
        broken link and must not be reported as dangling. Mirrors the
        maintenance sweep's own guard: path-qualified resolution
        (folder-relative, vault-root-relative, suffix match), then a
        title-keyed note path.
        """
        if self.vault_root is None:
            return False
        root = self.vault_root
        label = label.strip().lstrip("/")
        if not label:
            return False
        parent = str(Path(src_path).parent)
        norm = lambda p: os.path.normpath(p).replace(os.sep, "/")
        candidates = [norm(str(Path(parent) / label)), norm(label)]
        for cand in candidates:
            for try_p in (cand, cand + ".md"):
                if (root / try_p).is_file():
                    return True
        suffix = label.rstrip("/")
        for note in self.notes:
            p = note.path
            if p == suffix or p.endswith("/" + suffix) \
                    or p == suffix + ".md" or p.endswith("/" + suffix + ".md"):
                return True
        return False

    def _resolve_path(self, src_path: str, label: str) -> Optional[Note]:
        """Resolve a path-qualified wikilink label the way Obsidian does.

        A label carrying ``/`` or ``..`` (or a leading ``/``) is a *path*, not a
        title. Obsidian resolves it as: a folder-relative hint, optionally
        vault-root-relative, falling back to a suffix match against any note
        whose vault path ends with the given path. Returns the matched Note, or
        ``None`` if nothing resolves (a genuine dangling link).
        """
        label = label.strip().lstrip("/")
        if not label or ("/" not in label and not label.startswith("..")):
            # pure title — not a path link; let the title lookup handle it
            return None
        parent = str(Path(src_path).parent)
        norm = lambda p: os.path.normpath(p).replace(os.sep, "/")
        candidates: List[str] = []
        # (a) relative to the source note's own folder (handles ../ and sub/)
        candidates.append(norm(str(Path(parent) / label)))
        # (b) vault-root-relative (handles system/INDEX from a root note)
        candidates.append(norm(label))
        for cand in candidates:
            for try_p in (cand, cand + ".md"):
                if try_p in self._by_path:
                    return self._by_path[try_p]
        # (c) suffix match: any note whose vault path ends with this path
        # (Obsidian's folder-hint behaviour for [[folder/note]]).
        suffix = label.rstrip("/")
        for path in self.nodes:
            if path == suffix or path.endswith("/" + suffix) \
                    or path == suffix + ".md" or path.endswith("/" + suffix + ".md"):
                return self._by_path[path]
        return None

    def neighbors(self, path: str) -> Set[str]:
        """All notes directly linked to/from ``path``."""
        out = {t for t, _ in self.outgoing.get(path, []) if t}
        inc = set(self.incoming.get(path, []))
        return out | inc

    def linked(self, path: str, direction: str = "both") -> List[Dict[str, str]]:
        """Adjacency for ``path`` as structured entries.

        direction: "out" (this note links to), "in" (links to this note),
        "both" (union).
        """
        out: List[Dict[str, str]] = []
        for target, label in self.outgoing.get(path, []):
            out.append({"to": target, "label": label, "direction": "out"})
        if direction in ("in", "both"):
            for src in self.incoming.get(path, []):
                out.append({"to": src, "label": src, "direction": "in"})
        if direction == "out":
            out = [e for e in out if e["direction"] == "out"]
        return out

    def traverse(self, start: str, hops: int = 1, direction: str = "both") -> List[str]:
        """Breadth-first walk up to ``hops`` edges from ``start``.

        Returns de-duplicated paths in BFS order, excluding ``start``.
        """
        seen: Set[str] = set()
        frontier = {start}
        result: List[str] = []
        for _ in range(max(0, hops)):
            next_frontier: Set[str] = set()
            for node in frontier:
                for nbr in self.neighbors(node):
                    if nbr not in seen and nbr != start:
                        seen.add(nbr)
                        result.append(nbr)
                        next_frontier.add(nbr)
            frontier = next_frontier
            if not frontier:
                break
        return result


def build_graph(vault_root: Path, notes: Optional[Iterable[Note]] = None) -> Graph:
    """Build the graph for ``vault_root`` (or from a supplied note stream)."""
    vault_root = Path(vault_root).resolve()
    if notes is None:
        notes = iter_notes(vault_root)
    return Graph(notes, vault_root)
