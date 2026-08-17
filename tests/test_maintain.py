"""Maintenance sweep tests.

Covers: the delta pass (checkpoint over the audit log), the B1 census, B2
suggestions, distribution (findings → ledger issues, dedupe by key),
auto-resolve / auto-decline / prune, dry-run (no writes), and the guarantee
that the sweep works on any vault layout.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from vault import audit
from vault import issues
from vault import maintain
from vault.grants import load_roles
from vault.write import write_note


def _t(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(
        timespec="seconds")


def _fm(**kw):
    base = {"type": "note", "kind": ["note"], "status": "draft",
            "tags": ["t"], "created": "2026-08-02"}
    base.update(kw)
    return base


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip(), encoding="utf-8")


@pytest.fixture
def roles(vault_with_roles):
    return load_roles(vault_with_roles)


class TestCaseCollision:
    """Sibling folders differing only by case — the one ambiguity
    case-insensitive resolution cannot pick between."""

    def test_census_flags_case_colliding_folders(self, vault):
        (vault / "CREATIVE" / "ideas").mkdir(parents=True)
        (vault / "CREATIVE" / "Ideas").mkdir(parents=True)

        findings = maintain.run_census(vault)
        collisions = [f for f in findings if f["check"] == "case_collision"]
        assert len(collisions) == 1
        assert collisions[0]["path"] == "CREATIVE"
        assert "ideas" in collisions[0]["detail"]
        assert "Ideas" in collisions[0]["detail"]

    def test_census_stays_quiet_without_collisions(self, vault):
        findings = maintain.run_census(vault)
        assert not any(f["check"] == "case_collision" for f in findings)

    def test_auto_resolve_condition_tracks_the_fix(self, vault):
        (vault / "CREATIVE" / "ideas").mkdir(parents=True)
        (vault / "CREATIVE" / "Ideas").mkdir(parents=True)
        assert maintain._parent_has_case_collision(vault, "CREATIVE")
        (vault / "CREATIVE" / "Ideas").rmdir()
        assert not maintain._parent_has_case_collision(vault, "CREATIVE")


class TestDeltaPass:
    def test_delta_detects_new_changes_only(self, vault_with_roles, roles):
        write_note(vault_with_roles, "system", roles,
                   path="SYSTEM/HANDBOOK/broken.md",
                   frontmatter=_fm(), body="See [[missing-target]]")

        out = maintain.run_delta(vault_with_roles, "vault_manager", roles,
                                 dry_run=True)
        assert "SYSTEM/HANDBOOK/broken.md" in out["changed"]
        checks = {f["check"] for f in out["findings"]}
        assert "dangling" in checks
        # checkpoint NOT advanced in dry-run
        cp = maintain.checkpoint_path(vault_with_roles)
        assert cp is None or not cp.exists()

    def test_delta_advances_watermark_after_success(self, vault_with_roles, roles):
        write_note(vault_with_roles, "system", roles,
                   path="SYSTEM/HANDBOOK/broken.md",
                   frontmatter=_fm(), body="See [[missing-target]]")

        out = maintain.run_maintenance(vault_with_roles, "vault_manager", roles,
                                       mode="delta", distribute_issues=False)
        assert out["checkpoint"] > 0
        cp = maintain.checkpoint_path(vault_with_roles)
        assert cp.exists()
        assert json.loads(cp.read_text())["last_line"] == out["checkpoint"]

        # A second run with no new writes sees an empty change set.
        out2 = maintain.run_maintenance(vault_with_roles, "vault_manager", roles,
                                        mode="delta", distribute_issues=False)
        assert out2["delta"]["changed"] == []

    def test_delta_excludes_issue_actions_from_change_set(self, vault_with_roles, roles):
        # Simulate a manager issue-create landing in the audit trail after the
        # watermark: it must NOT be treated as a note change.
        audit.record(vault_with_roles, "vault_manager", "issue_create",
                     "SYSTEM/HANDBOOK/broken.md", key="dangling|broken")
        out = maintain.run_delta(vault_with_roles, "vault_manager", roles,
                                 dry_run=True)
        assert out["changed"] == []

    def test_delta_indexes_changed_folders(self, vault_with_roles, roles):
        write_note(vault_with_roles, "system", roles,
                   path="SYSTEM/HANDBOOK/fresh.md",
                   frontmatter=_fm(), body="New note.")
        out = maintain.run_delta(vault_with_roles, "vault_manager", roles,
                                 dry_run=False)
        assert any("SYSTEM/HANDBOOK" in p for p in out["indexed"])


class TestCensus:
    def test_census_finds_all_b1_classes(self, vault_with_roles):
        # dangling (body links to missing), empty, malformed, orphan
        _write(vault_with_roles / "SYSTEM/KNOWLEDGE/dangling.md", """
