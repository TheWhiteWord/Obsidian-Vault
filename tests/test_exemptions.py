"""P12 maintenance exemptions — config merge, sweep consult, edit_config.

Three layers:
  1. Config merge (test_config style): union / replace / restricted flag,
     mutual-exclusion NOT enforced, unknown check tolerated, malformed raises.
  2. Sweep consult (test_maintain style): exempted conditions produce no
     findings, the exempt_only asymmetry re-enables a check, glob scopes
     blanket-exempt, dry_run & distribute_issues suppress, and an open
     exempted suggestion closes immediately (not the 14-day TTL).
  3. edit_config (Task 1): a maintenance delta now persists (changed: True).
"""

from __future__ import annotations

import yaml
from pathlib import Path

import pytest

from vault import audit
from vault import issues
from vault import maintain
from vault.config import ConfigError, resolve_config
from vault.grants import load_roles
from vault.scaffold import edit_config


# ---------------------------------------------------------------------------
# 1. Config merge
# ---------------------------------------------------------------------------

class TestMaintenanceMerge:
    def test_exempt_unions_with_parent(self, vault):
        """Child ADDS to the parent's exempt list (union, not replace)."""
        root = vault / ".vault/config.yaml"
        root.write_text(
            "maintenance:\n"
            "  exempt:\n"
            "    duplicate: [\"system/skills/**\"]\n",
            encoding="utf-8",
        )
        child = vault / "system/.vault/config.yaml"
        child.parent.mkdir(parents=True, exist_ok=True)
        child.write_text(
            "maintenance:\n"
            "  exempt:\n"
            "    duplicate: [\"system/agents/**\"]\n",
            encoding="utf-8",
        )
        cfg = resolve_config(vault, vault / "system")
        assert set(cfg.maintenance["exempt"]["duplicate"]) == {
            "system/skills/**", "system/agents/**"
        }
        # exempt_only must be untouched
        assert cfg.maintenance["exempt_only"] == {}
        # child added, not restricted
        assert "duplicate" not in cfg.maintenance["restricted"]

    def test_exempt_only_replaces_and_flags_restricted(self, vault):
        """exempt_only REPLACES the set and marks the check restricted."""
        root = vault / ".vault/config.yaml"
        root.write_text(
            "maintenance:\n"
            "  exempt:\n"
            "    duplicate: [\"system/skills/**\"]\n",
            encoding="utf-8",
        )
        child = vault / "system/.vault/config.yaml"
        child.parent.mkdir(parents=True, exist_ok=True)
        child.write_text(
            "maintenance:\n"
            "  exempt_only:\n"
            "    duplicate: [\"system/creative/knowledge/**\"]\n",
            encoding="utf-8",
        )
        cfg = resolve_config(vault, vault / "system")
        # exempt_only replaces — the parent's glob is gone for that check
        assert cfg.maintenance["exempt_only"]["duplicate"] == [
            "system/creative/knowledge/**"
        ]
        assert "duplicate" in cfg.maintenance["restricted"]
        # ASYMMETRY: the exempt_only list wins for that check
        assert cfg.exempt_for("duplicate", "system/skills/x.md") is False
        assert cfg.exempt_for("duplicate", "system/creative/knowledge/x.md") is True

    def test_mutual_exclusion_not_enforced(self, vault):
        """exempt and exempt_only may coexist; exempt_only wins for the check
        it restricts, but an exempt-only check still exists for the others."""
        root = vault / ".vault/config.yaml"
        root.write_text(
            "maintenance:\n"
            "  exempt:\n"
            "    duplicate: [\"system/skills/**\"]\n"
            "    dangling:  [\"system/archive/**\"]\n",
            encoding="utf-8",
        )
        child = vault / "system/.vault/config.yaml"
        child.parent.mkdir(parents=True, exist_ok=True)
        child.write_text(
            "maintenance:\n"
            "  exempt_only:\n"
            "    duplicate: [\"system/creative/knowledge/**\"]\n",
            encoding="utf-8",
        )
        cfg = resolve_config(vault, vault / "system")
        # both modes present for duplicate
        assert "duplicate" in cfg.maintenance["exempt"]
        assert "duplicate" in cfg.maintenance["exempt_only"]
        # a DIFFERENT check's exempt still applies normally
        assert cfg.exempt_for("dangling", "system/archive/old.md") is True
        # exempt_only overrides exempt for the restricted check only
        assert cfg.exempt_for("duplicate", "system/skills/x.md") is False
        assert cfg.exempt_for("duplicate", "system/creative/knowledge/x.md") is True

    def test_unknown_check_name_is_tolerated(self, vault):
        """A scope may name a check that does not yet exist — no raise."""
        root = vault / ".vault/config.yaml"
        root.write_text(
            "maintenance:\n"
            "  exempt:\n"
            "    future_check: [\"system/beta/**\"]\n",
            encoding="utf-8",
        )
        cfg = resolve_config(vault, vault)
        assert cfg.maintenance["exempt"]["future_check"] == ["system/beta/**"]
        # unknown check never exempts an actual finding check
        assert cfg.exempt_for("duplicate", "system/beta/x.md") is False

    @pytest.mark.parametrize("bad_body", [
        "maintenance: not-a-mapping\n",                       # not a mapping
        "maintenance:\n  exempt: a-string\n",                 # section not mapping
        "maintenance:\n  exempt:\n    duplicate: a-glob\n",   # globs not a list of str
    ])
    def test_malformed_maintenance_raises(self, vault, bad_body):
        root = vault / ".vault/config.yaml"
        root.write_text(bad_body, encoding="utf-8")
        with pytest.raises(ConfigError):
            resolve_config(vault, vault)


