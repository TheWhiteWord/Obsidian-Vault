"""P7 — derived ownership resolver + shadowing (spec 07 §2.2–2.3).

The resolver is pure (no filesystem); shadowing is pinned through
``RoleRegistry.check`` so the enforcement point is covered, not just the
function.
"""

from __future__ import annotations

import pytest

from vault.grants import Grants, PermissionDenied, RoleRegistry
from vault.ownership import (
    duplicate_ownership_globs,
    is_ownership_glob,
    owner_of,
)


def _registry(agents) -> RoleRegistry:
    return RoleRegistry(
        agents={name: Grants(name, grants) for name, grants in agents.items()}
    )


class TestIsOwnershipGlob:
    def test_canonical_shapes(self):
        for p in (
            "work/creative/**",
            "work/creative/knowledge/**",
            "system/**",
            "README.md",
            "work/creative",  # bare literal = the folder itself
            "work/**",        # the work root — least specific, domains override
        ):
            assert is_ownership_glob(p), p

    def test_non_canonical(self):
        for p in (
            "work/*/knowledge/**",   # wildcard — capability only
            "**",                    # no literal anchor
            "*",
            "work/creative/deep/x/**",  # four segments — deeper than a subdomain
            "work/cre*ative/**",
            "work/crea?tive/**",
            "work/creative/[]/**",
            "",
            "/",
        ):
            assert not is_ownership_glob(p), p


class TestOwnerOf:
    def test_no_globs_no_owner(self):
        assert owner_of({}, "work/creative/note.md") is None

    def test_capability_globs_never_establish_ownership(self):
        # The old researcher overlap: wildcard write glob, no canonical globs.
        globs = {"researcher": ["work/*/knowledge/**"]}
        assert owner_of(globs, "work/creative/knowledge/kant.md") is None

    def test_most_segments_wins(self):
        globs = {
            "writer": ["work/creative/**"],
            "researcher": ["work/creative/knowledge/**"],
        }
        assert owner_of(globs, "work/creative/knowledge/kant.md") == "researcher"
        assert owner_of(globs, "work/creative/projects/idea.md") == "writer"
        assert owner_of(globs, "work/creative/knowledge") == "researcher"

    def test_single_segment_domain(self):
        globs = {"default": ["system/**", "README.md"]}
        assert owner_of(globs, "system/handbook/design.md") == "default"
        assert owner_of(globs, "system") == "default"
        assert owner_of(globs, "README.md") == "default"

    def test_unmatched_path_has_no_owner(self):
        globs = {"writer": ["work/creative/**"]}
        assert owner_of(globs, "work/coding/note.md") is None
        assert owner_of(globs, "work") is None

    def test_matching_is_case_insensitive(self):
        # Folder casing is cosmetic: a rename (creative → Creative) never
        # breaks ownership — the glob still resolves to the same owner.
        globs = {"writer": ["work/creative/**"]}
        assert owner_of(globs, "work/Creative/projects/idea.md") == "writer"
        assert owner_of(globs, "WORK/CREATIVE/projects/idea.md") == "writer"
        assert owner_of(globs, "WORK/creative/knowledge/k.md") == "writer"

    def test_deterministic_tie_break(self):
        # A duplicate is refused at bind; the resolver still picks one agent
        # deterministically (lexicographic) rather than blowing up.
        globs = {"zed": ["work/creative/**"], "ann": ["work/creative/**"]}
        assert owner_of(globs, "work/creative/note.md") == "ann"


class TestDuplicateOwnershipGlobs:
    def test_duplicate_across_agents_is_a_conflict(self):
        conflicts = duplicate_ownership_globs(
            {"a": ["work/creative/**"], "b": ["work/creative/**"]}
        )
        assert len(conflicts) == 1
        assert "work/creative/**" in conflicts[0]

    def test_nested_depths_are_not_a_conflict(self):
        # work/<d>/** and work/<d>/<s>/** is the design, not a tie.
        assert duplicate_ownership_globs(
            {"writer": ["work/creative/**"],
             "researcher": ["work/creative/knowledge/**"]}
        ) == []

    def test_wildcards_are_ignored(self):
        assert duplicate_ownership_globs(
            {"a": ["work/*/knowledge/**"], "b": ["work/*/knowledge/**"]}
        ) == []

    def test_case_variants_are_the_same_scope(self):
        # Two agents holding the same scope in different casing would make
        # ownership ambiguous — matching is case-insensitive, so the globs
        # are one scope and bind must refuse.
        conflicts = duplicate_ownership_globs(
            {"a": ["work/creative/**"], "b": ["work/Creative/**"]}
        )
        assert len(conflicts) == 1


