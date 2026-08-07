"""Adversarial permission tests.

Every agent attempts every forbidden operation. All must be refused **by
code**, not discouraged by prose. If any test here goes green by accident, the
boundary is theatre.
"""

from __future__ import annotations

import pytest

from vault.grants import PermissionDenied, RolesError, load_roles
from vault.write import WriteRefused, delete_note, edit_metadata, write_note

GOOD_FM = {
    "type": "note",
    "kind": ["note"],
    "status": "draft",
    "tags": ["test"],
    "created": "2026-08-02",
}


@pytest.fixture
def roles(vault_with_roles):
    return load_roles(vault_with_roles)


class TestWriteBoundary:
    """An out-of-domain write is refused by code."""

    def test_tww_cannot_write_into_system(self, vault_with_roles, roles):
        with pytest.raises(PermissionDenied, match="may not create"):
            write_note(vault_with_roles, "tww", roles,
                       "SYSTEM/HANDBOOK/sneaky.md", GOOD_FM)

    def test_system_cannot_write_into_creative(self, vault_with_roles, roles):
        with pytest.raises(PermissionDenied, match="may not create"):
            write_note(vault_with_roles, "system", roles,
                       "CREATIVE/PHILOSOPHY/sneaky.md", GOOD_FM)

    def test_tww_can_write_its_own_domain(self, vault_with_roles, roles):
        out = write_note(vault_with_roles, "tww", roles,
                         "CREATIVE/PHILOSOPHY/mine.md", GOOD_FM, "Body.")
        assert out.created is True

    def test_unknown_agent_is_refused(self, vault_with_roles, roles):
        with pytest.raises(RolesError, match="unknown agent"):
            write_note(vault_with_roles, "intruder", roles,
                       "CREATIVE/PHILOSOPHY/x.md", GOOD_FM)

    def test_no_roles_file_denies_everything(self, vault, tmp_path):
        empty = load_roles(vault)          # fixture has no roles.yaml
        with pytest.raises(RolesError):
            write_note(vault, "tww", empty, "CREATIVE/PHILOSOPHY/x.md", GOOD_FM)


class TestCaseTolerance:
    """Folder casing is cosmetic: grants match case-insensitively and
    writes resolve to the real on-disk folder — never a shadow tree."""

    def test_write_with_different_case_lands_in_real_folder(
            self, vault_with_roles, roles):
        out = write_note(vault_with_roles, "tww", roles,
                         "creative/philosophy/case-tolerance.md",
                         GOOD_FM, "Body.")
        assert out.created is True
        assert (vault_with_roles
                / "CREATIVE/PHILOSOPHY/case-tolerance.md").is_file()
        # No parallel lowercase tree appeared.
        assert not (vault_with_roles / "creative").exists()
        # The tool reports the real on-disk casing back.
        assert out.path == "CREATIVE/PHILOSOPHY/case-tolerance.md"

    def test_edit_with_different_case_finds_the_same_note(
            self, vault_with_roles, roles):
        write_note(vault_with_roles, "tww", roles,
                   "CREATIVE/PHILOSOPHY/case-edit.md", GOOD_FM, "First body.")
        out = write_note(vault_with_roles, "tww", roles,
                         "creative/philosophy/case-edit.md",
                         GOOD_FM, "Edited body.", overwrite=True)
        assert out.created is False
        text = (vault_with_roles / "CREATIVE/PHILOSOPHY/case-edit.md").read_text(
            encoding="utf-8")
        assert "Edited body." in text
        assert "First body." not in text
        assert len(list((vault_with_roles / "CREATIVE/PHILOSOPHY")
                        .glob("case-edit*"))) == 1


