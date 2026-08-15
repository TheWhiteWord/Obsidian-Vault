"""Vault maintenance sweep — see docs/guides/maintenance.md.

One tool, three depths — the cron schedule drives the mode:

  delta    — checkpoint over the audit log: check only what changed (and its
             link-neighbourhood), regen INDEX for changed folders, promote
             vocabulary. Fast; runs every tick.
  maintain — delta + full B1 census (dangling links, orphans, malformed
             frontmatter, empty notes, missing required fields).
  optimize — maintain + B2 suggestions (duplicates, missed connections, tag
             normalisation, thin notes). Suggestions only — never auto-applied.

Every run produces a findings artifact (machine interface), distributes
findings as ledger issues (dedupe by key), auto-resolves the manager's own
closed conditions, auto-declines stale suggestions, and prunes old closed
records. ``dry_run``: findings only — no writes, checkpoint not advanced.

The manager never edits content. AUTO actions (INDEX regen, vocabulary
promotion) touch derived artifacts and config; everything else is a finding
for a domain agent to act on.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .config import resolve_config
from .generate import write_index
from .grants import RoleRegistry
from .ownership import owner_of
from .notes import Note, derive_vocabulary, iter_notes
from .paths import relative_to_vault, safe_join
from . import audit
from . import issues
from . import graph as graph_mod

logger = logging.getLogger(__name__)


def _filter_exempted(vault_root: Path, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop findings whose check is exempted for the target path (P12).

    Consulted at finding-GENERATION time: a scope's ``maintenance.exempt`` /
    ``exempt_only`` (resolved via its ``config_chain``) says the check does
    not apply to that path, so the condition never becomes an issue.
    """
    out: List[Dict[str, Any]] = []
    for f in findings:
        target = f.get("path", "")
        if not target:
            continue
        cfg = resolve_config(Path(vault_root).resolve(), safe_join(Path(vault_root).resolve(), target))
        if cfg.exempt_for(f["check"], target):
            continue
        out.append(f)
    return out

#: Audit actions that mutate notes (the change set). ``issue_*`` actions
#: mutate the ledger, not notes — they are never part of the change set.
NOTE_ACTIONS = ("create", "edit", "edit_meta", "delete", "scaffold")

#: Suggestions auto-decline after this many days of non-action.
SUGGESTION_TTL_DAYS = 14

#: Closed records older than this are pruned (same value as issues.PRUNE_TTL_DAYS).
PRUNE_TTL_DAYS = issues.PRUNE_TTL_DAYS

#: Machine artifacts under the state dir.
CHECKPOINT_DIRNAME = "maintain"
CHECKPOINT_FILENAME = "checkpoint.json"
FINDINGS_DIRNAME = "findings"

#: All checks, so auto-resolve can re-run any one of them by name.
CHECKS = ("dangling", "orphan", "malformed", "empty", "missing_field",
          "case_collision")

#: ``missed_connection`` ignores a tag carried by at least this fraction of
#: all notes (or at least this many notes, whichever first) — such tags are
#: structural (project/section labels, e.g. a project's name tag on every
#: note in it), not content-resonance signals. Counting them would make the
#: rule fire on every sibling pair in a tagged project. Fixed + visible, not
#: learned: see docs/design/optimize-suggestions-reprise.md.
MISSING_CONNECTION_PERVASIVE_RATIO = 0.20
MISSING_CONNECTION_PERVASIVE_MIN = 2


class MaintainError(Exception):
    """Raised for invalid maintain requests (unknown mode, no state dir)."""


def _state_dir(vault_root: Path) -> Optional[Path]:
    cfg = resolve_config(Path(vault_root), Path(vault_root))
    state = cfg.state_path()
    if not state:
        return None
    return safe_join(Path(vault_root), state)


def _maintain_dir(vault_root: Path) -> Optional[Path]:
    state = _state_dir(vault_root)
    if state is None:
        return None
    return state / CHECKPOINT_DIRNAME


