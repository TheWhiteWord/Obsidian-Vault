"""Protocol registry tests — spec 09.

The registry is machinery under the state dir: structured records with
parties, not notes. These tests cover validation, the parties-only write
gate (the adversarial matrix), party-filtered listing, the no-pollution
guarantee, and the tool surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import __init__ as plugin
from vault import audit, protocols
from vault.grants import PermissionDenied
from vault.notes import iter_notes


def _call(handler, args: dict) -> dict:
    return json.loads(handler(args))


def _record(**overrides) -> dict:
    rec = {
        "name": "research-handoff",
        "version": 1,
        "requester": {"profiles": ["tww"], "domains": ["CREATIVE/**"]},
        "responder": {"profiles": ["system"], "domains": ["SYSTEM/**"]},
        "request_format": "task + intent + expected response form",
        "response_format": "findings + sources + summary",
        "instructions": "REQUEST SIDE — ask.\nRESPONSE SIDE — answer.",
    }
    rec.update(overrides)
    return rec


@pytest.fixture
def registry(vault_with_roles: Path) -> Path:
    """The registry folder for the fixture vault."""
    return vault_with_roles / ".state" / "protocols"


class TestValidation:
    def test_missing_required_field_raises(self, vault_with_roles):
        rec = _record()
        del rec["instructions"]
        with pytest.raises(protocols.ProtocolError):
            protocols.register_protocol(vault_with_roles, "tww", rec, confirm=True)

    def test_empty_profiles_raises(self, vault_with_roles):
        rec = _record()
        rec["requester"] = {"profiles": [], "domains": []}
        with pytest.raises(protocols.ProtocolError):
            protocols.register_protocol(vault_with_roles, "tww", rec, confirm=True)

    def test_non_string_profile_raises(self, vault_with_roles):
        rec = _record()
        rec["responder"] = {"profiles": [123], "domains": []}
        with pytest.raises(protocols.ProtocolError):
            protocols.register_protocol(vault_with_roles, "tww", rec, confirm=True)

    def test_empty_name_raises(self, vault_with_roles):
        rec = _record(name="   ")
        with pytest.raises(protocols.ProtocolError):
            protocols.register_protocol(vault_with_roles, "tww", rec, confirm=True)


class TestPartiesGate:
    """The adversarial matrix — the value is entirely in the refusals."""

    def test_requester_can_register(self, vault_with_roles, registry):
        out = protocols.register_protocol(
            vault_with_roles, "tww", _record(), confirm=True)
        assert out["ok"] is True
        assert out["action"] == "registered"
        assert (registry / "research-handoff-*.yaml").parent.exists()

    def test_responder_can_register(self, vault_with_roles):
        out = protocols.register_protocol(
            vault_with_roles, "system", _record(), confirm=True)
        assert out["action"] == "registered"

    def test_non_party_cannot_register(self, vault_with_roles):
        rec = _record()  # parties are tww + system
        with pytest.raises(PermissionDenied):
            protocols.register_protocol(
                vault_with_roles, "vault_manager", rec, confirm=True)

    def test_unknown_agent_cannot_register(self, vault_with_roles):
        rec = _record()
        with pytest.raises(PermissionDenied):
            protocols.register_protocol(
                vault_with_roles, "ghost", rec, confirm=True)

    def test_non_party_cannot_update(self, vault_with_roles):
        protocols.register_protocol(
            vault_with_roles, "tww", _record(), confirm=True)
        with pytest.raises(PermissionDenied):
            protocols.update_protocol(
                vault_with_roles, "vault_manager", "research-handoff",
                _record(), confirm=True)

    def test_party_can_update(self, vault_with_roles, registry):
        protocols.register_protocol(
            vault_with_roles, "tww", _record(), confirm=True)
        new_rec = _record(response_format="findings only")
        out = protocols.update_protocol(
            vault_with_roles, "tww", "research-handoff", new_rec, confirm=True)
        assert out["action"] == "updated"
        loaded = protocols.get_protocol(vault_with_roles, "research-handoff")
        assert loaded is not None
        assert loaded["response_format"] == "findings only"

    def test_update_unknown_record_not_found(self, vault_with_roles):
        out = protocols.update_protocol(
            vault_with_roles, "tww", "missing", _record(), confirm=True)
        assert out["ok"] is False
        assert out["error"] == "not_found"

    def test_update_keeps_slug_identity(self, vault_with_roles):
        """The record's name field never drifts from the slug key."""
        protocols.register_protocol(
            vault_with_roles, "tww", _record(), confirm=True)
        renamed = _record(name="other-name")
        protocols.update_protocol(
            vault_with_roles, "tww", "research-handoff", renamed, confirm=True)
        loaded = protocols.get_protocol(vault_with_roles, "research-handoff")
        assert loaded is not None
        assert loaded["name"] == "research-handoff"
        assert protocols.get_protocol(vault_with_roles, "other-name") is None

    def test_register_replaces_in_place(self, vault_with_roles, registry):
        protocols.register_protocol(
            vault_with_roles, "tww", _record(), confirm=True)
        protocols.register_protocol(
            vault_with_roles, "tww", _record(request_format="JSON"), confirm=True)
        files = list(registry.glob("*.yaml"))
        assert len(files) == 1
        loaded = protocols.get_protocol(
            vault_with_roles, "research-handoff")
        assert loaded is not None
        assert loaded["request_format"] == "JSON"


