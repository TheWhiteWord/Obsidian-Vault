"""Generated artifacts and scaffolding — spec §6, §10."""

from __future__ import annotations

import json

import pytest

from vault import audit
from vault.constants import GENERATED_MARKER
from vault.generate import (
    build_index,
    build_registry,
    is_generated,
    regenerate_indexes,
    write_index,
    write_registry,
)
from vault.grants import PermissionDenied, load_roles
from vault.scaffold import ScaffoldRefused, scaffold_folder
from vault.write import write_note

FM = {"type": "work", "kind": ["essay"], "status": "draft",
      "tags": ["test"], "created": "2026-08-02"}


@pytest.fixture
def roles(vault_with_roles):
    return load_roles(vault_with_roles)


class TestGeneratedMarker:
    def test_index_carries_the_marker(self, vault):
        assert build_index(vault, "CREATIVE/PHILOSOPHY").startswith(GENERATED_MARKER)

    def test_generated_files_are_detected(self, vault):
        write_index(vault, "CREATIVE/PHILOSOPHY")
        assert is_generated(vault / "CREATIVE/PHILOSOPHY/INDEX.md")

    def test_hand_authored_file_is_never_clobbered(self, vault):
        target = vault / "CREATIVE/PHILOSOPHY/INDEX.md"
        target.write_text("# My own index\nI wrote this by hand.\n")
        with pytest.raises(FileExistsError, match="not marked generated"):
            write_index(vault, "CREATIVE/PHILOSOPHY")
        assert "I wrote this by hand" in target.read_text()

    def test_generated_index_is_overwritten_freely(self, vault):
        write_index(vault, "CREATIVE/PHILOSOPHY")
        write_index(vault, "CREATIVE/PHILOSOPHY")      # must not raise


class TestIndexContent:
    def test_lists_notes_as_wikilinks(self, vault):
        text = build_index(vault, "CREATIVE/PHILOSOPHY")
        assert "[[recurrence]]" in text
        assert "[[aphorism]]" in text

    def test_shows_derived_tag_cloud(self, vault):
        text = build_index(vault, "CREATIVE/PHILOSOPHY")
        assert "#nietzsche (2)" in text

    def test_flags_malformed_notes(self, vault):
        (vault / "CREATIVE/PHILOSOPHY/broken.md").write_text("---\na: [b\n---\n")
        assert "Needs attention" in build_index(vault, "CREATIVE/PHILOSOPHY")

    def test_empty_folder_says_so(self, vault):
        (vault / "CREATIVE/EMPTY").mkdir()
        assert "No notes yet" in build_index(vault, "CREATIVE/EMPTY")

    def test_index_does_not_index_itself(self, vault):
        write_index(vault, "CREATIVE/PHILOSOPHY")
        text = build_index(vault, "CREATIVE/PHILOSOPHY")
        assert "[[INDEX]]" not in text
        assert "**2 notes**" in text        # not 3

    def test_regenerate_covers_every_note_folder(self, vault):
        written = regenerate_indexes(vault)
        assert any("CREATIVE/PHILOSOPHY" in p for p in written)
        assert any("CREATIVE/KNOWLEDGE" in p for p in written)


class TestRegistry:
    def test_describes_reality_not_intent(self, vault):
        text = build_registry(vault)
        assert "`aphorism` (1)" in text          # observed, unregistered
        assert "⚠ observed" in text

    def test_shows_inheritance_chain(self, vault):
        assert "Inherits:" in build_registry(vault)

    def test_written_to_a_configured_destination(self, vault):
        path = write_registry(vault, "SYSTEM/HANDBOOK")
        assert path == "SYSTEM/HANDBOOK/registry.md"
        assert is_generated(vault / path)


class TestWriteRefreshesIndex:
    def test_index_updates_after_a_write(self, vault_with_roles, roles):
        write_note(vault_with_roles, "tww", roles,
                   "CREATIVE/PHILOSOPHY/fresh.md", FM, "Body.")
        text = (vault_with_roles / "CREATIVE/PHILOSOPHY/INDEX.md").read_text()
        assert "[[fresh]]" in text

    def test_index_updates_after_a_delete(self, vault_with_roles, roles):
        from vault.write import delete_note
        write_note(vault_with_roles, "tww", roles,
                   "CREATIVE/PHILOSOPHY/temp.md", FM, "Body.")
        delete_note(vault_with_roles, "tww", roles, "CREATIVE/PHILOSOPHY/temp.md")

    def test_machinery_folders_never_get_an_index(self, vault_with_roles, roles):
        # Writing into a reserved engine folder (.state) must NOT spawn a
        # content-derived INDEX there — it is machinery, not a content tree.
        # (Reproduces the bug where a .state/INDEX.md appeared on audit writes.)
        write_note(vault_with_roles, "vault_manager", roles,
                   ".state/probe.md", FM, "x")
        assert not (vault_with_roles / ".state" / "INDEX.md").exists()
        (vault_with_roles / ".state" / "probe.md").unlink()