def checkpoint_path(vault_root: Path) -> Optional[Path]:
    d = _maintain_dir(vault_root)
    if d is None:
        return None
    return d / CHECKPOINT_FILENAME


def _read_checkpoint(vault_root: Path) -> int:
    """Last processed audit-log line number (0 = none yet)."""
    path = checkpoint_path(vault_root)
    if path is None or not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return int(data.get("last_line", 0))
    except (OSError, ValueError, json.JSONDecodeError):
        return 0


def _write_checkpoint(vault_root: Path, last_line: int) -> None:
    path = checkpoint_path(vault_root)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"last_line": last_line}, indent=2) + "\n", encoding="utf-8")


def _audit_entries(vault_root: Path) -> List[Dict[str, Any]]:
    """Every audit entry, oldest first (line order = append order)."""
    log = audit.audit_path(Path(vault_root))
    if log is None or not log.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ---------------------------------------------------------------------------
# The delta pass
# ---------------------------------------------------------------------------

def _change_set(entries: Iterable[Dict[str, Any]], last_line: int) -> Set[str]:
    """Paths of note mutations after the watermark, plus the new watermark.

    Returns (paths, new_last_line). Issue actions are excluded — they mutate
    the ledger, not notes.
    """
    paths: Set[str] = set()
    new_last = last_line
    for index, entry in enumerate(entries):
        line_no = index + 1
        if line_no <= last_line:
            continue
        new_last = line_no
        if entry.get("action") not in NOTE_ACTIONS:
            continue
        path = entry.get("path", "")
        if path:
            paths.add(path)
    return paths, new_last


def _neighbourhood(graph: graph_mod.Graph, paths: Iterable[str]) -> Set[str]:
    """The change set plus its link-neighbourhood.

    A deleted note's former linkers now dangle; a created note may resolve a
    previously-dangling link. Checking the neighbours of every change covers
    both directions.
    """
    out: Set[str] = set(paths)
    for path in paths:
        out |= graph.neighbors(path)
    return out


# ---------------------------------------------------------------------------
# Checks — B1 (correctness)
# ---------------------------------------------------------------------------

def _finding(check: str, path: str, severity: str, detail: str,
             suggestion: str, nature: str = "finding",
             partner: Optional[str] = None) -> Dict[str, Any]:
    return {"check": check, "path": path, "severity": severity,
            "detail": detail, "suggestion": suggestion, "nature": nature,
            "partner": partner}


def _check_dangling(graph: graph_mod.Graph, path: str) -> Optional[Dict[str, Any]]:
    for from_path, label in graph.dangling:
        if from_path == path:
            return _finding(
                "dangling", path, "medium",
                f"Links to [[{label}]] which does not exist",
                "Create the target note or remove the link")
    return None


def _check_orphan(graph: graph_mod.Graph, path: str) -> Optional[Dict[str, Any]]:
    note_paths = {n.path for n in graph.notes}
    if path not in note_paths:
        return None
    if not graph.neighbors(path):
        return _finding(
            "orphan", path, "low",
            "No note links to or from this one",
            "Link it into the web, or delete it if it is dead weight")
    return None


def _check_malformed(note: Note) -> Optional[Dict[str, Any]]:
    if note.error:
        return _finding(
            "malformed", note.path, "high",
            f"Frontmatter failed to parse: {note.error}",
            "Repair the frontmatter block")
    return None


def _check_empty(note: Note) -> Optional[Dict[str, Any]]:
    if not note.error and not note.content.strip():
        return _finding(
            "empty", note.path, "low",
            "Note has no body",
            "Write the content, or delete the note")
    return None


def _check_missing_fields(note: Note, vault_root: Path) -> Optional[Dict[str, Any]]:
    cfg = resolve_config(vault_root, (Path(vault_root) / note.path).parent)
    missing = [f for f in cfg.required_fields if f not in note.frontmatter]
    if missing:
        return _finding(
            "missing_field", note.path, "medium",
            f"Missing required field(s): {', '.join(missing)}",
            "Add the missing frontmatter field(s)")
    return None


