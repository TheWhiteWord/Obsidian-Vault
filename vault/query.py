"""Query — the read path (see docs/concepts/grants.md).

The read path. Deterministic: grep-class term matching over note titles,
tags, and bodies. No embeddings, no BM25 — A4 defers those until grep
proves insufficient, and at vault scale it has not.

Grant intersection is the key rule (§2.2.1): an agent's ``read`` grants are
applied to results, not to the query. An agent may search ``**`` and simply
receive nothing from where it cannot read. The search itself never widens a
grant.

``scope`` is a glob — or list of globs — in the engine's shared glob
language (``vault/grants.py`` — ``**`` crosses separators, ``*`` does
not), applied to results after the scan. A ``!``-prefixed entry is an
*exclusion* (P3.8, D9): ``["work/creative/**", "!work/creative/knowledge/**"]``
searches a domain tree minus the shared folder. Exclusions can only remove
results — a scope with no positive glob matches nothing, and negation is
applied after the read-grant intersection. ``folder`` is the single-folder
convenience: scan that subtree only.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from .grants import RoleRegistry, scope_matches
from .notes import Note, iter_notes

logger = logging.getLogger(__name__)

DEFAULT_SURFACES = ["title", "body", "tags", "links", "frontmatter"]

#: Word-boundary via lookarounds, not ``\\b``: ``\\b`` requires a word char
#: on the far side, so terms like ``C#`` or ``C++`` never matched. Lookarounds
#: only require a non-word boundary on the near side, so ``C#`` matches in
#: "learn C# today" while ``eternal`` still does not match "eternally".
_BOUNDARY = r"(?<!\w)(?:{term})(?!\w)"


def _matches_term(haystack: str, term: str) -> bool:
    return bool(re.search(
        _BOUNDARY.format(term=re.escape(term)), haystack, re.IGNORECASE
    ))


def _note_matches(note: Note, terms: List[str], fields: List[str]) -> bool:
    """A note matches if every term appears in some searched surface."""
    if not terms:
        return True

    surfaces = [note.title, note.content]
    if "tags" in fields:
        surfaces.append(" ".join(note.tags))
    if "title" in fields:
        surfaces.append(note.title)
    if "body" in fields:
        surfaces.append(note.content)
    if "links" in fields:
        surfaces.append(" ".join(note.links))
    if "frontmatter" in fields:
        surfaces.append(" ".join(str(v) for v in note.frontmatter.values()))

    haystack = " \n ".join(surfaces)
    return all(_matches_term(haystack, term) for term in terms)


def _score(note: Note, terms: List[str], surfaces: List[str]) -> int:
    """Deterministic relevance: per-term credit per surface hit.

    Title hits weigh double (titles are the strongest signal and are what
    an agent sees first). Body credit counts occurrences, capped so one
    term-spammy note cannot dominate a ranking. Everything stays a pure
    count — no embeddings, no statistical model. Ties fall back to scan
    (path) order in the stable sort.
    """
    score = 0
    title = note.title
    body = note.content
    for term in terms:
        if _matches_term(title, term):
            score += 2
        if _matches_term(body, term):
            occurrences = len(re.findall(
                _BOUNDARY.format(term=re.escape(term)), body, re.IGNORECASE
            ))
            score += min(occurrences, 5)
        if "tags" in surfaces and any(_matches_term(t, term) for t in note.tags):
            score += 1
        if "links" in surfaces and any(_matches_term(l, term) for l in note.links):
            score += 1
        if "frontmatter" in surfaces and any(
            _matches_term(str(v), term) for v in note.frontmatter.values()
        ):
            score += 1
    return score


def search(
    vault_root: Path,
    query: str = "",
    *,
    scope: Optional[Union[str, List[str]]] = None,
    fields: Optional[List[str]] = None,
    folder: Optional[str] = None,
    group_by: Optional[str] = None,
    roles: Optional[RoleRegistry] = None,
    agent: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Search the vault.

    Args:
        query: space-separated terms; a note must contain all of them.
        scope: glob over vault-relative paths restricting the result set
            (e.g. ``"CREATIVE/**"`` or ``"*/KNOWLEDGE/**"``), in the engine's
            shared glob language. Independent of read grants; the two are
            intersected.
        fields: which surfaces to match — any of
            ``title|body|tags|links|frontmatter``. Default all.
        folder: convenience alias for ``scope="<folder>/**"`` — scans that
            subtree only.
        group_by: ``folder`` | any frontmatter field name | ``tag`` — bucket
            the matches instead of returning a flat list.
        roles / agent: when given, results are intersected with the agent's
            ``read`` grants (§2.2.1). Omit to search unfiltered (the vault
            manager's maintenance pass does this).
        limit: max matches returned (or per bucket when grouping).
    """
    vault_root = Path(vault_root).resolve()
    terms = [t for t in query.split() if t] if query else []
    surfaces = fields or DEFAULT_SURFACES

    base = vault_root
    scope_patterns: Optional[List[str]] = None
    if folder:
        from .paths import safe_join
        base = safe_join(vault_root, folder)
    elif scope:
        # A glob is not a path: scan the vault, filter results after.
        scope_patterns = [scope] if isinstance(scope, str) else list(scope)

    matches: List[Note] = [
        n for n in iter_notes(vault_root, scope=base)
        if not n.error and _note_matches(n, terms, surfaces)
    ]

    if scope_patterns is not None:
        matches = [n for n in matches if scope_matches(scope_patterns, n.path)]

    # grant intersection (§2.2.1)
    if roles is not None and agent is not None:
        matches = [n for n in matches if roles.allows(agent, "read", n.path)]

    # deterministic relevance order (stable: ties keep scan order)
    if terms:
        matches.sort(key=lambda n: -_score(n, terms, surfaces))

    if not group_by:
        return {
            "query": query,
            "count": len(matches),
            "results": [_result(n, terms) for n in matches[:limit]],
        }

    return _group(matches, group_by, limit, terms)