---
type: knowledge
kind: [reference]
status: reference
tags: [x]
created: 2026-08-02
source: https://x.example
retrieved: 2026-08-02
---
See [[no-such-note]].
""")
        _write(vault_with_roles / "SYSTEM/KNOWLEDGE/empty.md", """
---
type: knowledge
kind: [reference]
status: reference
tags: [x]
created: 2026-08-02
source: https://x.example
retrieved: 2026-08-02
---
""")
        _write(vault_with_roles / "SYSTEM/KNOWLEDGE/bad.md",
               "---\nthis: [is: not: valid\n---\nBody.\n")
        _write(vault_with_roles / "SYSTEM/KNOWLEDGE/isolated.md", """
---
type: knowledge
kind: [reference]
status: reference
tags: [x]
created: 2026-08-02
source: https://x.example
retrieved: 2026-08-02
---
Alone in the vault.
""")

        findings = maintain.run_census(vault_with_roles)
        by_path = {(f["check"], f["path"]) for f in findings}
        assert ("dangling", "SYSTEM/KNOWLEDGE/dangling.md") in by_path
        assert ("empty", "SYSTEM/KNOWLEDGE/empty.md") in by_path
        assert ("malformed", "SYSTEM/KNOWLEDGE/bad.md") in by_path
        # isolated.md links to nothing and nothing links to it
        assert any(f["check"] == "orphan" and f["path"].endswith("isolated.md")
                   for f in findings)


class TestStaleIndex:
    def test_census_flags_index_missing_a_new_child(self, vault_with_roles, roles):
        # Simulate the pre-fix drift: a folder exists on disk but its parent
        # INDEX predates it and never listed it. CREATIVE/PHILOSOPHY is a
        # seeded fixture folder; we write a stale CREATIVE/INDEX.md that
        # predates the new branch.
        # Seed a stale parent INDEX as it would have looked before the child
        # was created (no mention of NEWBRANCH).
        (vault_with_roles / "CREATIVE/INDEX.md").write_text(
            "<!-- generated: do not edit -->\n# CREATIVE\n"
            "**0 notes**\n## Folders\n- [[PHILOSOPHY]]\n",
            encoding="utf-8")
        (vault_with_roles / "CREATIVE/NEWBRANCH").mkdir(parents=True)

        findings = maintain.run_census(vault_with_roles)
        stale = [f for f in findings if f["check"] == "stale_index"]
        assert stale, "expected a stale_index finding for CREATIVE"
        assert any(f["path"] == "CREATIVE" for f in stale)
        assert "NEWBRANCH" in stale[0]["detail"]

    def test_census_stays_quiet_when_index_matches(self, vault_with_roles, roles):
        # A correct, current INDEX must not raise a stale_index finding.
        # Creating NEWBRANCH without regenerating leaves CREATIVE/INDEX.md
        # stale (the original bug); the repair is regenerate_indexes, after
        # which the census must be quiet.
        from vault.generate import regenerate_indexes
        (vault_with_roles / "CREATIVE/NEWBRANCH").mkdir(parents=True)
        regenerate_indexes(vault_with_roles)
        findings = maintain.run_census(vault_with_roles)
        assert not any(f["check"] == "stale_index" for f in findings)


class TestSuggestions:
    def test_suggestions_are_nature_suggestion(self, vault_with_roles):
        # two notes with identical normalised titles in the same tree
        _write(vault_with_roles / "CREATIVE/PHILOSOPHY/Dupe.md", """