def _check_case_collisions(root: Path) -> List[Dict[str, Any]]:
    """Sibling folders whose names differ only by case — the one ambiguity
    case-insensitive resolution cannot pick between.

    One finding per colliding group, targeted at the parent folder. The
    collision is structural, so it lives in the full census (not the delta
    checkpoint pass): it appears when a folder is created or renamed, and
    the next census re-checks it.
    """
    from .constants import SKIP_DIRS

    findings: List[Dict[str, Any]] = []
    for directory, dirnames, _filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        by_case: Dict[str, List[str]] = {}
        for name in dirnames:
            by_case.setdefault(name.casefold(), []).append(name)
        for names in by_case.values():
            if len(names) > 1:
                rel = relative_to_vault(root, Path(directory))
                findings.append(_finding(
                    "case_collision", rel, "medium",
                    "Folders differ only by case: " + ", ".join(sorted(names)),
                    "Rename one — case-insensitive matching treats them "
                    "as one scope"))
    return findings


def _parent_has_case_collision(vault_root: Path, parent_rel: str) -> bool:
    """True when ``parent_rel`` still contains case-colliding siblings.

    The auto-resolve condition for ``case_collision`` findings. Unverifiable
    (path missing/illegal) keeps the issue open rather than closing on a
    guess.
    """
    from .constants import SKIP_DIRS

    try:
        parent = safe_join(vault_root, parent_rel)
    except Exception:  # noqa: BLE001 — cannot verify, keep the issue open
        return True
    if not parent.is_dir():
        return False
    by_case: Dict[str, List[str]] = {}
    for child in parent.iterdir():
        if not child.is_dir() or child.name in SKIP_DIRS:
            continue
        by_case.setdefault(child.name.casefold(), []).append(child.name)
    return any(len(names) > 1 for names in by_case.values())


def run_delta(
    vault_root: Path,
    agent: str,
    roles: RoleRegistry,
    *,
    dry_run: bool,
) -> Dict[str, Any]:
    """The checkpoint pass: check only the change set + neighbourhood."""
    entries = _audit_entries(vault_root)
    last_line = _read_checkpoint(vault_root)
    changed, new_last = _change_set(entries, last_line)

    notes = {n.path: n for n in iter_notes(vault_root)}
    g = graph_mod.build_graph(vault_root, notes.values())

    findings: List[Dict[str, Any]] = []
    scope = _neighbourhood(g, changed) if changed else set()

    for path in sorted(scope):
        note = notes.get(path)
        f = _check_dangling(g, path)
        if f:
            findings.append(f)
        if note is not None:
            if note.error:
                f = _check_malformed(note)
            elif not note.content.strip():
                f = _check_empty(note)
            else:
                f = _check_missing_fields(note, vault_root)
            if f:
                findings.append(f)

    # AUTO: regenerate INDEX for folders touched by the change set.
    indexed: List[str] = []
    folders = sorted({str(Path(p).parent) for p in changed
                      if Path(p).parent != Path(".")})
    if not dry_run:
        for folder in folders:
            if roles.any_grant(agent, folder):
                rel = write_index(vault_root, folder)
                if rel:
                    indexed.append(rel)

    # AUTO: vocabulary promotion (observed → declared past the threshold).
    promoted = _promote_vocabulary(vault_root, agent, roles, dry_run=dry_run)

    return {
        "mode": "delta",
        "changed": sorted(changed),
        "findings": _filter_exempted(vault_root, findings),
        "indexed": indexed,
        "promoted": promoted,
        "last_line": new_last,
    }


# ---------------------------------------------------------------------------
# Vocabulary promotion (AUTO — config grant)
# ---------------------------------------------------------------------------

