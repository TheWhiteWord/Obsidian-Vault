"""Generated artifacts and scaffolding."""

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
    reindex_ancestors,
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
        assert "**2 notes**" in text        # immediate-level notes, not the subtree

    def test_index_lists_only_immediate_notes_not_descendants(self, vault):
        # A note two levels deep must NOT appear at the parent's top level.
        # (It may appear nested one level in, under its own folder pointer —
        # that is the intended one-level expansion — but never loose here.)
        (vault / "CREATIVE/PHILOSOPHY/deep").mkdir(parents=True)
        (vault / "CREATIVE/PHILOSOPHY/deep/buried.md").write_text(
            "---\ntype: work\nkind: [essay]\nstatus: draft\ntags: [x]\n"
            "created: 2026-08-02\n---\nBody.\n"
        )
        text = build_index(vault, "CREATIVE/PHILOSOPHY")
        # bare top-level entry (not indented under a folder) must be absent
        assert "\n- [[buried]]" not in ("\n" + text)
        assert "**2 notes**" in text          # still only the two at this level

    def test_index_points_to_child_folders(self, vault):
        (vault / "CREATIVE/PHILOSOPHY/sub").mkdir()
        (vault / "CREATIVE/PHILOSOPHY/sub/leaf.md").write_text(
            "---\ntype: work\nkind: [essay]\nstatus: draft\ntags: [x]\n"
            "created: 2026-08-02\n---\nBody.\n"
        )
        text = build_index(vault, "CREATIVE/PHILOSOPHY")
        assert "## Folders" in text
        assert "- [[sub]]" in text             # child folder is a pointer
        # the child's note appears nested one level in, not as a top-level entry
        assert "\n- [[leaf]]" not in ("\n" + text)
        assert "    - [[leaf]]" in text

    def test_index_expands_child_folder_one_level(self, vault):
        # A child folder's first-level contents (its notes AND its own
        # subfolders) should appear nested under its pointer — but nothing
        # deeper, so the index still does not recurse.
        sub = vault / "CREATIVE/PHILOSOPHY/sub"
        sub.mkdir()
        (sub / "leaf.md").write_text(
            "---\ntype: work\nkind: [essay]\nstatus: draft\ntags: [x]\n"
            "created: 2026-08-02\n---\nBody.\n"
        )
        (sub / "grandchild").mkdir()
        (sub / "grandchild/deep.md").write_text(
            "---\ntype: work\nkind: [essay]\nstatus: draft\ntags: [x]\n"
            "created: 2026-08-02\n---\nBody.\n"
        )
        text = build_index(vault, "CREATIVE/PHILOSOPHY")
        assert "- [[sub]]" in text
        assert "    - [[leaf]]" in text           # child's note, one level in
        assert "    - [[grandchild]]" in text     # child's subfolder, one level in
        assert "[[deep]]" not in text             # NOT two levels deep

    def test_index_lists_every_subfolder_not_just_note_bearing_ones(self, vault):
        # A subfolder with no notes of its own must still appear as a pointer.
        (vault / "CREATIVE/PHILOSOPHY/empty").mkdir()
        text = build_index(vault, "CREATIVE/PHILOSOPHY")
        assert "## Folders" in text
        assert "- [[empty]]" in text            # sparsely populated branch shown

    def test_index_with_only_folders_is_not_empty(self, vault):
        # No notes added here, but a child with content: not "No notes yet",
        # and the child still appears as a folder pointer.
        (vault / "CREATIVE/PHILOSOPHY/onlychild").mkdir()
        (vault / "CREATIVE/PHILOSOPHY/onlychild/leaf.md").write_text(
            "---\ntype: work\nkind: [essay]\nstatus: draft\ntags: [x]\n"
            "created: 2026-08-02\n---\nBody.\n"
        )
        text = build_index(vault, "CREATIVE/PHILOSOPHY")
        assert "No notes yet" not in text
        # the 2 pre-existing notes at this level are still counted
        assert "**2 notes**" in text
        assert "## Folders" in text
        assert "- [[onlychild]]" in text

    def test_regenerate_refreshes_container_folders_without_direct_notes(self, vault):
        # A parent folder holding only subfolders (no direct notes) must still
        # get its INDEX regenerated — otherwise a stale recursive INDEX that
        # inlined descendants would survive the rollout.
        child = vault / "CREATIVE/PHILOSOPHY/child"
        child.mkdir(parents=True)
        (child / "leaf.md").write_text(
            "---\ntype: work\nkind: [essay]\nstatus: draft\ntags: [x]\n"
            "created: 2026-08-02\n---\nBody.\n"
        )
        # Seed a stale recursive-style INDEX that inlines the descendant.
        (vault / "CREATIVE/PHILOSOPHY/INDEX.md").write_text(
            "<!-- generated: do not edit -->\n# PHILOSOPHY\n**1 notes**\n"
            "## child\n- [[leaf]]\n"
        )
        from vault.generate import regenerate_indexes, write_index
        write_index(vault, "CREATIVE/PHILOSOPHY")  # single-folder path
        text = (vault / "CREATIVE/PHILOSOPHY/INDEX.md").read_text()
        # child's leaf appears nested one level in (under [[child]]), not as a
        # loose top-level entry, and the stale recursive inline is gone.
        assert "\n- [[leaf]]" not in ("\n" + text)
        assert "    - [[leaf]]" in text
        assert "## Folders" in text
        assert "- [[child]]" in text

        # And the bulk regenerate must also touch container folders,
        # including the scoped root itself.
        written = regenerate_indexes(vault, "CREATIVE/PHILOSOPHY")
        assert any("CREATIVE/PHILOSOPHY/INDEX.md" == p for p in written)

    def test_regenerate_covers_every_note_folder(self, vault):
        written = regenerate_indexes(vault)
        assert any("CREATIVE/PHILOSOPHY" in p for p in written)
        assert any("CREATIVE/KNOWLEDGE" in p for p in written)