---
type: work
kind: [concept]
status: draft
tags: [form, nietzsche]
created: 2026-08-02
---
Body A.
""")
        _write(vault_with_roles / "CREATIVE/PHILOSOPHY/dupe.md", """
---
type: work
kind: [concept]
status: draft
tags: [form, nietzsche]
created: 2026-08-02
---
Body B.
""")

        findings = maintain.run_suggestions(vault_with_roles, "vault_manager", None)
        assert findings, "expected at least one suggestion"
        assert all(f["nature"] == "suggestion" for f in findings)
        assert any(f["check"] == "duplicate" for f in findings)


class TestDistributionAndLifecycle:
    def test_full_flow_create_dedupe_resolve(self, vault_with_roles, roles):
        write_note(vault_with_roles, "system", roles,
                   path="SYSTEM/HANDBOOK/broken.md",
                   frontmatter=_fm(), body="See [[missing-target]]")

        # Run 1: finding distributed as an open issue.
        out = maintain.run_maintenance(vault_with_roles, "vault_manager", roles,
                                       mode="maintain", distribute_issues=True)
        assert out["distribution"]["created"]
        key = "dangling|SYSTEM/HANDBOOK/broken.md"
        rec = issues.read_issue(vault_with_roles, key)
        assert rec is not None and rec["state"] == "open"
        assert rec["tags"] == ["maintenance"]
        assert rec["raised_by"] == "vault_manager"
        # findings artifact written
        assert out["findings_file"] and out["findings_file"].startswith(".state/")

        # Run 2: same finding — dedupe, no new issue.
        out2 = maintain.run_maintenance(vault_with_roles, "vault_manager", roles,
                                        mode="maintain", distribute_issues=True)
        assert out2["distribution"]["skipped"]
        assert out2["distribution"]["created"] == []

        # Fix the note: create the target → condition cleared → auto-resolve.
        write_note(vault_with_roles, "system", roles,
                   path="SYSTEM/HANDBOOK/missing-target.md",
                   frontmatter=_fm(), body="Now it exists.")
        out3 = maintain.run_maintenance(vault_with_roles, "vault_manager", roles,
                                        mode="maintain", distribute_issues=True)
        assert key in out3["lifecycle"]["resolved"]
        assert issues.read_issue(vault_with_roles, key)["state"] == "resolved"

    def test_suggestions_auto_decline_after_ttl(self, vault_with_roles, roles):
        # An old open suggestion from the manager → auto-declined.
        issues.create_issue(vault_with_roles, "vault_manager",
                            key="duplicate|CREATIVE/PHILOSOPHY/a.md",
                            subject="[duplicate] a.md", detail="d",
                            target="CREATIVE/PHILOSOPHY/a.md",
                            nature="suggestion", tags=["maintenance"])
        rec_path = issues.issues_dir(vault_with_roles) / issues._slug(
            "duplicate|CREATIVE/PHILOSOPHY/a.md")
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        rec["created_at"] = _t(30)
        rec_path.write_text(json.dumps(rec), encoding="utf-8")

        out = maintain.run_maintenance(vault_with_roles, "vault_manager", roles,
                                       mode="optimize", distribute_issues=False)
        assert "duplicate|CREATIVE/PHILOSOPHY/a.md" in out["lifecycle"]["declined"]

    def test_auto_resolve_respects_grant_boundary(self, vault_with_roles, roles):
        # A dangling issue about a CREATIVE note, raised by tww (write on
        # CREATIVE/**). The condition clears once the target exists. An agent
        # with no write/meta over the target must NOT close it — the sweep
        # respects the grant boundary; tww may close its own.
        _write(vault_with_roles / "CREATIVE/PHILOSOPHY/broken.md", """
