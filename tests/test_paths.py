"""Case-insensitive path resolution — vault/paths.py ``safe_join``.

Folder casing is cosmetic: a caller may name a path in any casing and it
resolves to the real on-disk name. The escape guards stay intact.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vault.paths import VaultPathError, safe_join


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "WORK/CREATIVE/projects").mkdir(parents=True)
    return tmp_path


class TestCaseCorrection:
    def test_exact_case_unchanged(self, tree):
        assert safe_join(tree, "WORK/CREATIVE/projects") == \
            tree / "WORK/CREATIVE/projects"

    def test_existing_segments_resolve_to_real_case(self, tree):
        p = safe_join(tree, "work/creative/projects/x.md")
        assert p == tree / "WORK/CREATIVE/projects/x.md"

    def test_nonexistent_segment_keeps_given_case(self, tree):
        p = safe_join(tree, "WORK/creative/NewFolder")
        assert p == tree / "WORK/CREATIVE/NewFolder"

    def test_root_and_dot(self, tree):
        assert safe_join(tree, "") == tree
        assert safe_join(tree, ".") == tree

    def test_collision_picks_deterministically(self, tree):
        (tree / "WORK/CREATIVE/ideas").mkdir()
        (tree / "WORK/CREATIVE/Ideas").mkdir()
        # The requested name exists exactly — kept as-is.
        assert safe_join(tree, "WORK/CREATIVE/ideas") == \
            tree / "WORK/CREATIVE/ideas"
        # A non-exact spelling resolves to the first in (casefolded, real
        # name) order: "Ideas" < "ideas". The maintain sweep flags the
        # collision; the pick is just deterministic.
        assert safe_join(tree, "WORK/CREATIVE/IDEAS") == \
            tree / "WORK/CREATIVE/Ideas"

    def test_escapes_still_refused(self, tree):
        with pytest.raises(VaultPathError):
            safe_join(tree, "../outside")
        with pytest.raises(VaultPathError):
            safe_join(tree, "/absolute")