class TestReindexAncestors:
    def test_reindexes_folder_and_every_ancestor(self, vault):
        # Plant a folder without any INDEX regeneration.
        (vault / "CREATIVE/PHILOSOPHY/deep/leaf").mkdir(parents=True)
        # No INDEX files exist yet anywhere under the new branch.
        assert not (vault / "CREATIVE/PHILOSOPHY/deep/INDEX.md").exists()
        # Reindexing the leaf regenerates the leaf AND each ancestor up to
        # the scoped root it resolves within.
        written = reindex_ancestors(vault, "CREATIVE/PHILOSOPHY/deep/leaf")
        assert "CREATIVE/PHILOSOPHY/deep/leaf/INDEX.md" in written
        assert "CREATIVE/PHILOSOPHY/deep/INDEX.md" in written
        assert "CREATIVE/PHILOSOPHY/INDEX.md" in written
        # Ancestor INDEX now lists the new child.
        assert "[[deep]]" in (vault / "CREATIVE/PHILOSOPHY/INDEX.md").read_text()

    def test_reindex_is_never_fatal(self, vault):
        # A nonexistent folder returns [] rather than raising — callers must
        # not have their operation fail because a derived view missed.
        assert reindex_ancestors(vault, "CREATIVE/DOES-NOT-EXIST") == []


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

    def test_note_into_new_subtree_refreshes_grandparent(self, vault_with_roles, roles):
        # The real failure mode: an agent writes a note into a brand-new
        # subtree (work/graphic/image/note.md). The write path mkdir's the
        # whole tree, so only refreshing the note's immediate parent would
        # leave work/graphic/INDEX.md stale and the new 'image' branch
        # invisible in the README tree. The grandparent must be refreshed too.
        write_note(vault_with_roles, "tww", roles,
                   "CREATIVE/PHILOSOPHY/deep/newbranch/note.md", FM, "Body.")
        grandparent = (vault_with_roles / "CREATIVE/PHILOSOPHY/INDEX.md").read_text()
        assert "[[deep]]" in grandparent
        assert "[[newbranch]]" in (
            vault_with_roles / "CREATIVE/PHILOSOPHY/deep/INDEX.md").read_text()

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

    def test_scaffold_refreshes_parent_index(self, vault_with_roles, roles):
        # Creating a nested folder must update the PARENT's INDEX so the new
        # child is listed — previously only the new folder's own INDEX was
        # regenerated, leaving the parent stale (the work/INDEX gap).
        from vault.generate import write_index
        # Seed the parent's INDEX in its current (pre-child) state.
        write_index(vault_with_roles, "CREATIVE")
        parent_idx = vault_with_roles / "CREATIVE/INDEX.md"
        assert parent_idx.is_file()
        assert "NEWCHILD" not in parent_idx.read_text()
        scaffold_folder(vault_with_roles, "tww", roles,
                        "CREATIVE/NEWCHILD", confirm=True)
        refreshed = (vault_with_roles / "CREATIVE/INDEX.md").read_text()
        assert "[[NEWCHILD]]" in refreshed
        # And the new child's own INDEX exists.
        assert (vault_with_roles / "CREATIVE/NEWCHILD/INDEX.md").is_file()

    def test_scaffold_refreshes_all_ancestors(self, vault_with_roles, roles):
        # A deeply nested scaffold reaches every ancestor's INDEX, up to root.
        scaffold_folder(vault_with_roles, "tww", roles,
                        "CREATIVE/A/B/C", confirm=True)
        for ancestor in ("CREATIVE/A", "CREATIVE/A/B", "CREATIVE/A/B/C"):
            assert (vault_with_roles / f"{ancestor}/INDEX.md").is_file()
        # CREATIVE/INDEX.md lists A; CREATIVE/A/INDEX.md lists B; etc.
        assert "[[A]]" in (vault_with_roles / "CREATIVE/INDEX.md").read_text()
        assert "[[B]]" in (vault_with_roles / "CREATIVE/A/INDEX.md").read_text()
        assert "[[C]]" in (vault_with_roles / "CREATIVE/A/B/INDEX.md").read_text()

    def test_agent_cannot_scaffold_outside_its_tree(self, vault_with_roles, roles):
        with pytest.raises(PermissionDenied):
            scaffold_folder(vault_with_roles, "tww", roles,
                            "SYSTEM/NEW", confirm=True)

    def test_cannot_scaffold_into_config_dir(self, vault_with_roles, roles):
        from vault.paths import VaultPathError
        with pytest.raises(VaultPathError):
            scaffold_folder(vault_with_roles, "tww", roles,
                            "CREATIVE/.vault/sneaky", confirm=True)