# ---------------------------------------------------------------------------
# 2. Sweep consult
# ---------------------------------------------------------------------------

def _write_note(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip(), encoding="utf-8")


def _make_duplicate_pair(vault_root: Path, tree: str, slug: str) -> None:
    """Two notes with identical normalised TITLE → a duplicate suggestion.

    The B2 duplicate check keys on the note's normalised *title*. The title
    is derived from the note body/heading, but for these minimal notes it
    falls back to the filename stem. Writing ``<slug>.md`` and
    ``<SLUG>.md`` gives stems that normalise to the same token, so they
    collide (this is what the real test suite uses).
    """
    body = (
        "---\n"
        "type: work\n"
        "kind: [concept]\n"
        "status: draft\n"
        "tags: [form, nietzsche]\n"
        "created: 2026-08-02\n"
        "---\n"
        "Body.\n"
    )
    _write_note(vault_root / tree / f"{slug}.md", body)
    _write_note(vault_root / tree / f"{slug.upper()}.md", body)


def _set_root_maintenance(vault_root: Path, maintenance: dict) -> None:
    """Merge a maintenance block into the vault root config, preserving the
    rest (notably ``paths: {state: .state}`` when present)."""
    root = vault_root / ".vault/config.yaml"
    raw = yaml.safe_load(root.read_text(encoding="utf-8")) or {}
    raw["maintenance"] = maintenance
    root.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


