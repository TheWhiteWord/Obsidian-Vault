"""Declined propositions are permanently recorded and never re-proposed.

A `missed_connection` an owner declines is written to the engine store
(``.state/maintenance/declined.yaml``) and the engine skips it on every
subsequent sweep, so agents never re-assess it. Decline is permanent: the
issue does not re-open. Re-opening/resolving the issue clears the store entry.

Self-contained vaults (no fixture coupling) so the behaviour is deterministic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vault import maintain, issues


def _seed(v: Path) -> None:
    (v / ".vault").mkdir(parents=True)
    (v / ".vault/config.yaml").write_text(
        "fields:\n"
        "  type: {required: true, allowed: [note, work]}\n"
        "  kind: {required: true, multi: true, allowed: [concept]}\n"
        "  status: {required: true, allowed: [draft]}\n"
        "  tags: {required: true, multi: true}\n"
        "  created: {required: true, format: date}\n",
        encoding="utf-8",
    )


def _note(v: Path, path: str, tags) -> None:
    p = v / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\ntype: note\nkind: [concept]\nstatus: draft\n"
        f"tags: [{', '.join(tags)}]\ncreated: 2026-08-02\n---\nBody.\n",
        encoding="utf-8",
    )


def _raise_and_decline(v: Path, agent: str = "vault_manager"):
    """Raise a missed_connection between two specific-tag notes, then decline it."""
    _seed(v)
    _note(v, "work/creative/projects/alpha/a.md", ["grief", "memory"])
    _note(v, "work/creative/projects/beta/b.md", ["grief", "memory"])
    sugg = maintain.run_suggestions(v, agent, None)
    mc = [f for f in sugg if f["check"] == "missed_connection"]
    assert mc, "expected a missed_connection to raise"
    f = mc[0]
    key = f"missed_connection|{f['path']}"
    # distribute the finding into an issue record (what run_maintenance does)
    issues.create_issue(
        v, agent, key=key, subject=f"[{f['check']}] {f['path']}",
        detail=f.get("detail", ""), target=f["path"], nature="suggestion",
        priority="low", tags=["maintenance"], partner=f.get("partner"))
    out = issues.resolve_issue(v, agent, key, state="declined", reason="owner: not a connection")
    assert out["result"] == "closed"
    return key, f["path"], f["partner"]


class TestDeclinedProposition:
    def test_decline_records_pair_and_suppresses(self, tmp_path: Path):
        v = tmp_path
        key, a, b = _raise_and_decline(v)
        # store carries the pair both ways
        store = issues.load_declined(v)
        assert b in store.get(a, [])
        assert a in store.get(b, [])
        # engine no longer proposes it
        sugg2 = maintain.run_suggestions(v, "vault_manager", None)
        mc2 = [f for f in sugg2 if f["check"] == "missed_connection"]
        assert not any(f["path"] == a for f in mc2), "declined pair must not re-propose"

    def test_decline_is_permanent_no_reopen(self, tmp_path: Path):
        v = tmp_path
        key, a, _ = _raise_and_decline(v)
        # second raise attempt must NOT re-open the declined issue
        out = issues.create_issue(
            v, "vault_manager", key=key, subject="x", detail="d",
            target=a, nature="suggestion", priority="low", tags=["maintenance"])
        assert out["result"] == "exists"
        rec = issues.read_issue(v, key)
        assert rec["state"] == "declined"

    def test_reopen_clears_store_entry(self, tmp_path: Path):
        v = tmp_path
        key, a, b = _raise_and_decline(v)
        # owner links the notes (or otherwise resolves) -> store entry cleared.
        out = issues.resolve_issue(v, "vault_manager", key, state="resolved",
                                   reason="linked the notes")
        assert out["result"] == "closed"
        store = issues.load_declined(v)
        assert b not in store.get(a, [])

    def test_decline_store_is_non_verbose_one_file(self, tmp_path: Path):
        # one vault-wide store, not one file per note
        v = tmp_path
        _raise_and_decline(v)
        store_path = (issues._maintain_store_path(v))
        assert store_path is not None and store_path.exists()
        # content is a compact note -> [partners] map
        import yaml
        data = yaml.safe_load(store_path.read_text(encoding="utf-8"))
        assert isinstance(data.get("declined"), dict)
