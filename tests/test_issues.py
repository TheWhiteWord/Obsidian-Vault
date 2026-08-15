"""Issue ledger tests.

The ledger is machinery under the state dir: records, not notes. These tests
cover the lifecycle (create / dedupe / re-escalation / resolve / prune), the
list filters, and the no-pollution guarantee.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from vault import audit
from vault import issues
from vault.notes import iter_notes


def _t(days_ago: int) -> str:
    """An ISO timestamp ``days_ago`` days in the past (UTC)."""
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(
        timespec="seconds")


KEY = "dangling|work/creative/projects/a.md"


@pytest.fixture
def ledger(vault_with_roles: Path) -> Path:
    """The ledger folder for the fixture vault."""
    return vault_with_roles / ".state" / "issues"


class TestCreateAndDedupe:
    def test_create_writes_record_and_audits(self, vault_with_roles, ledger):
        result = issues.create_issue(
            vault_with_roles, "vault_manager",
            key=KEY, subject="[dangling] work/creative/projects/a.md",
            detail="Links to [[Missing Note]]",
            target="work/creative/projects/a.md",
            priority="high", tags=["maintenance"],
        )
        assert result["result"] == "created"

        path = ledger / issues._slug(KEY)
        assert path.exists()
        rec = json.loads(path.read_text(encoding="utf-8"))
        assert rec["key"] == KEY
        assert rec["state"] == "open"
        assert rec["nature"] == "finding"
        assert rec["priority"] == "high"
        assert rec["tags"] == ["maintenance"]
        assert rec["raised_by"] == "vault_manager"
        assert rec["resolved_at"] is None

        entries = audit.read_entries(vault_with_roles, action="issue_create")
        assert len(entries) == 1
        assert entries[0]["path"] == "work/creative/projects/a.md"
        assert entries[0]["agent"] == "vault_manager"

    def test_dedupe_same_key_returns_exists(self, vault_with_roles):
        issues.create_issue(vault_with_roles, "vault_manager",
                            key=KEY, subject="s", detail="d",
                            target="work/creative/projects/a.md")
        second = issues.create_issue(vault_with_roles, "vault_manager",
                                     key=KEY, subject="s", detail="d",
                                     target="work/creative/projects/a.md")
        assert second["result"] == "exists"
        # still exactly one record, one create in the audit trail
        assert len(list(issues.issues_dir(vault_with_roles).glob("*.json"))) == 1
        creates = audit.read_entries(vault_with_roles, action="issue_create")
        assert len(creates) == 1

    def test_key_slug_is_deterministic_and_unique(self, vault_with_roles):
        assert issues._slug(KEY) == issues._slug(KEY)
        other = issues._slug("orphan|SYSTEM/handbook/design.md")
        assert other != issues._slug(KEY)
        # keys with the same words but different separators still differ
        assert issues._slug("a|b/c") != issues._slug("a/b|c")


class TestLifecycle:
    def test_resolve_closes_with_reason(self, vault_with_roles):
        issues.create_issue(vault_with_roles, "vault_manager",
                            key=KEY, subject="s", detail="d",
                            target="work/creative/projects/a.md")
        out = issues.resolve_issue(
            vault_with_roles, "vault_manager", KEY,
            state="resolved", reason="condition cleared")
        assert out["result"] == "closed"

        rec = issues.read_issue(vault_with_roles, KEY)
        assert rec["state"] == "resolved"
        assert rec["resolved_by"] == "vault_manager"
        assert rec["reason"] == "condition cleared"
        assert rec["resolved_at"] is not None

        entries = audit.read_entries(vault_with_roles, action="issue_resolve")
        assert entries[0]["state"] == "resolved"

    def test_resolve_missing_key(self, vault_with_roles):
        out = issues.resolve_issue(vault_with_roles, "vault_manager", KEY)
        assert out["result"] == "not_found"

    def test_resolve_already_closed(self, vault_with_roles):
        issues.create_issue(vault_with_roles, "vault_manager",
                            key=KEY, subject="s", detail="d", target="a.md")
        issues.resolve_issue(vault_with_roles, "vault_manager", KEY)
        # Re-asserting the SAME closed state is idempotent.
        out = issues.resolve_issue(vault_with_roles, "vault_manager", KEY,
                                   state="resolved")
        assert out["result"] == "already_closed"
        # An explicit owner override to a different closed state is allowed
        # (e.g. decline a previously-resolved suggestion).
        out2 = issues.resolve_issue(vault_with_roles, "vault_manager", KEY,
                                    state="declined", reason="reconsider")
        assert out2["result"] == "closed"

    def test_resolve_rejects_invalid_closure_state(self, vault_with_roles):
        issues.create_issue(vault_with_roles, "vault_manager",
                            key=KEY, subject="s", detail="d", target="a.md")
        with pytest.raises(issues.IssueError):
            issues.resolve_issue(vault_with_roles, "vault_manager", KEY,
                                 state="open")

    def test_create_rejects_invalid_nature_or_priority(self, vault_with_roles):
        with pytest.raises(issues.IssueError):
            issues.create_issue(vault_with_roles, "vault_manager",
                                key=KEY, subject="s", detail="d",
                                target="a.md", nature="bogus")
        with pytest.raises(issues.IssueError):
            issues.create_issue(vault_with_roles, "vault_manager",
                                key=KEY, subject="s", detail="d",
                                target="a.md", priority="urgent")

    def test_re_escalation_reopens_same_key(self, vault_with_roles):
        issues.create_issue(vault_with_roles, "vault_manager",
                            key=KEY, subject="s", detail="d",
                            target="work/creative/projects/a.md")
        issues.resolve_issue(vault_with_roles, "vault_manager", KEY,
                             reason="fixed")

        reopened = issues.create_issue(vault_with_roles, "vault_manager",
                                       key=KEY, subject="s", detail="d",
                                       target="work/creative/projects/a.md")
        assert reopened["result"] == "reopened"

        rec = issues.read_issue(vault_with_roles, KEY)
        assert rec["state"] == "open"
        assert rec["resolved_at"] is None
        assert rec["reason"] is None
        # history stays attached to one ticket: created_at preserved
        assert rec["created_at"] is not None
        # one create + one resolve + one reopen in the trail
        assert len(audit.read_entries(vault_with_roles, action="issue_create")) == 1
        assert len(audit.read_entries(vault_with_roles, action="issue_reopen")) == 1


class TestList:
    def _seed(self, vault_with_roles):
        issues.create_issue(vault_with_roles, "vault_manager",
                            key="a|one", subject="One", detail="d",
                            target="work/creative/projects/a.md",
                            priority="high", tags=["maintenance"])
        issues.create_issue(vault_with_roles, "vault_manager",
                            key="b|two", subject="Two", detail="d",
                            target="work/coding/b.md",
                            priority="low", nature="suggestion")
        issues.create_issue(vault_with_roles, "researcher",
                            key="c|three", subject="Three", detail="d",
                            target="system/**", tags=["research"])

    def test_list_all_newest_first(self, vault_with_roles):
        self._seed(vault_with_roles)
        out = issues.list_issues(vault_with_roles)
        assert len(out) == 3
        # sorted by created_at desc — "c|three" created last
        assert out[0]["key"] == "c|three"

    def test_list_filters(self, vault_with_roles):
        self._seed(vault_with_roles)
        assert [i["key"] for i in issues.list_issues(vault_with_roles, state="open")] \
            == ["c|three", "b|two", "a|one"]
        assert [i["key"] for i in issues.list_issues(
            vault_with_roles, nature="suggestion")] == ["b|two"]
        assert [i["key"] for i in issues.list_issues(
            vault_with_roles, priority="high")] == ["a|one"]
        assert [i["key"] for i in issues.list_issues(
            vault_with_roles, raised_by="researcher")] == ["c|three"]
        assert [i["key"] for i in issues.list_issues(
            vault_with_roles, tags=["maintenance"])] == ["a|one"]

    def test_list_filters_by_target_glob(self, vault_with_roles):
        self._seed(vault_with_roles)
        # concrete path under the glob
        assert [i["key"] for i in issues.list_issues(
            vault_with_roles, target="work/creative/**")] == ["a|one"]
        # scope-glob target matches a glob filter ("system/**" is system-wide)
        assert [i["key"] for i in issues.list_issues(
            vault_with_roles, target="system/**")] == ["c|three"]

    def test_list_excludes_closed_by_default_filter(self, vault_with_roles):
        self._seed(vault_with_roles)
        issues.resolve_issue(vault_with_roles, "vault_manager", "a|one")
        out = issues.list_issues(vault_with_roles, state="open")
        assert "a|one" not in [i["key"] for i in out]
        assert len(issues.list_issues(vault_with_roles, state="resolved")) == 1


class TestAssignment:
    """Assignee field + claim transition (P10, 2026-08-08)."""

    def _create(self, vault, key=KEY, assignee=None):
        return issues.create_issue(
            vault, "vault_manager",
            key=key, subject="s", detail="d",
            target="work/creative/projects/a.md",
            assignee=assignee,
        )

    def test_create_without_assignee_defaults_null(self, vault_with_roles):
        self._create(vault_with_roles)
        rec = issues.read_issue(vault_with_roles, KEY)
        assert rec["assignee"] is None
        assert rec["claimed_by"] is None

    def test_create_with_assignee_stores_it(self, vault_with_roles):
        self._create(vault_with_roles, assignee="creative")
        rec = issues.read_issue(vault_with_roles, KEY)
        assert rec["assignee"] == "creative"

    def test_create_rejects_blank_assignee(self, vault_with_roles):
        with pytest.raises(issues.IssueError):
            self._create(vault_with_roles, assignee="   ")
        with pytest.raises(issues.IssueError):
            self._create(vault_with_roles, assignee="")

    def test_assign_sets_assignee_on_open(self, vault_with_roles):
        self._create(vault_with_roles)  # open, assignee null
        out = issues.assign_issue(vault_with_roles, "vault_manager",
                                  KEY, "creative")
        assert out["result"] == "assigned"
        assert out["assignee"] == "creative"
        rec = issues.read_issue(vault_with_roles, KEY)
        assert rec["assignee"] == "creative"
        assert rec["state"] == "open"  # assign leaves state untouched
        entries = audit.read_entries(vault_with_roles, action="issue_assign")
        assert len(entries) == 1

    def test_assign_reassigns_in_progress(self, vault_with_roles):
        self._create(vault_with_roles)
        issues.resolve_issue(vault_with_roles, "creative", KEY,
                             state="in_progress")
        out = issues.assign_issue(vault_with_roles, "vault_manager",
                                  KEY, "system")
        assert out["result"] == "assigned"
        rec = issues.read_issue(vault_with_roles, KEY)
        assert rec["assignee"] == "system"
        assert rec["state"] == "in_progress"
        assert rec["claimed_by"] == "creative"  # holder preserved

    def test_assign_refuses_closed(self, vault_with_roles):
        self._create(vault_with_roles)
        issues.resolve_issue(vault_with_roles, "creative", KEY,
                             state="resolved", reason="done")
        out = issues.assign_issue(vault_with_roles, "vault_manager",
                                  KEY, "creative")
        assert out["result"] == "already_closed"

    def test_assign_missing_key(self, vault_with_roles):
        out = issues.assign_issue(vault_with_roles, "vault_manager",
                                  "no|such", "creative")
        assert out["result"] == "not_found"

    def test_assign_rejects_blank_assignee(self, vault_with_roles):
        self._create(vault_with_roles)
        with pytest.raises(issues.IssueError):
            issues.assign_issue(vault_with_roles, "vault_manager",
                                KEY, "  ")
        with pytest.raises(issues.IssueError):
            issues.assign_issue(vault_with_roles, "vault_manager",
                                KEY, "")

    def test_list_filter_by_assignee(self, vault_with_roles):
        self._create(vault_with_roles, key="a|one", assignee="creative")
        self._create(vault_with_roles, key="b|two")
        assert [i["key"] for i in issues.list_issues(
            vault_with_roles, assigned_to="creative")] == ["a|one"]
        assert [i["key"] for i in issues.list_issues(
            vault_with_roles, assigned_to="nobody")] == []

    def test_claim_sets_claimed_by_not_resolved_by(self, vault_with_roles):
        self._create(vault_with_roles)
        out = issues.resolve_issue(vault_with_roles, "creative", KEY,
                                   state="in_progress")
        assert out["result"] == "claimed"
        rec = issues.read_issue(vault_with_roles, KEY)
        assert rec["state"] == "in_progress"
        assert rec["claimed_by"] == "creative"
        assert rec["resolved_by"] is None
        assert rec["resolved_at"] is None
        entries = audit.read_entries(vault_with_roles, action="issue_claim")
        assert len(entries) == 1

    def test_in_progress_dedupes_as_open(self, vault_with_roles):
        self._create(vault_with_roles)
        issues.resolve_issue(vault_with_roles, "creative", KEY,
                             state="in_progress")
        out = issues.create_issue(vault_with_roles, "vault_manager",
                                  key=KEY, subject="s", detail="d",
                                  target="work/creative/projects/a.md")
        assert out["result"] == "exists"

    def test_close_after_claim_keeps_holder(self, vault_with_roles):
        self._create(vault_with_roles)
        issues.resolve_issue(vault_with_roles, "creative", KEY,
                             state="in_progress")
        out = issues.resolve_issue(vault_with_roles, "creative", KEY,
                                   state="resolved", reason="done")
        assert out["result"] == "closed"
        rec = issues.read_issue(vault_with_roles, KEY)
        assert rec["state"] == "resolved"
        assert rec["claimed_by"] == "creative"
        assert rec["resolved_by"] == "creative"

    def test_reopen_preserves_assignee_and_claimed_by(self, vault_with_roles):
        self._create(vault_with_roles, assignee="creative")
        issues.resolve_issue(vault_with_roles, "creative", KEY,
                             state="in_progress")
        issues.resolve_issue(vault_with_roles, "creative", KEY,
                             state="resolved", reason="done")
        reopened = issues.create_issue(
            vault_with_roles, "vault_manager",
            key=KEY, subject="s", detail="d",
            target="work/creative/projects/a.md")
        assert reopened["result"] == "reopened"
        rec = issues.read_issue(vault_with_roles, KEY)
        assert rec["state"] == "open"
        assert rec["assignee"] == "creative"
        assert rec["claimed_by"] == "creative"
        assert rec["resolved_by"] is None


class TestPrune:
    def test_prune_ttl_is_seven_days(self):
        """The closed-record pruning contract is locked at 7 days."""
        assert issues.PRUNE_TTL_DAYS == 7

    def test_prune_deletes_only_old_closed(self, vault_with_roles):
        issues.create_issue(vault_with_roles, "vault_manager",
                            key="old|one", subject="Old", detail="d",
                            target="a.md")
        issues.resolve_issue(vault_with_roles, "vault_manager", "old|one")

        # backdate the closed record beyond the TTL
        rec_path = issues.issues_dir(vault_with_roles) / issues._slug("old|one")
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        rec["resolved_at"] = _t(60)
        rec["updated_at"] = _t(60)
        rec_path.write_text(json.dumps(rec), encoding="utf-8")

        issues.create_issue(vault_with_roles, "vault_manager",
                            key="open|two", subject="Open", detail="d",
                            target="b.md")

        pruned = issues.prune_issues(vault_with_roles, "vault_manager",
                                     ttl_days=30)
        assert pruned == ["old|one"]
        assert not rec_path.exists()
        # open records survive
        assert issues.read_issue(vault_with_roles, "open|two") is not None
        # audit records the prune
        assert audit.read_entries(vault_with_roles, action="issue_prune")

    def test_prune_keeps_recent_closed(self, vault_with_roles):
        issues.create_issue(vault_with_roles, "vault_manager",
                            key="recent|one", subject="Recent", detail="d",
                            target="a.md")
        issues.resolve_issue(vault_with_roles, "vault_manager", "recent|one")
        assert issues.prune_issues(vault_with_roles, "vault_manager",
                                   ttl_days=30) == []
        assert issues.read_issue(vault_with_roles, "recent|one") is not None


class TestNoPollution:
    def test_ledger_is_invisible_to_note_scan(self, vault_with_roles):
        issues.create_issue(vault_with_roles, "vault_manager",
                            key=KEY, subject="s", detail="d",
                            target="work/creative/projects/a.md")
        paths = [n.path for n in iter_notes(vault_with_roles)]
        assert all(not p.startswith(".state/") for p in paths)

    def test_ledger_respects_relocated_state_dir(self, tmp_path):
        """A PARA-style vault with state at Archive/_state keeps the ledger there."""
        def _write(path: Path, text: str) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text.lstrip(), encoding="utf-8")

        _write(tmp_path / ".vault/config.yaml", """
fields:
  category: { required: true, vocabulary: true, allowed: [project, area] }
paths:
  state: Archive/_state
""")
        out = issues.create_issue(tmp_path, "default",
                                  key=KEY, subject="s", detail="d",
                                  target="Projects/launch.md")
        assert out["result"] == "created"
        assert (tmp_path / "Archive/_state/issues").exists()
        assert issues.read_issue(tmp_path, KEY)["target"] == "Projects/launch.md"
