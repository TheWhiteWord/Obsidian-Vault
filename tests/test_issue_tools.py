"""Issue/maintain tools end-to-end — through the real plugin handlers.

The engine tests cover the logic; these cover the surface: argument
dispatch, grant enforcement at the tool boundary, and the batch path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import __init__ as plugin
from vault import issues
from vault.write import write_note


def _call(handler, args: dict) -> dict:
    return json.loads(handler(args))


def _fm(**kw):
    base = {"type": "note", "kind": ["note"], "status": "draft",
            "tags": ["t"], "created": "2026-08-02"}
    base.update(kw)
    return base


class TestIssueTool:
    def test_raise_single(self, vault_with_roles):
        out = _call(plugin._handle_issue, {
            "vault": str(vault_with_roles), "agent": "tww",
            "items": [{"subject": "Broken link", "detail": "d",
                       "target": "CREATIVE/PHILOSOPHY/recurrence.md"}],
        })
        assert out["issues"][0]["result"] == "created"
        entries = issues.list_issues(vault_with_roles)
        assert len(entries) == 1
        assert entries[0]["target"] == "CREATIVE/PHILOSOPHY/recurrence.md"

    def test_raise_batch(self, vault_with_roles):
        out = _call(plugin._handle_issue, {
            "vault": str(vault_with_roles), "agent": "vault_manager",
            "items": [
                {"subject": "One", "detail": "d", "target": "a.md"},
                {"subject": "Two", "detail": "d", "target": "b.md"},
            ],
        })
        assert [i["result"] for i in out["issues"]] == ["created", "created"]

    def test_raise_with_assignee(self, vault_with_roles):
        out = _call(plugin._handle_issue, {
            "vault": str(vault_with_roles), "agent": "tww",
            "items": [{"subject": "Broken link", "detail": "d",
                       "target": "CREATIVE/PHILOSOPHY/recurrence.md",
                       "assignee": "tww"}],
        })
        assert out["issues"][0]["result"] == "created"
        recs = issues.list_issues(vault_with_roles)
        assert recs[0]["assignee"] == "tww"

    def test_raise_unknown_agent_refused(self, vault_with_roles):
        out = _call(plugin._handle_issue, {
            "vault": str(vault_with_roles), "agent": "ghost",
            "items": [{"subject": "x", "detail": "d", "target": "a.md"}],
        })
        assert out["ok"] is False
        assert out["error"] == "RolesError"

    def test_raise_missing_vault(self):
        out = _call(plugin._handle_issue, {
            "vault": "/nonexistent/vault", "agent": "tww",
            "items": [{"subject": "x", "detail": "d", "target": "a.md"}],
        })
        assert out["ok"] is False

    def test_resolve_requires_ownership(self, vault_with_roles):
        issues.create_issue(vault_with_roles, "tww",
                            key="k|CREATIVE/PHILOSOPHY/recurrence.md",
                            subject="s", detail="d",
                            target="CREATIVE/PHILOSOPHY/recurrence.md")
        # system holds write only on SYSTEM/** — cannot resolve a CREATIVE issue
        out = _call(plugin._handle_issue_resolve, {
            "vault": str(vault_with_roles), "agent": "system",
            "key": "k|CREATIVE/PHILOSOPHY/recurrence.md",
        })
        assert out["ok"] is False
        assert out["error"] == "permission_denied"
        # tww owns CREATIVE/** — can resolve
        out2 = _call(plugin._handle_issue_resolve, {
            "vault": str(vault_with_roles), "agent": "tww",
            "key": "k|CREATIVE/PHILOSOPHY/recurrence.md",
            "reason": "fixed it",
        })
        assert out2["result"] == "closed"
        assert issues.read_issue(vault_with_roles,
                                 "k|CREATIVE/PHILOSOPHY/recurrence.md")["state"] \
            == "resolved"

    def test_resolve_missing(self, vault_with_roles):
        out = _call(plugin._handle_issue_resolve, {
            "vault": str(vault_with_roles), "agent": "tww",
            "key": "no|such",
        })
        assert out["ok"] is False and out["error"] == "not_found"

    def test_list_grant_intersection(self, vault_with_roles):
        issues.create_issue(vault_with_roles, "tww",
                            key="a|CREATIVE/PHILOSOPHY/recurrence.md",
                            subject="s", detail="d",
                            target="CREATIVE/PHILOSOPHY/recurrence.md")
        issues.create_issue(vault_with_roles, "system",
                            key="b|SYSTEM/HANDBOOK/design.md",
                            subject="s", detail="d",
                            target="SYSTEM/HANDBOOK/design.md")
        # tww reads CREATIVE/** + */KNOWLEDGE/** — sees only the CREATIVE issue
        out = _call(plugin._handle_issue_list, {
            "vault": str(vault_with_roles), "agent": "tww",
        })
        assert out["count"] == 1
        assert out["issues"][0]["key"] == "a|CREATIVE/PHILOSOPHY/recurrence.md"
        # system reads ** — sees both
        out2 = _call(plugin._handle_issue_list, {
            "vault": str(vault_with_roles), "agent": "system",
        })
        assert out2["count"] == 2


    def test_claim_requires_ownership(self, vault_with_roles):
        issues.create_issue(vault_with_roles, "tww",
                            key="k|CREATIVE/PHILOSOPHY/recurrence.md",
                            subject="s", detail="d",
                            target="CREATIVE/PHILOSOPHY/recurrence.md")
        # system holds write only on SYSTEM/** — cannot claim a CREATIVE issue
        out = _call(plugin._handle_issue_resolve, {
            "vault": str(vault_with_roles), "agent": "system",
            "key": "k|CREATIVE/PHILOSOPHY/recurrence.md",
            "state": "in_progress",
        })
        assert out["ok"] is False
        assert out["error"] == "permission_denied"
        # tww owns CREATIVE/** — can claim
        out2 = _call(plugin._handle_issue_resolve, {
            "vault": str(vault_with_roles), "agent": "tww",
            "key": "k|CREATIVE/PHILOSOPHY/recurrence.md",
            "state": "in_progress",
        })
        assert out2["result"] == "claimed"
        rec = issues.read_issue(vault_with_roles,
                                "k|CREATIVE/PHILOSOPHY/recurrence.md")
        assert rec["state"] == "in_progress"
        assert rec["claimed_by"] == "tww"
        assert rec["resolved_by"] is None

    def test_assignee_does_not_override_grants(self, vault_with_roles):
        # Issue assigned to tww but in SYSTEM/** — system (not tww) can act
        issues.create_issue(vault_with_roles, "tww",
                            key="k|SYSTEM/HANDBOOK/design.md",
                            subject="s", detail="d",
                            target="SYSTEM/HANDBOOK/design.md",
                            assignee="tww")
        out = _call(plugin._handle_issue_resolve, {
            "vault": str(vault_with_roles), "agent": "tww",
            "key": "k|SYSTEM/HANDBOOK/design.md",
            "state": "in_progress",
        })
        # assignee is a SHOULD signal, never a CAN override
        assert out["ok"] is False
        assert out["error"] == "permission_denied"

    def test_assign_requires_ownership(self, vault_with_roles):
        issues.create_issue(vault_with_roles, "tww",
                            key="k|CREATIVE/PHILOSOPHY/recurrence.md",
                            subject="s", detail="d",
                            target="CREATIVE/PHILOSOPHY/recurrence.md")
        # system holds write only on SYSTEM/** — cannot route a CREATIVE issue
        out = _call(plugin._handle_issue_resolve, {
            "vault": str(vault_with_roles), "agent": "system",
            "key": "k|CREATIVE/PHILOSOPHY/recurrence.md",
            "assignee": "tww",
        })
        assert out["ok"] is False
        assert out["error"] == "permission_denied"
        # tww owns CREATIVE/** — can assign
        out2 = _call(plugin._handle_issue_resolve, {
            "vault": str(vault_with_roles), "agent": "tww",
            "key": "k|CREATIVE/PHILOSOPHY/recurrence.md",
            "assignee": "creative",
        })
        assert out2["result"] == "assigned"
        rec = issues.read_issue(vault_with_roles,
                                "k|CREATIVE/PHILOSOPHY/recurrence.md")
        assert rec["assignee"] == "creative"
        assert rec["state"] == "open"  # assign leaves state untouched

    def test_assign_then_claim_then_resolve(self, vault_with_roles):
        # Full routing lifecycle through the tool: manager assigns, the
        # assignee claims, then resolves.
        issues.create_issue(vault_with_roles, "vault_manager",
                            key="k|CREATIVE/PHILOSOPHY/recurrence.md",
                            subject="s", detail="d",
                            target="CREATIVE/PHILOSOPHY/recurrence.md")
        out = _call(plugin._handle_issue_resolve, {
            "vault": str(vault_with_roles), "agent": "vault_manager",
            "key": "k|CREATIVE/PHILOSOPHY/recurrence.md",
            "assignee": "tww",
        })
        assert out["result"] == "assigned"
        out2 = _call(plugin._handle_issue_resolve, {
            "vault": str(vault_with_roles), "agent": "tww",
            "key": "k|CREATIVE/PHILOSOPHY/recurrence.md",
            "state": "in_progress",
        })
        assert out2["result"] == "claimed"
        out3 = _call(plugin._handle_issue_resolve, {
            "vault": str(vault_with_roles), "agent": "tww",
            "key": "k|CREATIVE/PHILOSOPHY/recurrence.md",
            "state": "resolved", "reason": "done",
        })
        assert out3["result"] == "closed"
        rec = issues.read_issue(vault_with_roles,
                                "k|CREATIVE/PHILOSOPHY/recurrence.md")
        assert rec["assignee"] == "tww"
        assert rec["state"] == "resolved"
        assert rec["claimed_by"] == "tww"

    def test_list_assigned_to_me(self, vault_with_roles):
        issues.create_issue(vault_with_roles, "vault_manager",
                            key="a|CREATIVE/PHILOSOPHY/recurrence.md",
                            subject="s", detail="d",
                            target="CREATIVE/PHILOSOPHY/recurrence.md",
                            assignee="tww")
        issues.create_issue(vault_with_roles, "vault_manager",
                            key="b|SYSTEM/HANDBOOK/design.md",
                            subject="s", detail="d",
                            target="SYSTEM/HANDBOOK/design.md",
                            assignee="system")
        out = _call(plugin._handle_issue_list, {
            "vault": str(vault_with_roles), "agent": "tww",
            "assigned_to": "me",
        })
        assert out["count"] == 1
        assert out["issues"][0]["key"] == "a|CREATIVE/PHILOSOPHY/recurrence.md"


class TestMaintainTool:
    def test_dry_run_through_tool(self, vault_with_roles):
        write_note(vault_with_roles, "system",
                   __import__("vault.grants", fromlist=["load_roles"])
                   .load_roles(vault_with_roles),
                   path="SYSTEM/HANDBOOK/broken.md",
                   frontmatter=_fm(), body="See [[missing-target]]")
        out = _call(plugin._handle_maintain, {
            "vault": str(vault_with_roles), "agent": "vault_manager",
            "mode": "maintain", "dry_run": True,
        })
        assert out["findings"]
        assert out["findings_file"] is None
        assert issues.list_issues(vault_with_roles) == []

    def test_live_run_through_tool(self, vault_with_roles):
        write_note(vault_with_roles, "system",
                   __import__("vault.grants", fromlist=["load_roles"])
                   .load_roles(vault_with_roles),
                   path="SYSTEM/HANDBOOK/broken.md",
                   frontmatter=_fm(), body="See [[missing-target]]")
        out = _call(plugin._handle_maintain, {
            "vault": str(vault_with_roles), "agent": "vault_manager",
            "mode": "maintain",
        })
        assert out["distribution"]["created"]
        assert out["findings_file"]
        key = "dangling|SYSTEM/HANDBOOK/broken.md"
        assert issues.read_issue(vault_with_roles, key)["state"] == "open"