class TestAppendSemantics:
    """`append` creates; it must never edit or delete (§2.1).

    P7: creation inside an owned scope is the owner's — the
    legacy cross-tree ``*/ISSUES/**`` pattern is shadowed. Append now
    operates only where no ownership glob matches (an unowned tree), so the
    semantics tests use ``MISC/ISSUES`` (no canonical owner); the shadowing
    denial uses ``SYSTEM/ISSUES`` (owned by ``system``).
    """

    def test_append_allows_creating_an_issue(self, vault_with_roles, roles):
        out = write_note(vault_with_roles, "tww", roles,
                         "MISC/ISSUES/broken-thing.md",
                         {**GOOD_FM, "kind": ["issue"], "status": "open"})
        assert out.created is True

    def test_append_cannot_edit_an_existing_note(self, vault_with_roles, roles):
        write_note(vault_with_roles, "tww", roles, "MISC/ISSUES/one.md",
                   {**GOOD_FM, "kind": ["issue"], "status": "open"})
        with pytest.raises(PermissionDenied, match="may not edit"):
            write_note(vault_with_roles, "tww", roles, "MISC/ISSUES/one.md",
                       {**GOOD_FM, "kind": ["issue"], "status": "resolved"},
                       overwrite=True)

    def test_append_cannot_delete_even_its_own_note(self, vault_with_roles, roles):
        write_note(vault_with_roles, "tww", roles, "MISC/ISSUES/two.md",
                   {**GOOD_FM, "kind": ["issue"], "status": "open"})
        with pytest.raises(PermissionDenied, match="may not delete"):
            delete_note(vault_with_roles, "tww", roles, "MISC/ISSUES/two.md")

    def test_append_is_shadowed_outside_own_scope(self, vault_with_roles, roles):
        # P7: SYSTEM is owned by `system`; tww's append */ISSUES/** is a
        # capability glob and grants nothing inside an owned scope.
        with pytest.raises(PermissionDenied, match="scope is owned by system"):
            write_note(vault_with_roles, "tww", roles,
                       "SYSTEM/ISSUES/broken-thing.md",
                       {**GOOD_FM, "kind": ["issue"], "status": "open"})


class TestMetaGrantCannotTouchProse:
    """`meta` is the vault manager's hard constraint (§2.2)."""

    def test_meta_edit_leaves_body_byte_identical(self, vault_with_roles, roles):
        path = vault_with_roles / "CREATIVE/PHILOSOPHY/recurrence.md"
        original_body = path.read_text().split("---", 2)[2]

        edit_metadata(vault_with_roles, "vault_manager", roles,
                      "CREATIVE/PHILOSOPHY/recurrence.md",
                      {"status": "active"})

        assert path.read_text().split("---", 2)[2] == original_body

    def test_meta_can_change_frontmatter(self, vault_with_roles, roles):
        edit_metadata(vault_with_roles, "vault_manager", roles,
                      "CREATIVE/PHILOSOPHY/recurrence.md",
                      {"status": "active"})
        text = (vault_with_roles / "CREATIVE/PHILOSOPHY/recurrence.md").read_text()
        assert "status: active" in text

    def test_vault_manager_cannot_write_prose_in_a_domain(self, vault_with_roles, roles):
        with pytest.raises(PermissionDenied, match="may not create"):
            write_note(vault_with_roles, "vault_manager", roles,
                       "CREATIVE/PHILOSOPHY/essay.md", GOOD_FM, "I wrote this.")

    def test_agent_without_meta_grant_cannot_use_it(self, vault_with_roles, roles):
        with pytest.raises(PermissionDenied, match="requires 'meta'"):
            edit_metadata(vault_with_roles, "tww", roles,
                          "SYSTEM/HANDBOOK/design.md", {"status": "active"})


class TestConfigGrant:
    """Only `config` holders may extend a vocabulary (§3.7)."""

    def test_registration_requires_the_config_grant(self, vault_with_roles, roles):
        # `system` owns SYSTEM but holds no config grant → refused for the
        # grant, exactly as before (P7: the agent is the owner, so shadowing
        # is not the reason).
        with pytest.raises(PermissionDenied, match="requires 'config'"):
            write_note(vault_with_roles, "system", roles,
                       "SYSTEM/HANDBOOK/new.md",
                       {**GOOD_FM, "kind": ["aphorism"]},
                       register={"kind": "aphorism"})

    def test_owner_with_config_can_register(self, vault_with_roles, roles):
        # D-5/P7: the domain owner holds config on its own tree — registering
        # in its own domain succeeds.
        out = write_note(vault_with_roles, "tww", roles,
                         "CREATIVE/PHILOSOPHY/new.md",
                         {**GOOD_FM, "kind": ["aphorism"]},
                         register={"kind": "aphorism"})
        assert out.registered == {"kind": "aphorism"}

    def test_vault_manager_may_register(self, vault_with_roles, roles):
        out = write_note(vault_with_roles, "vault_manager", roles,
                         ".state/probe.md",
                         {**GOOD_FM, "kind": ["telemetry"]},
                         register={"kind": "telemetry"})
        assert out.registered == {"kind": "telemetry"}
        text = (vault_with_roles / ".vault/config.yaml").read_text()
        assert "telemetry" in text          # landed in the tree, not the root

    def test_cannot_register_into_a_restricted_field(self, vault_with_roles, roles):
        """KNOWLEDGE restricts `type` via allowed_only — no extending it."""
        with pytest.raises((WriteRefused, PermissionDenied), match="restricted|may not"):
            write_note(vault_with_roles, "vault_manager", roles,
                       "SYSTEM/KNOWLEDGE/x.md",
                       {**GOOD_FM, "type": "invented", "source": "s",
                        "retrieved": "2026-08-02"},
                       register={"type": "invented"})