---
type: work
kind: [concept]
status: draft
tags: [x]
created: 2026-08-02
---
See [[missing-target]].
""")
        key = "dangling|CREATIVE/PHILOSOPHY/broken.md"
        issues.create_issue(vault_with_roles, "tww",
                            key=key, subject="[dangling] broken.md", detail="d",
                            target="CREATIVE/PHILOSOPHY/broken.md",
                            nature="finding", tags=["maintenance"])
        _write(vault_with_roles / "CREATIVE/PHILOSOPHY/missing-target.md", """
---
type: work
kind: [concept]
status: draft
tags: [x]
created: 2026-08-02
---
Now it exists.
""")

        # system has write only on SYSTEM/** — no standing over CREATIVE.
        out = maintain.run_maintenance(vault_with_roles, "system", roles,
                                       mode="maintain", distribute_issues=False)
        assert key not in out["lifecycle"]["resolved"]
        assert issues.read_issue(vault_with_roles, key)["state"] == "open"

        # tww owns CREATIVE/** → its sweep closes the issue it raised.
        tww_roles = load_roles(vault_with_roles)
        out2 = maintain.run_maintenance(vault_with_roles, "tww", tww_roles,
                                        mode="maintain", distribute_issues=False)
        assert key in out2["lifecycle"]["resolved"]

    def test_prune_removes_old_closed(self, vault_with_roles, roles):
        issues.create_issue(vault_with_roles, "vault_manager",
                            key="old|a", subject="Old", detail="d", target="a.md")
        issues.resolve_issue(vault_with_roles, "vault_manager", "old|a")
        rec_path = issues.issues_dir(vault_with_roles) / issues._slug("old|a")
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        rec["resolved_at"] = _t(60)
        rec["updated_at"] = _t(60)
        rec_path.write_text(json.dumps(rec), encoding="utf-8")

        out = maintain.run_maintenance(vault_with_roles, "vault_manager", roles,
                                       mode="maintain", distribute_issues=False)
        assert "old|a" in out["lifecycle"]["pruned"]


class TestDryRun:
    def test_dry_run_writes_nothing(self, vault_with_roles, roles):
        write_note(vault_with_roles, "system", roles,
                   path="SYSTEM/HANDBOOK/broken.md",
                   frontmatter=_fm(), body="See [[missing-target]]")

        out = maintain.run_maintenance(vault_with_roles, "vault_manager", roles,
                                       mode="maintain", distribute_issues=True,
                                       dry_run=True)
        assert out["findings"]
        assert out["distribution"]["would_create"] >= 1
        # no checkpoint, no findings file, no issues
        cp = maintain.checkpoint_path(vault_with_roles)
        assert cp is None or not cp.exists()
        assert out["findings_file"] is None
        assert issues.list_issues(vault_with_roles) == []
        # the dangling note itself is untouched
        assert "SYSTEM/HANDBOOK/broken.md" in [n.path for n in
                                               __import__("vault.notes",
                                                          fromlist=["iter_notes"])
                                               .iter_notes(vault_with_roles)]


class TestParaPortability:
    def test_sweep_works_on_para_layout(self, tmp_path):
        """A PARA vault with relocated state — zero code change required."""
        def _write(path: Path, text: str) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text.lstrip(), encoding="utf-8")

        _write(tmp_path / ".vault/config.yaml", """
fields:
  category: { required: true, vocabulary: true, allowed: [project, area] }
  format: { required: true, multi: true, vocabulary: true, allowed: [brief] }
  owner: { required: true }
paths:
  state: Archive/_state
tags:
  mode: closed
""")
        _write(tmp_path / ".vault/roles.yaml", """
