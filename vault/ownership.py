"""Derived ownership from canonical ownership globs — spec 07 §2.2 (P7).

**Mechanism only.** Ownership is a *derived* property of the live
``roles.yaml``: a path's owner is the agent holding the most-specific
**ownership glob**. An ownership glob has canonical shape — one or two
literal segments, optional terminal ``/**`` (``work/<d>/**``,
``work/<d>/<s>/**``, ``system/**``) — and only ``bind`` produces them.

Every other write glob is a **capability glob**: it grants write where it
matches, but never establishes ownership and never shadows an ownership
glob. The old ``work/*/knowledge/**`` write glob is capability-only by
construction.

``write``/``config`` resolve only for the derived owner (shadowing);
``read``/``meta`` stay generous. This module is the single source for both
the resolver and the bind-time validation.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Optional, Tuple

_GLOB_CHARS = "*?["


def is_ownership_glob(pattern: str) -> bool:
    """Canonical ownership shape: 1-3 literal segments, optional terminal ``/**``.

    The bind-produced shapes: ``system/**`` (1), ``work/<d>/**`` (2),
    ``work/<d>/<s>/**`` (3). A bare literal (``work/creative``) is accepted
    as the folder itself; ``path_matches`` treats a trailing ``/**`` as also
    matching the folder, so the two are equivalent for ownership purposes.
    ``**`` / ``*`` alone (no literal anchor) are not ownership globs.
    """
    p = pattern.strip("/")
    if p.endswith("/**"):
        p = p[:-3]
    if not p:
        return False
    segments = p.split("/")
    if len(segments) > 3:
        return False
    return all(seg and not any(c in seg for c in _GLOB_CHARS) for seg in segments)


def _matches(pattern: str, target: str) -> bool:
    """Match a canonical ownership glob (literal segments + optional ``/**``)."""
    if pattern.endswith("/**"):
        base = pattern[:-3]
        return target == base or target.startswith(base + "/")
    return target == pattern


def _segments(pattern: str) -> int:
    p = pattern.strip("/")
    if p.endswith("/**"):
        p = p[:-3]
    return p.count("/") + 1


def owner_of(
    ownership_globs: Mapping[str, Iterable[str]],
    rel_path: str,
) -> Optional[str]:
    """The derived owner of ``rel_path``, or ``None`` when no ownership glob matches.

    ``ownership_globs`` maps agent name → that agent's *write* globs (only
    write globs can establish ownership). Most segments wins
    (``work/<d>/<s>/**`` beats ``work/<d>/**``); a real tie is refused at
    bind time by :func:`duplicate_ownership_globs`, so the agent-name
    tie-break here is only a deterministic fallback for hand-edited policy.
    """
    target = rel_path.strip("/")
    best: Optional[Tuple[int, str]] = None
    winner: Optional[str] = None
    for agent, globs in ownership_globs.items():
        for pattern in globs:
            if not is_ownership_glob(pattern):
                continue
            if not _matches(pattern, target):
                continue
            key = (-_segments(pattern), agent)
            if best is None or key < best:
                best, winner = key, agent
    return winner


def duplicate_ownership_globs(
    agents_write: Mapping[str, Iterable[str]],
) -> List[str]:
    """Ownership globs held by more than one agent — the bind-time refusal.

    Two agents holding the *same* ownership glob would make ownership
    ambiguous (same depth, same literal). Nested globs at different depths
    are the design, not a conflict: ``work/<d>/**`` and
    ``work/<d>/<s>/**`` resolve by segment count. Returns human-readable
    conflict lines; empty means the set is sound.
    """
    holder: Dict[str, str] = {}
    conflicts: List[str] = []
    for agent, globs in agents_write.items():
        for pattern in globs:
            if not is_ownership_glob(pattern):
                continue
            norm = pattern.strip("/")
            if norm in holder and holder[norm] != agent:
                conflicts.append(f"{norm} ({holder[norm]} and {agent})")
            else:
                holder.setdefault(norm, agent)
    return conflicts
