"""Wikilink graph — derived on demand (Principle 1).

The graph is *derived*, not stored as a source of truth. It is computed from
note bodies on demand, so it cannot drift from reality (there is no cached copy
to go stale). At vault scale (thousands of notes) a full recompute is sub-second;
that is simpler and more correct than an incremental cache that must be kept in
sync with every write. The spec says "incremental" — deriving per call is the
stronger form of that guarantee.

Nodes are notes (by vault-relative path). Edges are `[[wikilinks]]`. Link
targets are resolved to notes by title (case-insensitive); an edge to a missing
title is kept as a dangling edge so the maintenance pass (P4) can flag it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .notes import Note, iter_notes


class Graph:
    """An in-memory wikilink graph for one vault."""

    def __init__(self, notes: Iterable[Note]):
        self.notes: List[Note] = [n for n in notes if not n.error]
        self._by_title: Dict[str, Note] = {}
        for n in self.notes:
            self._by_title.setdefault(n.title.lower(), n)

        self.nodes: Set[str] = {n.path for n in self.notes}
        # outgoing[path] = list of (target_path_or_None, raw_label)
        self.outgoing: Dict[str, List[Tuple[Optional[str], str]]] = {p: [] for p in self.nodes}
        self.incoming: Dict[str, List[str]] = {p: [] for p in self.nodes}
        self.dangling: List[Tuple[str, str]] = []

        for n in self.notes:
            for label in n.links:
                target = self._by_title.get(label.strip().lower())
                target_path = target.path if target else None
                self.outgoing[n.path].append((target_path, label.strip()))
                if target_path:
                    self.incoming[target_path].append(n.path)
                else:
                    self.dangling.append((n.path, label.strip()))

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
    return Graph(notes)