agents:
  manager:
    meta: ["**"]
    read: ["**"]
    write: [".state/**"]
""")
        _write(tmp_path / "Projects/launch.md", """
---
category: project
format: [brief]
owner: davide
---
See [[missing-piece]].
""")
        _write(tmp_path / "Projects/launch.md", """
---
category: project
format: [brief]
owner: davide
---
See [[missing-piece]].
""")
        roles = load_roles(tmp_path)
        out = maintain.run_maintenance(tmp_path, "manager", roles,
                                       mode="maintain", distribute_issues=True)
        assert any(f["check"] == "dangling" for f in out["findings"])
        # ledger lives under the relocated state dir
        key = "dangling|Projects/launch.md"
        assert issues.read_issue(tmp_path, key)["state"] == "open"
        assert (tmp_path / "Archive/_state/issues").exists()


class TestFindingsPruning:
    """Findings JSONL is write-only — once distributed into the ledger the
    file is redundant, so prior runs' files must not accumulate."""

    @staticmethod
    def _findings_dir(vault: Path) -> Path:
        return maintain._maintain_dir(vault) / maintain.FINDINGS_DIRNAME

    @staticmethod
    def _names(d: Path):
        return sorted(p.name for p in d.glob("*.jsonl"))

    def test_prune_keeps_current_run_deletes_older(self, vault_with_roles):
        d = self._findings_dir(vault_with_roles)
        d.mkdir(parents=True, exist_ok=True)
        (d / "20260804-101010.jsonl").write_text("{}\n", encoding="utf-8")
        (d / "20260815-121212.jsonl").write_text("{}\n", encoding="utf-8")

        n = maintain.prune_findings(
            vault_with_roles, keep_current_run_id="20260815-121212")

        assert n == 1
        assert self._names(d) == ["20260815-121212.jsonl"]

    def test_prune_with_none_deletes_all(self, vault_with_roles):
        d = self._findings_dir(vault_with_roles)
        d.mkdir(parents=True, exist_ok=True)
        for rid in ("20260801-000001", "20260802-000002", "20260803-000003"):
            (d / f"{rid}.jsonl").write_text("{}\n", encoding="utf-8")

        assert maintain.prune_findings(vault_with_roles,
                                       keep_current_run_id=None) == 3
        assert self._names(d) == []

    def test_prune_only_touches_jsonl(self, vault_with_roles):
        d = self._findings_dir(vault_with_roles)
        d.mkdir(parents=True, exist_ok=True)
        (d / "20260801-000001.jsonl").write_text("{}\n", encoding="utf-8")
        (d / "notes.txt").write_text("keep me", encoding="utf-8")

        assert maintain.prune_findings(vault_with_roles) == 1
        assert (d / "notes.txt").exists()

    def test_prune_missing_dir_is_a_noop(self, vault_with_roles):
        d = self._findings_dir(vault_with_roles)
        assert not d.exists()
        assert maintain.prune_findings(vault_with_roles) == 0
        assert maintain.prune_findings(vault_with_roles,
                                       keep_current_run_id="x") == 0

    def test_sweep_leaves_only_the_current_runs_file(self, vault_with_roles,
                                                     roles):
        write_note(vault_with_roles, "system", roles,
                   path="SYSTEM/HANDBOOK/broken.md",
                   frontmatter=_fm(), body="See [[missing-target]]")

        out1 = maintain.run_maintenance(vault_with_roles, "vault_manager",
                                        roles, mode="maintain",
                                        distribute_issues=True)
        d = self._findings_dir(vault_with_roles)
        first = self._names(d)
        assert len(first) == 1

        # Second run writes its own file under a distinct run_id.
        out2 = maintain.run_maintenance(vault_with_roles, "vault_manager",
                                        roles, mode="maintain",
                                        distribute_issues=True)
        # Force distinct ids even inside the same second.
        if self._names(d) == first:
            (d / "20260101-000000.jsonl").write_text("{}\n", encoding="utf-8")
            out2 = maintain.run_maintenance(vault_with_roles, "vault_manager",
                                            roles, mode="maintain",
                                            distribute_issues=True)

        remaining = self._names(d)
        assert len(remaining) == 1, remaining
        # The survivor is the current run's reported file.
        assert out2["findings_file"].endswith(remaining[0])
        assert (vault_with_roles / out2["findings_file"]).exists()
        assert out1["findings_file"] is not None

    def test_dry_run_neither_writes_nor_prunes(self, vault_with_roles, roles):
        d = self._findings_dir(vault_with_roles)
        d.mkdir(parents=True, exist_ok=True)
        (d / "20260804-101010.jsonl").write_text("{}\n", encoding="utf-8")

        write_note(vault_with_roles, "system", roles,
                   path="SYSTEM/HANDBOOK/broken.md",
                   frontmatter=_fm(), body="See [[missing-target]]")
        out = maintain.run_maintenance(vault_with_roles, "vault_manager", roles,
                                       mode="maintain", distribute_issues=True,
                                       dry_run=True)

        assert out["findings_file"] is None
        assert "findings_pruned" not in out
        assert self._names(d) == ["20260804-101010.jsonl"]