class TestAuditTrail:
    def test_writes_are_recorded(self, vault_with_roles, roles):
        write_note(vault_with_roles, "tww", roles,
                   "CREATIVE/PHILOSOPHY/logged.md", FM, "Body.")
        entries = audit.read_entries(vault_with_roles)
        assert entries[0]["agent"] == "tww"
        assert entries[0]["action"] == "create"

    def test_entries_are_filterable(self, vault_with_roles, roles):
        write_note(vault_with_roles, "tww", roles,
                   "CREATIVE/PHILOSOPHY/a.md", FM, "x")
        assert audit.read_entries(vault_with_roles, agent="nobody") == []

    def test_default_STATE_trail_always_written(self, vault_with_roles, roles):
        # The engine defaults to a root .state/ audit trail even without an
        # explicit paths.state — the manager (P4) needs it. Default is dot-
        # prefixed so it reads as machinery, not a content tree.
        write_note(vault_with_roles, "tww", roles,
                   "CREATIVE/PHILOSOPHY/a.md", FM, "x")
        log = vault_with_roles / ".state" / "audit-log.jsonl"
        assert log.exists()
        entries = audit.read_entries(vault_with_roles)
        assert len(entries) >= 1
        assert entries[0]["agent"] == "tww"

    def test_log_is_append_only_jsonl(self, vault_with_roles, roles):
        for name in ("one", "two"):
            write_note(vault_with_roles, "tww", roles,
                       f"CREATIVE/PHILOSOPHY/{name}.md", FM, "x")
        log = vault_with_roles / ".state" / "audit-log.jsonl"
        lines = [l for l in log.read_text().splitlines() if l.strip()]
        assert len(lines) == 2
        assert all(json.loads(l)["action"] == "create" for l in lines)


class TestScaffoldProposal:
    def test_proposal_writes_nothing(self, vault_with_roles, roles):
        out = scaffold_folder(vault_with_roles, "tww", roles,
                              "CREATIVE/NEWTHING", intent="a place for things")
        assert out["proposal"] is True
        assert not (vault_with_roles / "CREATIVE/NEWTHING").exists()

    def test_empty_delta_is_stated_plainly(self, vault_with_roles, roles):
        out = scaffold_folder(vault_with_roles, "tww", roles, "CREATIVE/PLAIN")
        assert out["delta"] == {}
        assert out["writes_config"] is False
        assert "inherits everything" in out["note"]

    def test_proposal_reports_what_is_inherited(self, vault_with_roles, roles):
        out = scaffold_folder(vault_with_roles, "tww", roles, "CREATIVE/PLAIN")
        assert "kind" in out["inherits"]["vocabularies"]

    def test_delta_strips_already_inherited_values(self, vault_with_roles, roles):
        out = scaffold_folder(
            vault_with_roles, "tww", roles, "CREATIVE/POETRY",
            proposed={"fields": {"kind": {"allowed": ["poem", "sonnet"]}}},
        )
        # 'poem' is already inherited from CREATIVE; only 'sonnet' is new
        assert out["delta"]["fields"]["kind"]["allowed"] == ["sonnet"]


class TestScaffoldCreation:
    def test_empty_delta_writes_no_config_file(self, vault_with_roles, roles):
        out = scaffold_folder(vault_with_roles, "tww", roles,
                              "CREATIVE/PLAIN", confirm=True)
        assert out["config"] is None
        assert out["inherits_only"] is True
        assert (vault_with_roles / "CREATIVE/PLAIN").is_dir()
        assert not (vault_with_roles / "CREATIVE/PLAIN/.vault").exists()

    def test_structural_delta_needs_user_confirmation(self, vault_with_roles, roles):
        with pytest.raises(ScaffoldRefused, match="needs explicit user confirmation"):
            scaffold_folder(
                vault_with_roles, "tww", roles, "CREATIVE/STRICT",
                proposed={"fields": {"mood": {"required": True}}},
                confirm=True,
            )

    def test_user_confirmed_structural_delta_proceeds(self, vault_with_roles, roles):
        out = scaffold_folder(
            vault_with_roles, "tww", roles, "CREATIVE/STRICT",
            proposed={"fields": {"mood": {"required": True}},
                      "user_confirmed": True},
            confirm=True,
        )
        assert out["config"] == "CREATIVE/STRICT/.vault/config.yaml"

    def test_scaffold_is_audited(self, vault_with_roles, roles):
        scaffold_folder(vault_with_roles, "tww", roles,
                        "CREATIVE/TRACKED", intent="why", confirm=True)
        entries = audit.read_entries(vault_with_roles, action="scaffold")
        assert entries[0]["intent"] == "why"


class TestScaffoldGrants:
    """§10.3 — vault_manager curates structure, never creates it."""

    def test_vault_manager_cannot_scaffold_a_domain(self, vault_with_roles, roles):
        with pytest.raises(PermissionDenied):
            scaffold_folder(vault_with_roles, "vault_manager", roles,
                            "CREATIVE/NEW", confirm=True)

    def test_agent_cannot_scaffold_outside_its_tree(self, vault_with_roles, roles):
        with pytest.raises(PermissionDenied):
            scaffold_folder(vault_with_roles, "tww", roles,
                            "SYSTEM/NEW", confirm=True)

    def test_cannot_scaffold_into_config_dir(self, vault_with_roles, roles):
        from vault.paths import VaultPathError
        with pytest.raises(VaultPathError):
            scaffold_folder(vault_with_roles, "tww", roles,
                            "CREATIVE/.vault/sneaky", confirm=True)