class TestProposeMode:
    def test_without_confirm_writes_nothing(self, vault_with_roles, registry):
        out = protocols.register_protocol(
            vault_with_roles, "tww", _record(), confirm=False)
        assert out["ok"] is True
        assert out["confirm_required"] is True
        assert list(registry.glob("*.yaml")) == []

    def test_propose_still_gates(self, vault_with_roles):
        rec = _record()  # non-party vault_manager
        with pytest.raises(PermissionDenied):
            protocols.register_protocol(
                vault_with_roles, "vault_manager", rec, confirm=False)

    def test_propose_still_validates(self, vault_with_roles):
        rec = _record()
        del rec["instructions"]
        with pytest.raises(protocols.ProtocolError):
            protocols.register_protocol(
                vault_with_roles, "tww", rec, confirm=False)


class TestListAndGet:
    def _seed_two(self, vault_with_roles):
        protocols.register_protocol(
            vault_with_roles, "tww", _record(), confirm=True)
        protocols.register_protocol(
            vault_with_roles, "tww",
            _record(name="creative-system",
                    requester={"profiles": ["tww"], "domains": []},
                    responder={"profiles": ["vault_manager"], "domains": []}),
            confirm=True)

    def test_list_returns_only_my_handoffs(self, vault_with_roles):
        self._seed_two(vault_with_roles)
        out = protocols.list_protocols(vault_with_roles, "tww")
        assert out["count"] == 2
        # vault_manager is a party of the second only
        out2 = protocols.list_protocols(vault_with_roles, "vault_manager")
        assert out2["count"] == 1
        assert out2["protocols"][0]["name"] == "creative-system"

    def test_list_peer_narrows(self, vault_with_roles):
        self._seed_two(vault_with_roles)
        out = protocols.list_protocols(
            vault_with_roles, "tww", peer="vault_manager")
        assert out["count"] == 1
        assert out["protocols"][0]["name"] == "creative-system"

    def test_list_summary_omits_instructions(self, vault_with_roles):
        protocols.register_protocol(
            vault_with_roles, "tww", _record(), confirm=True)
        out = protocols.list_protocols(vault_with_roles, "tww")
        assert "instructions" not in out["protocols"][0]

    def test_get_returns_full_record(self, vault_with_roles):
        protocols.register_protocol(
            vault_with_roles, "tww", _record(), confirm=True)
        rec = protocols.get_protocol(vault_with_roles, "research-handoff")
        assert rec["instructions"] == "REQUEST SIDE — ask.\nRESPONSE SIDE — answer."

    def test_get_missing_returns_none(self, vault_with_roles):
        assert protocols.get_protocol(vault_with_roles, "missing") is None

    def test_no_state_dir_lists_empty(self, para_vault_no_state):
        out = protocols.list_protocols(para_vault_no_state, "tww")
        assert out == {"protocols": [], "count": 0}


class TestAudit:
    def test_register_and_update_audited(self, vault_with_roles):
        protocols.register_protocol(
            vault_with_roles, "tww", _record(), confirm=True)
        protocols.update_protocol(
            vault_with_roles, "tww", "research-handoff",
            _record(response_format="JSON"), confirm=True)
        entries = audit.read_entries(vault_with_roles)
        actions = [e["action"] for e in entries]
        assert "protocol_register" in actions
        assert "protocol_update" in actions


class TestNoPollution:
    def test_records_invisible_to_note_walk(self, vault_with_roles):
        protocols.register_protocol(
            vault_with_roles, "tww", _record(), confirm=True)
        paths = [n.path for n in iter_notes(vault_with_roles)]
        assert all(not p.startswith(".state/") for p in paths)


class TestToolSurface:
    def test_read_via_tool(self, vault_with_roles):
        protocols.register_protocol(
            vault_with_roles, "tww", _record(), confirm=True)
        out = _call(plugin._handle_protocol, {
            "vault": str(vault_with_roles), "agent": "tww",
            "name": "research-handoff",
        })
        assert out["ok"] is True
        assert out["protocol"]["response_format"] == "findings + sources + summary"

    def test_register_via_tool_propose_then_confirm(
            self, vault_with_roles, registry):
        out = _call(plugin._handle_protocol, {
            "vault": str(vault_with_roles), "agent": "tww",
            "register": _record(),
        })
        assert out["ok"] is True
        assert out["confirm_required"] is True
        assert list(registry.glob("*.yaml")) == []

        out2 = _call(plugin._handle_protocol, {
            "vault": str(vault_with_roles), "agent": "tww",
            "register": _record(), "confirm": True,
        })
        assert out2["ok"] is True
        assert out2["action"] == "registered"

    def test_list_via_tool(self, vault_with_roles):
        protocols.register_protocol(
            vault_with_roles, "tww", _record(), confirm=True)
        out = _call(plugin._handle_protocol_list, {
            "vault": str(vault_with_roles), "agent": "tww",
        })
        assert out["count"] == 1

    def test_tool_refuses_unknown_agent(self, vault_with_roles):
        out = _call(plugin._handle_protocol, {
            "vault": str(vault_with_roles), "agent": "ghost",
            "name": "research-handoff",
        })
        assert out["ok"] is False
        assert out["error"] == "RolesError"

    def test_tool_refuses_non_party_write(self, vault_with_roles):
        out = _call(plugin._handle_protocol, {
            "vault": str(vault_with_roles), "agent": "vault_manager",
            "register": _record(), "confirm": True,
        })
        assert out["ok"] is False
        assert out["error"] == "permission_denied"
