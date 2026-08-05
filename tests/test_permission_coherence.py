"""P3.6 — permission coherence (D2/D7).

The code and the spec must agree: read is deny-by-default enforcement on
every surface (graph, audit), INDEX regeneration is gated, the ISSUES
channel is actually restricted (not a union with the root vocabulary),
and obsidian_context tells the caller what it may do and where the
writing conventions live (pointer, not content).
"""

from __future__ import annotations

import json

import pytest

import __init__ as plugin
from vault.config import resolve_config
from vault.context import build_context
from vault.write import WriteRefused, write_note

GOOD_FM = {
    "type": "note",
    "kind": ["note"],
    "status": "draft",
    "tags": ["test"],
    "created": "2026-08-03",
}

ISSUES_CONFIG = """\
fields:
  kind:    { required: true, multi: true, vocabulary: true, allowed_only: [issue] }
  status:  { required: true, allowed_only: [open, in-progress, resolved] }
  created: { required: true, format: date }
defaults:
  status: open
  created: "@today"
"""


@pytest.fixture
def vault_with_issue_config(vault_with_roles):
    """vault_with_roles plus the ISSUES channel configs (live-vault shape)."""
    for tree in ("SYSTEM", "CREATIVE"):
        cfg_dir = vault_with_roles / tree / "ISSUES" / ".vault"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "config.yaml").write_text(ISSUES_CONFIG, encoding="utf-8")
    return vault_with_roles


@pytest.fixture
def roles(vault_with_roles):
    from vault.grants import load_roles
    return load_roles(vault_with_roles)


class TestIssuesChannelRestricted:
    """D6 #3 — `allowed` unioned with root; the channel must restrict."""

    def test_issues_vocabulary_is_allowed_only(self, vault_with_issue_config):
        for tree in ("SYSTEM", "CREATIVE"):
            cfg = resolve_config(
                vault_with_issue_config, vault_with_issue_config / tree / "ISSUES")
            assert cfg.allowed_values("kind") == ["issue"]
            assert cfg.allowed_values("status") == ["open", "in-progress", "resolved"]
            assert cfg.fields["kind"]["restricted"] is True

    def test_conforming_issue_is_accepted(self, vault_with_issue_config, roles):
        out = write_note(vault_with_issue_config, "tww", roles,
                         "SYSTEM/ISSUES/real-problem.md",
                         {"type": "note", "kind": ["issue"], "status": "open",
                          "tags": ["bug"], "created": "2026-08-03"})
        assert out.created is True

    def test_non_issue_kind_is_refused(self, vault_with_issue_config, roles):
        with pytest.raises(WriteRefused, match="does not conform"):
            write_note(vault_with_issue_config, "tww", roles,
                       "SYSTEM/ISSUES/not-an-issue.md",
                       {"type": "note", "kind": ["spec"], "status": "open",
                        "tags": ["x"], "created": "2026-08-03"})

    def test_non_issue_status_is_refused(self, vault_with_issue_config, roles):
        with pytest.raises(WriteRefused, match="does not conform"):
            write_note(vault_with_issue_config, "tww", roles,
                       "SYSTEM/ISSUES/bad-status.md",
                       {"type": "note", "kind": ["issue"], "status": "draft",
                        "tags": ["x"], "created": "2026-08-03"})


class TestGraphReadEnforcement:
    """D2 — an agent sees nothing from a note it cannot read."""

    def test_unreadable_center_returns_empty(self, vault_with_roles):
        out = json.loads(plugin._handle_graph({
            "path": "SYSTEM/HANDBOOK/design.md",
            "vault": str(vault_with_roles),
            "agent": "tww",
        }))
        assert out["neighbors"] == [] and out["hops"] == []

    def test_readable_center_lists_only_readable_neighbors(self, vault_with_roles):
        # recurrence.md links [[kant-on-time]] (CREATIVE/KNOWLEDGE — readable)
        out = json.loads(plugin._handle_graph({
            "path": "CREATIVE/PHILOSOPHY/recurrence.md",
            "vault": str(vault_with_roles),
            "agent": "tww",
        }))
        assert out["neighbors"]  # at least the KNOWLEDGE note
        for e in out["neighbors"]:
            assert e["to"].startswith("CREATIVE/") or "/KNOWLEDGE/" in e["to"]

    def test_system_sees_the_same_graph(self, vault_with_roles):
        out = json.loads(plugin._handle_graph({
            "path": "CREATIVE/PHILOSOPHY/recurrence.md",
            "vault": str(vault_with_roles),
            "agent": "system",
        }))
        assert any(e["to"].endswith("kant-on-time.md") for e in out["neighbors"])