def _result(note: Note, terms: List[str]) -> Dict[str, Any]:
    """Field-agnostic result row.

    No field name is hardcoded (principle 7): the note's frontmatter is
    returned as-is, so a ``type``/``kind`` vault and a ``category``/``format``
    vault both surface their fields without engine changes.
    """
    return {
        "path": note.path,
        "title": note.title,
        "tags": note.tags,
        "frontmatter": note.frontmatter,
        "snippet": _snippet(note.content, terms),
        "links": note.links[:10],
    }


def _snippet(body: str, terms: List[str], window: int = 80,
             max_length: int = 160) -> str:
    """Excerpt around the first matched term, not the body head.

    An agent searching for a term deep in a long note should see the term,
    not the first paragraph. Falls back to the head when the body is short
    or no term matched (e.g. empty-query listings).
    """
    body = body.strip().replace("\n", " ")
    if not terms or len(body) <= max_length:
        return body[:max_length] + ("…" if len(body) > max_length else "")

    for term in terms:
        match = re.search(re.escape(term), body, re.IGNORECASE)
        if match:
            start = max(0, match.start() - window)
            end = min(len(body), match.end() + window)
            prefix = "…" if start > 0 else ""
            suffix = "…" if end < len(body) else ""
            return f"{prefix}{body[start:end]}{suffix}"

    return body[:max_length] + "…"


def _group(notes: List[Note], key: str, limit: int,
           terms: List[str]) -> Dict[str, Any]:
    """Bucket matches by folder or by any frontmatter field.

    ``key`` is a frontmatter field name (config-provided, never hardcoded) or
    the literal ``"folder"`` / ``"tag"``. Multi-valued fields (lists) bucket
    under each value. The engine treats ``type``/``kind``/anything uniformly —
    no field name is special-cased.
    """
    buckets: Dict[str, List[Note]] = {}
    for n in notes:
        if key == "folder":
            values = [n.folder or "(root)"]
        elif key == "tag":
            values = n.tags or ["(untagged)"]
        else:
            raw = n.frontmatter.get(key)
            if isinstance(raw, (list, tuple, set)):
                values = [str(v) for v in raw] or ["(none)"]
            elif raw in (None, "", [], {}):
                values = ["(none)"]
            else:
                values = [str(raw)]

        for value in values:
            buckets.setdefault(value, []).append(n)

    return {
        "query": "",
        "group_by": key,
        "buckets": {
            k: [_result(n, terms) for n in v[:limit]]
            for k, v in sorted(buckets.items())
        },
    }