class TestSweepExemption:
    def test_exempted_folder_produces_no_finding(self, vault):
        _set_root_maintenance(vault, {
            "exempt": {"duplicate": ["system/skills/**"]}})
        # two identical-title notes under the exempted scope
        _make_duplicate_pair(vault, "system/skills", "dup")
        findings = maintain.run_suggestions(vault, "vault_manager", None)
        assert not any(
            f["check"] == "duplicate" and f["path"].startswith("system/skills/")
            for f in findings
        )

    def test_non_exempted_same_check_still_raises(self, vault):
        _set_root_maintenance(vault, {
            "exempt": {"duplicate": ["system/skills/**"]}})
        # identical titles OUTSIDE the exempted scope → still flagged
        _make_duplicate_pair(vault, "system/handbook", "dup")
        findings = maintain.run_suggestions(vault, "vault_manager", None)
        assert any(
            f["check"] == "duplicate" and f["path"].startswith("system/handbook/")
            for f in findings
        )

    def test_exempt_only_re_enables_parent_exempt_check(self, vault_with_roles):
        """Asymmetry: a parent exempts duplicate for ALL of ``system/**``. A
        child scope narrows that exemption via ``exempt_only`` to ONLY
        ``system/knowledge/keep/**`` — so the check is *re-enabled* (opted back
        in) for every other system sub-scope, while the narrowed set stays
        exempt. ``exempt_only`` REPLACES the inherited exempt union for the
        check and flags it ``restricted``, so the parent's broad exemption no
        longer applies beyond the child's narrower list."""
        _set_root_maintenance(vault_with_roles, {
            "exempt": {"duplicate": ["system/**"]}})
        child = vault_with_roles / "system/knowledge/.vault/config.yaml"
        child.parent.mkdir(parents=True, exist_ok=True)
        child.write_text(
            "maintenance:\n"
            "  exempt_only:\n"
            "    duplicate: [\"system/knowledge/keep/**\"]\n",
            encoding="utf-8",
        )
        # a sub-scope INSIDE the child config but OUTSIDE the narrowed exempt
        # set → re-enabled (the child's exempt_only REPLACED the parent's broad
        # system/** exemption for this check)
        _make_duplicate_pair(vault_with_roles, "system/knowledge/elsewhere", "dup")
        findings = maintain.run_suggestions(
            vault_with_roles, "vault_manager", None)
        assert any(
            f["check"] == "duplicate"
            and f["path"].startswith("system/knowledge/elsewhere/")
            for f in findings
        )
        # the narrowed set itself stays exempt (no finding)
        _make_duplicate_pair(vault_with_roles, "system/knowledge/keep", "dup2")
        findings2 = maintain.run_suggestions(
            vault_with_roles, "vault_manager", None)
        assert not any(
            f["check"] == "duplicate"
            and f["path"].startswith("system/knowledge/keep/")
            for f in findings2
        )

    def test_glob_scope_exempts_every_note_under_it(self, vault):
        _set_root_maintenance(vault, {
            "exempt": {"duplicate": ["system/**"]}})
        # duplicates all over the system tree — none should surface
        _make_duplicate_pair(vault, "system/a/b/c", "dup")
        _make_duplicate_pair(vault, "system/x", "dup2")
        findings = maintain.run_suggestions(vault, "vault_manager", None)
        assert not any(
            f["check"] == "duplicate" and f["path"].startswith("system/")
            for f in findings
        )

    def test_dry_run_suppresses_exempted_finding(self, vault):
        _set_root_maintenance(vault, {
            "exempt": {"duplicate": ["system/skills/**"]}})
        _make_duplicate_pair(vault, "system/skills", "dup")
        out = maintain.run_maintenance(
            vault, "vault_manager", None,
            mode="optimize", distribute_issues=False, dry_run=True)
        assert not any(
            f["check"] == "duplicate" and f["path"].startswith("system/skills/")
            for f in out["findings"]
        )
        # dry_run writes nothing — no issues created
        assert issues.list_issues(vault) == []

    def test_distribute_issues_false_suppresses_exempted_finding(self, vault_with_roles):
        roles = load_roles(vault_with_roles)
        _set_root_maintenance(vault_with_roles, {
            "exempt": {"duplicate": ["system/skills/**"]}})
        _make_duplicate_pair(vault_with_roles, "system/skills", "dup")
        out = maintain.run_maintenance(
            vault_with_roles, "vault_manager", roles,
            mode="optimize", distribute_issues=False)
        # no exempted finding in the artifact
        assert not any(
            f["check"] == "duplicate" and f["path"].startswith("system/skills/")
            for f in out["findings"]
        )
        # and nothing distributed
        assert out["distribution"] == {
            "created": [], "reopened": [], "skipped": []
        }

    def test_open_exempted_suggestion_closed_by_auto_resolve(self, vault_with_roles):
        """An OPEN suggestion whose check/target becomes exempted is closed
        immediately by auto_resolve (reason 'scope-exempted'), not left to the
        14-day TTL."""
        roles = load_roles(vault_with_roles)
        _make_duplicate_pair(vault_with_roles, "system/skills", "dup")
        # distribute once so the suggestion becomes an OPEN issue
        maintain.run_maintenance(
            vault_with_roles, "vault_manager", roles,
            mode="optimize", distribute_issues=True)
        open_dupes = [
            r for r in issues.list_issues(vault_with_roles, state="open")
            if r["key"].startswith("duplicate|")
        ]
        assert open_dupes, "expected an open duplicate suggestion to distribute"
        key = open_dupes[0]["key"]
        assert open_dupes[0]["state"] == "open"

        # now exempt that scope
        _set_root_maintenance(vault_with_roles, {
            "exempt": {"duplicate": ["system/skills/**"]}})

        out = maintain.run_maintenance(
            vault_with_roles, "vault_manager", roles,
            mode="optimize", distribute_issues=False)
        assert key in out["lifecycle"]["resolved"]
        closed = issues.read_issue(vault_with_roles, key)
        assert closed["state"] == "resolved"
        assert closed["reason"] == "scope-exempted"

    def test_condition_holds_false_for_exempted_pair(self, vault):
        _set_root_maintenance(vault, {
            "exempt": {"duplicate": ["system/skills/**"]}})
        _make_duplicate_pair(vault, "system/skills", "dup")
        notes = list(__import__("vault.notes", fromlist=["iter_notes"])
                     .iter_notes(vault))
        g = __import__("vault.graph", fromlist=["build_graph"]) \
            .build_graph(vault, notes)
        note_map = {n.path: n for n in notes}
        # even though the duplicate genuinely exists, the exempted scope makes
        # the condition "cleared" → _condition_holds is False → auto_resolve
        # would close it.
        assert maintain._condition_holds(
            "duplicate", "system/skills/dup.md", g, note_map, vault) is False