class TestAuditReadEnforcement:
    """D2 — the audit trail is a read surface; filter by read grants."""

    def test_tww_sees_only_its_own_paths(self, vault_with_roles, roles):
        write_note(vault_with_roles, "system", roles,
                   "SYSTEM/HANDBOOK/logged.md", GOOD_FM, "x")
        write_note(vault_with_roles, "tww", roles,
                   "CREATIVE/PHILOSOPHY/mine.md", GOOD_FM, "y")

        as_tww = json.loads(plugin._handle_audit({
            "vault": str(vault_with_roles), "limit": 50, "agent": "tww"}))
        paths = {e["path"] for e in as_tww["entries"]}
        assert "CREATIVE/PHILOSOPHY/mine.md" in paths
        assert "SYSTEM/HANDBOOK/logged.md" not in paths

        as_system = json.loads(plugin._handle_audit({
            "vault": str(vault_with_roles), "limit": 50, "agent": "system"}))
        sys_paths = {e["path"] for e in as_system["entries"]}
        assert "SYSTEM/HANDBOOK/logged.md" in sys_paths


class TestIndexGrantGating:
    """Regenerating INDEX is a write of derived files — gate on any grant."""

    def test_tww_cannot_reindex_system(self, vault_with_roles):
        out = json.loads(plugin._handle_index({
            "folder": "SYSTEM", "vault": str(vault_with_roles), "agent": "tww"}))
        assert out.get("ok") is False and out.get("error") == "permission_denied"

    def test_system_can_reindex_its_tree(self, vault_with_roles):
        out = json.loads(plugin._handle_index({
            "folder": "SYSTEM", "vault": str(vault_with_roles),
            "agent": "system"}))
        assert out.get("ok") is True or "indexed" in out

    def test_vault_manager_meta_grant_suffices(self, vault_with_roles):
        # any grant (here: meta) gates derived bookkeeping, not write only
        out = json.loads(plugin._handle_index({
            "folder": "CREATIVE", "vault": str(vault_with_roles),
            "agent": "vault_manager"}))
        assert out.get("ok") is True or "indexed" in out

    def test_tww_cannot_reindex_the_whole_vault(self, vault_with_roles):
        out = json.loads(plugin._handle_index({
            "folder": ".", "vault": str(vault_with_roles), "agent": "tww"}))
        assert out.get("ok") is False and out.get("error") == "permission_denied"


class TestContextGrantsAndConventions:
    """§5 + D7 — the context call tells the caller what it may do."""

    def test_grants_row_reflects_agent(self, vault_with_roles, roles):
        in_domain = build_context(vault_with_roles, "CREATIVE",
                                  agent="tww", roles=roles)
        assert in_domain["grants"]["write"] is True
        assert in_domain["grants"]["read"] is True

        out_domain = build_context(vault_with_roles, "SYSTEM",
                                   agent="tww", roles=roles)
        assert out_domain["grants"]["write"] is False
        assert out_domain["grants"]["read"] is False

    def test_conventions_ref_defaults_to_bundled_skill(self, vault):
        ctx = build_context(vault, "CREATIVE")
        assert ctx["conventions_ref"] == {"skill": "plugin:obsidian-vault"}

    def test_conventions_ref_honours_config_override(self, vault):
        (vault / ".vault/config.yaml").write_text(
            (vault / ".vault/config.yaml").read_text()
            + "\nconventions:\n  skill: my-vault-skill\n",
            encoding="utf-8")
        ctx = build_context(vault, "CREATIVE")
        assert ctx["conventions_ref"] == {"skill": "my-vault-skill"}

    def test_context_through_handler_carries_grants(self, vault_with_roles):
        out = json.loads(plugin._handle_context({
            "folder": "CREATIVE", "vault": str(vault_with_roles),
            "agent": "tww"}))
        assert out["grants"]["write"] is True
        assert out["conventions_ref"] == {"skill": "plugin:obsidian-vault"}

    def test_context_without_roles_grants_nothing(self, vault):
        # no roles.yaml → deny by default, all-false row, no crash
        from vault.grants import load_roles
        ctx = build_context(vault, "CREATIVE", agent="tww",
                            roles=load_roles(vault))
        assert ctx["grants"] == {
            "read": False, "write": False, "append": False,
            "meta": False, "config": False}