def _promote_vocabulary(
    vault_root: Path,
    agent: str,
    roles: RoleRegistry,
    *,
    dry_run: bool,
) -> List[str]:
    """Promote observed values past the configured threshold (§3.7).

    Thresholds come from the root config's ``vocabulary`` section:
    ``promote_after_uses`` (default 3). Promotion writes to the nearest
    declaring config — requires the `config` grant (manager has ``**``).
    """
    from .write import _register_value

    root = Path(vault_root).resolve()
    cfg = resolve_config(root, root)
    threshold = int(cfg.vocabulary.get("promote_after_uses", 3) or 3)

    notes = list(iter_notes(root))
    promoted: List[str] = []
    for field in cfg.vocabulary_fields():
        declared = cfg.allowed_values(field) or []
        vocab = derive_vocabulary(notes, field, declared=declared)
        for entry in vocab.get("observed", []):
            if entry["count"] < threshold:
                continue
            if dry_run:
                promoted.append(f"{field}:{entry['name']}")
                continue
            try:
                _register_value(root, root, cfg, agent, roles, field, entry["name"])
                promoted.append(f"{field}:{entry['name']}")
            except Exception as exc:  # noqa: BLE001 — promotion must not kill the pass
                logger.warning("vocabulary promotion failed for %s=%s: %s",
                               field, entry["name"], exc)
    return promoted


# ---------------------------------------------------------------------------
# Full census (B1) and suggestions (B2)
# ---------------------------------------------------------------------------

def _dangling_target_exists(vault_root: Path, src_path: str, label: str) -> bool:
    """True if a dangling link's target resolves to a real file on disk.

    The graph excludes generated files (INDEX) as nodes, so a link to one
    reads as dangling even though the file exists. A link that resolves to any
    on-disk ``.md`` is not a broken link and should not be flagged. Mirrors the
    graph's path-qualified resolution (folder-relative, vault-root-relative,
    suffix match) and falls back to a title-keyed note path.
    """
    root = Path(vault_root).resolve()
    label = label.strip().lstrip("/")
    if not label:
        return False
    parent = str(Path(src_path).parent)
    norm = lambda p: os.path.normpath(p).replace(os.sep, "/")
    candidates = [
        norm(str(Path(parent) / label)),
        norm(label),
    ]
    for cand in candidates:
        for try_p in (cand, cand + ".md"):
            if (root / try_p).is_file():
                return True
    # suffix match (Obsidian folder-hint): note whose path ends with label
    suffix = label.rstrip("/")
    for note in iter_notes(root):
        p = note.path
        if p == suffix or p.endswith("/" + suffix) \
                or p == suffix + ".md" or p.endswith("/" + suffix + ".md"):
            return True
    return False


def run_census(vault_root: Path) -> List[Dict[str, Any]]:
    """Full-vault B1: dangling, orphans, malformed, empty, missing fields,
    case-colliding folders."""
    root = Path(vault_root).resolve()
    notes = list(iter_notes(root))
    g = graph_mod.build_graph(root, notes)
    note_map = {n.path: n for n in notes}

    findings: List[Dict[str, Any]] = []
    findings.extend(_check_case_collisions(root))
    for from_path, label in g.dangling:
        # A link whose target exists on disk is not a broken link — the graph
        # simply does not track generated files (e.g. INDEX) as nodes, so a
        # [[system/INDEX]] reference reads as dangling though the file is real.
        if _dangling_target_exists(root, from_path, label):
            continue
        findings.append(_check_dangling(g, from_path) or _finding(
            "dangling", from_path, "medium",
            "Has a dangling link", "Create the target or remove the link"))

    for note in notes:
        if note.error:
            findings.append(_check_malformed(note))
            continue
        if not note.content.strip():
            findings.append(_check_empty(note))
        missing = _check_missing_fields(note, root)
        if missing:
            findings.append(missing)
        if not g.neighbors(note.path):
            findings.append(_check_orphan(g, note.path))

    return _dedupe(_filter_exempted(root, findings))