# ---------------------------------------------------------------------------
# 3. edit_config (Task 1)
# ---------------------------------------------------------------------------

class TestEditConfigMaintenance:
    def test_edit_config_persists_maintenance_delta(self, vault_with_roles):
        roles = load_roles(vault_with_roles)
        # The CREATIVE tree is owned by ``tww`` (write+config on CREATIVE/**),
        # so tww may edit_config there without P7 shadowing.
        target = vault_with_roles / "CREATIVE/.vault/config.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "fields:\n  type: {allowed: [work]}\n", encoding="utf-8")

        proposed = {"maintenance": {"exempt": {
            "duplicate": ["system/skills/**"]}}}

        # proposal shows the delta (no writes yet)
        prop = edit_config(vault_with_roles, "tww", roles,
                           "CREATIVE/.vault/config.yaml",
                           proposed=proposed)
        assert prop["delta"].get("maintenance") == {
            "exempt": {"duplicate": ["system/skills/**"]}
        }
        assert prop["proposal"] is True

        # confirm → persists
        out = edit_config(vault_with_roles, "tww", roles,
                          "CREATIVE/.vault/config.yaml",
                          proposed=proposed, confirm=True)
        assert out["changed"] is True
        assert "maintenance" in out["delta"]

        # the file actually carries it
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
        assert raw["maintenance"]["exempt"]["duplicate"] == ["system/skills/**"]

        # and it resolves at runtime for the CREATIVE scope
        cfg = resolve_config(vault_with_roles, vault_with_roles / "CREATIVE")
        assert cfg.exempt_for("duplicate", "system/skills/x.md") is True

    def test_edit_config_noop_when_already_inherited(self, vault_with_roles):
        """Proposing a maintenance delta identical to the inherited value
        yields changed: False and writes nothing (Task 1 carries only real
        changes)."""
        roles = load_roles(vault_with_roles)
        _set_root_maintenance(vault_with_roles, {
            "exempt": {"duplicate": ["system/skills/**"]}})
        target = vault_with_roles / "CREATIVE/.vault/config.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "fields:\n  type: {allowed: [work]}\n", encoding="utf-8")

        proposed = {"maintenance": {"exempt": {
            "duplicate": ["system/skills/**"]}}}
        out = edit_config(vault_with_roles, "tww", roles,
                          "CREATIVE/.vault/config.yaml",
                          proposed=proposed, confirm=True)
        assert out["changed"] is False