class TestShadowing:
    def _nested(self) -> RoleRegistry:
        return _registry({
            "writer": {
                "write": ["work/creative/**"],
                "config": ["work/creative/**"],
                "read": ["work/creative/**"],
            },
            "researcher": {
                "write": ["work/creative/knowledge/**"],
                "config": ["work/creative/knowledge/**"],
                "read": ["work/creative/**"],   # read over the parent (N-4)
            },
        })

    def test_owner_writes_own_scope(self):
        roles = self._nested()
        assert roles.allows("writer", "edit", "work/creative/projects/idea.md")
        assert roles.allows("researcher", "create", "work/creative/knowledge/k.md")

    def test_non_owner_shadowed_by_capability(self):
        # The researcher holds the old wildcard overlap as a capability glob
        # — it must not grant write inside the writer's owned scope.
        roles = _registry({
            "writer": {"write": ["work/creative/**"]},
            "researcher": {"write": ["work/*/knowledge/**"]},
        })
        assert roles.allows("researcher", "create",
                            "work/creative/knowledge/k.md") is False
        with pytest.raises(PermissionDenied, match="scope is owned by writer"):
            roles.check("researcher", "create", "work/creative/knowledge/k.md")

    def test_writer_shadowed_inside_subdomain(self):
        roles = self._nested()
        assert roles.allows("writer", "create", "work/creative/knowledge/k.md") is False
        assert roles.allows("writer", "edit", "work/creative/knowledge/k.md") is False

    def test_config_is_shadowed_too(self):
        roles = self._nested()
        assert roles.allows("writer", "edit_config",
                            "work/creative/knowledge/.vault/config.yaml") is False
        assert roles.allows("researcher", "edit_config",
                            "work/creative/knowledge/.vault/config.yaml")

    def test_append_is_shadowed(self):
        roles = _registry({
            "owner": {"write": ["work/creative/**"]},
            "reporter": {"append": ["*/ISSUES/**"]},
        })
        assert roles.allows("reporter", "create", "work/creative/ISSUES/x.md") is False
        assert roles.allows("owner", "create", "work/creative/ISSUES/x.md")

    def test_read_stays_generous(self):
        roles = self._nested()
        # writer has read over work/creative/** — the subdomain is inside it.
        assert roles.allows("writer", "read", "work/creative/knowledge/k.md")
        # researcher reads the whole parent (N-4).
        assert roles.allows("researcher", "read", "work/creative/projects/idea.md")

    def test_meta_stays_generous(self):
        roles = _registry({
            "writer": {"write": ["work/creative/**"]},
            "researcher": {"write": ["work/creative/knowledge/**"]},
            "manager": {"meta": ["**"], "read": ["**"]},
        })
        # The manager's meta backstop works inside the subdomain; the writer's
        # meta over the domain would too (bind adds meta in the preset).
        assert roles.allows("manager", "edit_meta",
                            "work/creative/knowledge/k.md")
        assert roles.allows("writer", "edit_meta",
                            "work/creative/knowledge/k.md") is False  # no meta grant yet

    def test_unbind_lifts_shadowing(self):
        # Removing the subdomain ownership glob restores the parent's write.
        roles = _registry({
            "writer": {"write": ["work/creative/**"]},
        })
        assert roles.allows("writer", "create", "work/creative/knowledge/k.md")

    def test_unowned_scope_capability_still_works(self):
        # No canonical globs anywhere → the old overlap model is unchanged.
        roles = _registry({
            "researcher": {"write": ["work/*/knowledge/**"]},
        })
        assert roles.allows("researcher", "create", "work/creative/knowledge/k.md")
