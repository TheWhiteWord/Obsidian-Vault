"""missed_connection pervasive-tag filter.

Locks the fix in docs/design/optimize-suggestions-reprise.md: a tag carried by
most notes *within a project unit* is structural (project/section label), not
a connection signal, so siblings sharing only it must not raise
missed_connection. Specific shared tags (incl. across projects) still surface.

These tests build their own throwaway vault so the behaviour is deterministic
and not sensitive to fixtures' pre-existing notes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from vault import maintain


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.lstrip(), encoding="utf-8")


def _seed(v: Path) -> None:
    (v / ".vault").mkdir(parents=True)
    (v / ".vault/config.yaml").write_text(
        "fields:\n"
        "  type: {required: true, allowed: [note, work]}\n"
        "  kind: {required: true, multi: true, allowed: [concept, premise]}\n"
        "  status: {required: true, allowed: [draft]}\n"
        "  tags: {required: true, multi: true}\n"
        "  created: {required: true, format: date}\n",
        encoding="utf-8",
    )


class TestMissedConnectionPervasive:
    def test_project_wide_label_not_a_missed_connection(self, tmp_path: Path):
        # Two sibling notes in a work/.../projects/<name> unit that share only
        # the project label + a section label. Before the filter this raised a
        # missed_connection (the ~50 boilerplate suggestions across TV Series /
        # short stories). After, it must not.
        v = tmp_path
        _seed(v)
        unit = v / "work/creative/projects/tv-series"
        _write(unit / "01-premise/the-central-irony.md", """
---
type: note
kind: [premise]
status: draft
tags: [the-writing-is-on-the-wall, tv-series, premise]
created: 2026-08-02
---
Body.
""")
        _write(unit / "01-premise/the-event.md", """
---
type: note
kind: [premise]
status: draft
tags: [the-writing-is-on-the-wall, tv-series, premise]
created: 2026-08-02
---
Body.
""")
        findings = maintain.run_suggestions(v, "vault_manager", None)
        mc = [f for f in findings if f["check"] == "missed_connection"]
        assert not any(
            f["path"].startswith("work/creative/projects/tv-series/")
            for f in mc
        ), "project/section labels must not generate missed_connection noise"

    def test_specific_shared_tag_still_surfaces(self, tmp_path: Path):
        # A SPECIFIC (non-pervasive) tag shared across two different project
        # units is real resonance and must still raise missed_connection. The
        # rule requires >= 2 shared content tags, so give the pair two specific
        # tags (grief + memory) that are NOT pervasive in either unit.
        v = tmp_path
        _seed(v)
        _write(v / "work/creative/projects/alpha/a.md", """
---
type: note
kind: [concept]
status: draft
tags: [grief, memory]
created: 2026-08-02
---
Body A.
""")
        _write(v / "work/creative/projects/beta/b.md", """
---
type: note
kind: [concept]
status: draft
tags: [grief, memory]
created: 2026-08-02
---
Body B.
""")
        findings = maintain.run_suggestions(v, "vault_manager", None)
        mc = [f for f in findings if f["check"] == "missed_connection"]
        assert any(
            f["path"].endswith("alpha/a.md") and "grief" in f["suggestion"]
            for f in mc
        ), "specific shared tag across units should still surface"

    def test_pervasive_threshold_is_deterministic(self, tmp_path: Path):
        # The filter is fixed (ratio + minimum), not learned. In a 4-note
        # unit a tag on >= 2 (max(2, int(4*0.2)=0) = 2) notes is pervasive; a
        # tag on 1 note is not. Asserts the math, not vault behaviour.
        notes = [
            type("N", (), {"tags": ["x", "y"], "path": f"work/creative/projects/u/{i}.md"})()
            for i in range(4)
        ]
        pervasive = maintain._pervasive_tags(
            notes, maintain.MISSING_CONNECTION_PERVASIVE_RATIO,
            maintain.MISSING_CONNECTION_PERVASIVE_MIN)
        assert pervasive == {"x", "y"}

    def test_project_unit_groups_by_project_folder(self):
        assert maintain._project_unit(
            "work/creative/projects/tv-series/01-premise/x.md"
        ) == "work/creative/projects/tv-series"
        assert maintain._project_unit("system/handbook/foo.md") == "system"
        assert maintain._project_unit("README.md") == "README.md"