class TestAutoAssign:
    """Sweep findings must be auto-assigned to the owning domain agent."""

    def test_distribute_routes_to_derived_owner(self, vault_with_roles, roles):
        write_note(vault_with_roles, "system", roles,
                   path="SYSTEM/HANDBOOK/broken.md",
                   frontmatter=_fm(), body="See [[missing-target]]")

        out = maintain.run_maintenance(vault_with_roles, "vault_manager", roles,
                                       mode="maintain", distribute_issues=True)
        assert out["distribution"]["created"]

        open_issues = issues.list_issues(vault_with_roles, state="open")
        # Every created issue carries an assignee — none left null.
        assert all(i["assignee"] for i in open_issues), \
            [(i["key"], i["assignee"]) for i in open_issues]
        # The system-domain finding routes to the default owner.
        sys_issue = next(i for i in open_issues
                        if i["target"] == "SYSTEM/HANDBOOK/broken.md")
        assert sys_issue["assignee"] == "default"

    def test_distribute_routes_work_domain_to_its_owner(self, vault_with_roles,
                                                        roles):
        # Creative domain owns work/creative/** via write glob.
        write_note(vault_with_roles, "creative", roles,
                   path="WORK/CREATIVE/notes/orphan.md",
                   frontmatter=_fm())
        # An orphan has no links — give it a hub neighbour so it is detected.
        write_note(vault_with_roles, "creative", roles,
                   path="WORK/CREATIVE/notes/hub.md",
                   frontmatter=_fm(), body="[[orphan]]")

        out = maintain.run_maintenance(vault_with_roles, "vault_manager", roles,
                                       mode="maintain", distribute_issues=True)
        assert out["distribution"]["created"]

        open_issues = issues.list_issues(vault_with_roles, state="open")
        creative_issues = [i for i in open_issues
                           if i["target"].startswith("WORK/CREATIVE/")]
        assert creative_issues
        assert all(i["assignee"] == "creative" for i in creative_issues)

    def test_distribute_ownerless_path_stays_unassigned(self, vault_with_roles,
                                                         roles):
        # A path outside every ownership glob has no derived owner, so it
        # stays null and remains manager triage (unchanged behaviour).
        findings = [{
            "check": "tag_normalization",
            "path": "ROOT-ONLY.md",   # matches no ownership glob
            "severity": "low",
            "detail": "x",
            "suggestion": "y",
            "nature": "suggestion",
        }]
        result = maintain.distribute(vault_with_roles, "vault_manager",
                                     roles, findings)
        assert result["created"]
        rec = issues.read_issue(vault_with_roles,
                                "tag_normalization|ROOT-ONLY.md")
        assert rec is not None and rec["assignee"] is None