class TestPathEscapes:
    def test_traversal_in_write_is_refused(self, vault_with_roles, roles):
        from vault.paths import VaultPathError
        with pytest.raises(VaultPathError, match="escapes"):
            write_note(vault_with_roles, "tww", roles,
                       "CREATIVE/../../etc/evil.md", GOOD_FM)

    def test_cannot_write_into_config_dir(self, vault_with_roles, roles):
        from vault.paths import VaultPathError
        with pytest.raises(VaultPathError, match="config, not content"):
            write_note(vault_with_roles, "vault_manager", roles,
                       "CREATIVE/PHILOSOPHY/.vault/config.yaml", GOOD_FM)


class TestGlobSemantics:
    """`*` must not cross separators; `**` must."""

    def test_star_matches_one_segment_only(self, roles):
        g = roles.get("tww")
        assert g.matches("append", "SYSTEM/ISSUES/x.md")
        assert g.matches("append", "CREATIVE/ISSUES/x.md")
        assert not g.matches("append", "SYSTEM/HANDBOOK/ISSUES/x.md")

    def test_doublestar_crosses_separators(self, roles):
        g = roles.get("system")
        assert g.matches("read", "CREATIVE/PHILOSOPHY/deep/nested/note.md")

    def test_read_is_wider_than_write(self, roles):
        g = roles.get("tww")
        assert g.matches("read", "SYSTEM/KNOWLEDGE/api.md")
        assert not g.matches("write", "SYSTEM/KNOWLEDGE/api.md")
        assert not g.matches("read", "SYSTEM/HANDBOOK/design.md")

    def test_filter_readable_is_silent(self, roles):
        visible = roles.filter_readable("tww", [
            "CREATIVE/PHILOSOPHY/a.md",
            "SYSTEM/KNOWLEDGE/b.md",
            "SYSTEM/HANDBOOK/c.md",
        ])
        assert visible == ["CREATIVE/PHILOSOPHY/a.md", "SYSTEM/KNOWLEDGE/b.md"]


class TestScopeMatches:
    """P3.8 — the search-scope glob language: positives plus `!` exclusions."""

    def test_positive_pattern_only(self):
        from vault.grants import scope_matches
        assert scope_matches(["CREATIVE/**"], "CREATIVE/PHILOSOPHY/a.md")
        assert not scope_matches(["CREATIVE/**"], "SYSTEM/HANDBOOK/a.md")

    def test_exclusion_removes(self):
        from vault.grants import scope_matches
        assert not scope_matches(["**", "!CREATIVE/KNOWLEDGE/**"],
                                 "CREATIVE/KNOWLEDGE/kant-on-time.md")
        assert scope_matches(["**", "!CREATIVE/KNOWLEDGE/**"],
                             "CREATIVE/PHILOSOPHY/a.md")

    def test_empty_or_exclusion_only_matches_nothing(self):
        from vault.grants import scope_matches
        assert not scope_matches([], "CREATIVE/PHILOSOPHY/a.md")
        assert not scope_matches(["!**"], "CREATIVE/PHILOSOPHY/a.md")

    def test_star_vs_doublestar_in_negation(self):
        from vault.grants import scope_matches
        # '*' does not cross separators: '!*/design.md' excludes only notes
        # one segment deep, '!**/design.md' excludes at any depth.
        assert not scope_matches(["**", "!*/design.md"], "SYSTEM/design.md")
        assert scope_matches(["**", "!*/design.md"], "SYSTEM/HANDBOOK/design.md")
        assert scope_matches(["**", "!*/design.md"], "SYSTEM/HANDBOOK/deep/design.md")
        assert not scope_matches(["**", "!**/design.md"],
                                 "SYSTEM/HANDBOOK/deep/design.md")

    def test_folder_self_is_excluded_by_trailing_slash_glob(self):
        from vault.grants import scope_matches
        # the shared trailing-/** convenience applies to exclusions too
        assert not scope_matches(["**", "!CREATIVE/KNOWLEDGE/**"],
                                 "CREATIVE/KNOWLEDGE")

    def test_grant_patterns_are_positive_only(self):
        from vault.grants import path_matches
        # a '!' inside a grant pattern is a literal that matches nothing —
        # negation lives in search scopes, never grants (deny-by-default)
        assert not path_matches("!CREATIVE/**", "CREATIVE/PHILOSOPHY/a.md")
