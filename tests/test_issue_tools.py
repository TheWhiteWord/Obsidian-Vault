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