def _dedupe(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[Tuple[str, str]] = set()
    out: List[Dict[str, Any]] = []
    for f in findings:
        key = (f["check"], f["path"])
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def _project_unit(path: str) -> str:
    """The project unit a note belongs to, for ``missed_connection``.

    Notes under a per-project root (``work/creative/projects/<name>/``,
    ``work/coding/projects/<name>/``) are grouped by that project folder;
    everything else groups by its top-level tree. Project-unit grouping keeps
    the "pervasive within the project" tag filter scoped to one project, so a
    label universal inside a project is not mistaken for vault-wide resonance.
    """
    parts = path.split("/")
    if len(parts) >= 4 and parts[0] in ("work",) and parts[2] == "projects":
        return "/".join(parts[:4])  # work/<domain>/projects/<name>
    return parts[0] if parts else "."


def _pervasive_tags(
    notes: Iterable[Note], ratio: float, minimum: int
) -> Set[str]:
    """Tags carried by so many notes they carry no connection signal.

    A tag on at least ``max(minimum, int(total * ratio))`` notes is structural
    (a project or section label every note in that project wears), not a
    content-resonance marker. ``missed_connection`` excludes these so it does
    not flag every sibling pair in a tagged project as a "missed link".

    Fixed thresholds (not learned) keep the rule deterministic and visible —
    see docs/design/optimize-suggestions-reprise.md.
    """
    total = 0
    counts: Dict[str, int] = {}
    for note in notes:
        total += 1
        for tag in note.tags:
            counts[tag] = counts.get(tag, 0) + 1
    if total == 0:
        return set()
    threshold = max(minimum, int(total * ratio))
    return {tag for tag, n in counts.items() if n >= threshold}


def run_suggestions(
    vault_root: Path,
    agent: str,
    roles: RoleRegistry,  # noqa: ARG001 — reserved for grant-gated suggestions
) -> List[Dict[str, Any]]:
    """B2 optimization candidates — all suggestions, never auto-applied."""
    root = Path(vault_root).resolve()
    notes = list(iter_notes(root))
    g = graph_mod.build_graph(root, notes)
    note_map = {n.path: n for n in notes}

    findings: List[Dict[str, Any]] = []

    # Duplicates: identical normalised title ANYWHERE in the vault. A title
    # collision breaks title-based wikilinks, so flag it for disambiguation.
    by_title: Dict[str, List[Note]] = {}
    for note in notes:
        key = _normalise(note.title)
        if key:
            by_title.setdefault(key, []).append(note)
    for key, group in by_title.items():
        if len(group) > 1:
            paths = ", ".join(n.path for n in group)
            findings.append(_finding(
                "duplicate", group[0].path, "low",
                f"{len(group)} notes share the title '{key}'",
                f"Disambiguate: same title '{key}' in multiple folders breaks "
                f"[[wikilinks]]. Rename or accept folder-scoped linking. "
                f"Notes: {paths}", nature="suggestion"))

    # Missed connections: within one top-level tree, share >= 2 *content*
    # tags, no link either way. A shared tag is treated as structural noise
    # (and dropped) only when it is pervasive within BOTH notes' own project
    # units -- i.e. a project/section label every note in that project wears,
    # not a content-resonance signal. Comparison stays within the top-level
    # tree so genuine resonance ACROSS projects (e.g. a theme tag shared by
    # two different stories) still surfaces.
    #
    # A proposition an owner has *declined* is permanently recorded
    # (issues.record_decline) and loaded here once per run; any pair in the
    # store is skipped so the engine never re-proposes it and no agent
    # re-assesses it. The store is keyed by note -> [partners] for O(1) lookup,
    # so vault growth adds no per-proposition scan cost. See
    # docs/design/optimize-suggestions-reprise.md.
    declined = issues.load_declined(vault_root)
    by_unit: Dict[str, List[Note]] = {}
    for note in notes:
        by_unit.setdefault(_project_unit(note.path), []).append(note)
    pervasive_by_unit: Dict[str, Set[str]] = {}
    for unit, group in by_unit.items():
        pervasive_by_unit[unit] = _pervasive_tags(
            group, MISSING_CONNECTION_PERVASIVE_RATIO,
            MISSING_CONNECTION_PERVASIVE_MIN)
    by_tree: Dict[str, List[Note]] = {}
    for note in notes:
        tree = note.path.split("/")[0] if "/" in note.path else "."
        by_tree.setdefault(tree, []).append(note)
    for tree, group in by_tree.items():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if b.path in declined.get(a.path, []) or a.path in declined.get(b.path, []):
                    continue  # owner declined this pair before; don't re-propose
                pa = pervasive_by_unit.get(_project_unit(a.path), set())
                pb = pervasive_by_unit.get(_project_unit(b.path), set())
                shared = (set(a.tags) & set(b.tags)) - pa - pb
                if len(shared) < 2:
                    continue
                if b.path in g.neighbors(a.path):
                    continue
                findings.append(_finding(
                    "missed_connection", a.path, "low",
                    f"Shares {len(shared)} tags with {b.path} but is not linked",
                    f"Consider linking: shared tags: {', '.join(sorted(shared))}",
                    nature="suggestion", partner=b.path))

    # Tag normalisation: same tag in multiple case variants.
    by_lower: Dict[str, Set[str]] = {}
    for note in notes:
        for tag in note.tags:
            by_lower.setdefault(tag.lower(), set()).add(tag)
    for lower, variants in by_lower.items():
        if len(variants) > 1:
            first_path = next(n.path for n in notes if lower in
                              {t.lower() for t in n.tags})
            findings.append(_finding(
                "tag_normalization", first_path, "low",
                f"Tag '{lower}' appears as: {', '.join(sorted(variants))}",
                "Pick one spelling and merge", nature="suggestion"))

    # Thin notes: valid frontmatter, near-empty body (excluding generated).
    for note in notes:
        if note.error or note.content.strip():
            continue
        if len(note.content.splitlines()) > 3:
            continue
        findings.append(_finding(
            "thin_note", note.path, "low",
            "Note has very little body content",
            "Expand it, or delete it", nature="suggestion"))

    return _dedupe(_filter_exempted(root, findings))


def _normalise(title: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


# ---------------------------------------------------------------------------
# Distribution + lifecycle
# ---------------------------------------------------------------------------

def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _findings_path(vault_root: Path, run_id: str) -> Optional[Path]:
    d = _maintain_dir(vault_root)
    if d is None:
        return None
    return d / FINDINGS_DIRNAME / f"{run_id}.jsonl"


def _write_findings(vault_root: Path, run_id: str,
                    findings: List[Dict[str, Any]]) -> None:
    path = _findings_path(vault_root, run_id)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for f in findings:
            fh.write(json.dumps(f, default=str) + "\n")


def prune_findings(vault_root: Path,
                   keep_current_run_id: Optional[str] = None) -> int:
    """Delete findings JSONL artifacts; return how many files were removed.

    The findings file is write-only: ``distribute()`` turns the same in-memory
    list into ledger issues, and nothing ever reads the JSONL back. Once a
    run's findings are issues, its file is redundant — the ledger is the
    durable record. ``keep_current_run_id`` spares exactly that run's file
    (so ``result["findings_file"]`` stays a valid path); ``None`` deletes all.
    Undeletable files are skipped, never fatal.
    """
    d = _maintain_dir(Path(vault_root))
    if d is None:
        return 0
    findings_dir = d / FINDINGS_DIRNAME
    if not findings_dir.is_dir():
        return 0
    deleted = 0
    for path in sorted(findings_dir.glob("*.jsonl")):
        if not path.is_file():
            continue
        if keep_current_run_id is not None and path.stem == keep_current_run_id:
            continue
        try:
            path.unlink()
        except OSError:
            continue
        deleted += 1
    return deleted


def distribute(
    vault_root: Path,
    agent: str,
    roles: RoleRegistry,
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Turn findings into ledger issues (dedupe by key, re-open when recurs).

    Every finding becomes an issue record: ``key = <check>|<path>``,
    ``target = path``, ``tags: [maintenance]``. Creating is the escalation
    valve — any registered agent may raise; the audit trail records who.

    Assignee is auto-computed: the derived owner of ``f["path"]`` from
    ``roles.yaml`` write globs (most-specific wins, via ``owner_of``). The
    owning domain agent is the one who can resolve content; routing the
    issue to it on creation is what makes ``assigned_to=me`` a real query
    instead of every agent scanning the whole ledger. A finding whose path
    matches no ownership glob (truly ownerless — near-impossible given the
    default owner holds ``system/**`` and contributors hold their
    ``work/**``) gets ``assignee=None`` and remains manager triage, exactly
    as before.
    """
    write_globs = roles._write_globs
    created: List[str] = []
    skipped: List[str] = []
    reopened: List[str] = []
    for f in findings:
        key = f"{f['check']}|{f['path']}"
        assignee = owner_of(write_globs, f["path"])
        out = issues.create_issue(
            vault_root, agent,
            key=key,
            subject=f"[{f['check']}] {f['path']}",
            detail=f.get("detail", ""),
            target=f["path"],
            nature=f.get("nature", "finding"),
            priority=f.get("severity", "medium"),
            tags=["maintenance"],
            assignee=assignee,
            partner=f.get("partner"),
        )
        (created if out["result"] == issues.RESULT_CREATED
         else reopened if out["result"] == issues.RESULT_REOPENED
         else skipped).append(key)
    return {"created": created, "reopened": reopened, "skipped": skipped}


def auto_resolve(
    vault_root: Path,
    agent: str,
    roles: RoleRegistry,
) -> Dict[str, Any]:
    """Close the manager's own issues whose condition has cleared.

    Only touches records this agent raised (``raised_by`` = itself, tagged
    ``maintenance``). Suggestions open past the TTL auto-decline (non-action
    = implicit decline). Grant-checked: resolve requires write/meta over the
    target, which the manager holds vault-wide.
    """
    open_issues = [
        r for r in issues.list_issues(vault_root, state="open")
        if r.get("raised_by") == agent and "maintenance" in (r.get("tags") or [])
    ]

    # Build the current graph once for condition re-checks.
    notes = list(iter_notes(vault_root))
    g = graph_mod.build_graph(vault_root, notes)
    note_map = {n.path: n for n in notes}

    resolved: List[str] = []
    declined: List[str] = []
    for record in open_issues:
        key = record["key"]
        target = record.get("target", "")
        # Grant-kind check (write|meta over the target), not an operation
        # check: `write` and `meta` are grant kinds, not operations — the
        # operations that exercise them are edit / edit_meta.
        grants = roles.get(agent)
        if not (grants.matches("write", target)
                or grants.matches("meta", target)):
            continue  # cannot close what we cannot touch — leave for the owner

        if record.get("nature") == "suggestion":
            # A suggestion whose check/target is now exempted closes
            # immediately (P12) — the scope declared it by-design, so it
            # should not linger the full 14-day TTL.
            check = key.split("|", 1)[0]
            if _exempt(vault_root, target, check):
                out = issues.resolve_issue(
                    vault_root, agent, key, state="resolved",
                    reason="scope-exempted")
                if out["result"] == issues.RESULT_CLOSED:
                    resolved.append(key)
                continue
            created_at = record.get("created_at", "")
            try:
                age_days = (datetime.now(timezone.utc)
                            - datetime.fromisoformat(created_at)).days
            except ValueError:
                age_days = 0
            if age_days >= SUGGESTION_TTL_DAYS:
                out = issues.resolve_issue(
                    vault_root, agent, key, state="declined",
                    reason="non-action = implicit decline")
                if out["result"] == issues.RESULT_CLOSED:
                    declined.append(key)
            continue

        # Finding: re-run the check named by the key prefix on the target.
        check = key.split("|", 1)[0]
        still_open = _condition_holds(check, target, g, note_map, vault_root)
        if not still_open:
            out = issues.resolve_issue(
                vault_root, agent, key, state="resolved",
                reason="condition cleared")
            if out["result"] == issues.RESULT_CLOSED:
                resolved.append(key)

    pruned = issues.prune_issues(vault_root, agent, ttl_days=PRUNE_TTL_DAYS)
    return {"resolved": resolved, "declined": declined, "pruned": pruned}


def _condition_holds(
    check: str,
    target: str,
    g: graph_mod.Graph,
    note_map: Dict[str, Note],
    vault_root: Path,
) -> bool:
    """Does the finding still exist? (True = keep the issue open.)

    An exempted check/target (P12: the scope declared the finding by-design
    via ``maintenance.exempt``) is treated as cleared — the engine no longer
    counts that condition, so ``auto_resolve`` may close the open issue.
    """
    if _exempt(vault_root, target, check):
        return False
    if check == "dangling":
        return _check_dangling(g, target) is not None
    if check == "orphan":
        return _check_orphan(g, target) is not None
    note = note_map.get(target)
    if check == "malformed":
        return bool(note and note.error)
    if check == "empty":
        return bool(note and not note.error and not note.content.strip())
    if check == "missing_field":
        return _check_missing_fields(note, vault_root) is not None if note else False
    if check == "case_collision":
        return _parent_has_case_collision(vault_root, target)
    # Unknown check: keep it open rather than close on a guess.
    return True


def _exempt(vault_root: Path, target: str, check: str) -> bool:
    """Is ``check`` exempted for ``target`` under the nearest scope config?

    Resolves the merged ``maintenance`` section via ``config_chain`` on the
    note's folder and tests the check's globs against the vault-relative path
    with the shared ``path_matches`` matcher.
    """
    try:
        cfg = resolve_config(Path(vault_root).resolve(), safe_join(Path(vault_root).resolve(), target))
    except Exception:
        # A path we cannot resolve a config for is never treated as exempt —
        # default to checking it rather than silently suppressing a finding.
        return False
    return cfg.exempt_for(check, target)


# ---------------------------------------------------------------------------
# The sweep
# ---------------------------------------------------------------------------

def run_maintenance(
    vault_root: Path,
    agent: str,
    roles: RoleRegistry,
    *,
    mode: str = "maintain",
    distribute_issues: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Run the sweep. ``dry_run`` writes nothing, advances nothing."""
    if mode not in ("delta", "maintain", "optimize"):
        raise MaintainError(f"unknown mode {mode!r}; valid: delta|maintain|optimize")

    result: Dict[str, Any] = {"mode": mode, "dry_run": dry_run}

    delta = run_delta(vault_root, agent, roles, dry_run=dry_run)
    result["delta"] = {
        "changed": delta["changed"],
        "indexed": delta["indexed"],
        "promoted": delta["promoted"],
    }

    findings: List[Dict[str, Any]] = list(delta["findings"])
    if mode in ("maintain", "optimize"):
        findings = _dedupe(findings + run_census(vault_root))
    if mode == "optimize":
        findings = _dedupe(findings + run_suggestions(vault_root, agent, roles))

    result["findings"] = findings

    if dry_run:
        # Rehearsal: report what would happen, change nothing.
        result["findings_file"] = None
        result["distribution"] = {
            "would_create": sum(1 for f in findings
                                if f.get("nature", "finding") == "finding"),
            "would_suggest": sum(1 for f in findings
                                 if f.get("nature") == "suggestion"),
        }
        return result

    run_id = _run_id()
    _write_findings(vault_root, run_id, findings)
    result["findings_file"] = (
        relative_to_vault(Path(vault_root), _findings_path(vault_root, run_id))
        if _findings_path(vault_root, run_id) else None)

    if distribute_issues and findings:
        result["distribution"] = distribute(vault_root, agent, roles, findings)
    else:
        result["distribution"] = {"created": [], "reopened": [], "skipped": []}

    result["lifecycle"] = auto_resolve(vault_root, agent, roles)

    # Advance the watermark only after a full successful run.
    last_line = delta["last_line"]
    _write_checkpoint(vault_root, last_line)
    result["checkpoint"] = last_line

    # This run's findings are now ledger issues, so every PRIOR run's
    # write-only JSONL is redundant. Keep this run's file: it is the path
    # reported in result["findings_file"] (and, when distribution is off,
    # the sole record of the run). Never reached on dry_run.
    result["findings_pruned"] = prune_findings(vault_root,
                                               keep_current_run_id=run_id)
    return result
