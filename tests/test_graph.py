"""Graph link-resolution tests.

Covers path-aware, ambiguity-recording title resolution: same-folder
preference, ambiguous collisions surfaced in ``graph.ambiguous``, and that
single/missing titles behave exactly as before.
"""

from __future__ import annotations

from pathlib import Path

from vault.graph import build_graph
from vault.notes import iter_notes


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip(), encoding="utf-8")


_FM = """\
---
type: note
kind: [note]
status: draft
tags: [t]
created: 2026-08-02
---
"""


def _build(tmp_path: Path):
    notes = list(iter_notes(tmp_path))
    return build_graph(tmp_path, notes)


class TestPathAwareResolution:
    def test_same_folder_preferred_over_other_folders(self, tmp_path):
        # Two same-title notes in different folders.
        _write(tmp_path / "A/sametitle.md", _FM + "Body A.\n")
        _write(tmp_path / "B/sametitle.md", _FM + "Body B.\n")
        # A third note inside folder A links [[sametitle]].
        _write(tmp_path / "A/src.md", _FM + "See [[sametitle]].\n")

        g = _build(tmp_path)
        out = g.linked("A/src.md", direction="out")
        assert out, "expected an outgoing edge"
        assert out[0]["to"] == "A/sametitle.md"
        assert out[0]["to"] != "B/sametitle.md"
        # B remains reachable by its own path; only A/src's link prefers A.
        assert "A/sametitle.md" in g.nodes and "B/sametitle.md" in g.nodes

    def test_link_outside_both_folders_is_ambiguous(self, tmp_path):
        _write(tmp_path / "A/sametitle.md", _FM + "Body A.\n")
        _write(tmp_path / "B/sametitle.md", _FM + "Body B.\n")
        # A note at the vault root, in neither folder, links [[sametitle]].
        _write(tmp_path / "outside.md", _FM + "See [[sametitle]].\n")

        g = _build(tmp_path)
        out = g.linked("outside.md", direction="out")
        assert out, "expected an outgoing edge"
        target = out[0]["to"]
        assert target in ("A/sametitle.md", "B/sametitle.md")

        # Recorded as ambiguous: (source, label, sorted candidate paths).
        assert (("outside.md", "sametitle",
                 ["A/sametitle.md", "B/sametitle.md"]) in g.ambiguous)

    def test_single_title_resolves_normally_not_ambiguous(self, tmp_path):
        _write(tmp_path / "ONLY/alpha.md", _FM + "Body.\n")
        _write(tmp_path / "SRC/linker.md", _FM + "See [[alpha]].\n")

        g = _build(tmp_path)
        out = g.linked("SRC/linker.md", direction="out")
        assert out[0]["to"] == "ONLY/alpha.md"
        assert g.ambiguous == []

    def test_missing_title_is_dangling_not_ambiguous(self, tmp_path):
        _write(tmp_path / "SRC/linker.md", _FM + "See [[no-such-note]].\n")

        g = _build(tmp_path)
        out = g.linked("SRC/linker.md", direction="out")
        assert out[0]["to"] is None
        assert ("SRC/linker.md", "no-such-note") in g.dangling
        assert g.ambiguous == []

    def test_link_to_generated_or_real_file_is_not_dangling(self, tmp_path):
        # The graph's node set is notes only, so a link to a generated file
        # (INDEX) or any real on-disk .md looks unresolved. Such a link is NOT
        # a broken link and must not be reported as dangling — only a link to
        # a note that truly does not exist on disk should be.
        # A generated INDEX at the root:
        _write(tmp_path / "INDEX.md",
               "<!-- generated: do not edit -->\n# vault\n")
        # Another generated INDEX under system/ (path-qualified target):
        _write(tmp_path / "system/INDEX.md",
               "<!-- generated: do not edit -->\n# system\n")
        # Source note linking to both generated files:
        _write(tmp_path / "README.md",
               _FM + "Map: [[system/INDEX]] and [[INDEX]].\n")

        g = _build(tmp_path)
        dangling_labels = {l for _, l in g.dangling}
        assert "system/INDEX" not in dangling_labels
        assert "INDEX" not in dangling_labels

        # Control: a link to a note that does not exist on disk is still
        # dangling (behavior preserved).
        _write(tmp_path / "SRC/linker.md", _FM + "See [[ghost-note]].\n")
        g2 = _build(tmp_path)
        assert ("SRC/linker.md", "ghost-note") in g2.dangling


class TestMaintainDuplicateGuidance:
    def test_duplicate_finding_says_disambiguate_not_merge(self, tmp_path):
        from vault import maintain

        _write(tmp_path / ".vault/config.yaml",
               "fields:\n  title: { required: true }\n")
        # Same normalised title in two different folders.
        _write(tmp_path / "A/draft.md", _FM + "Draft A.\n")
        _write(tmp_path / "B/draft.md", _FM + "Draft B.\n")

        findings = maintain.run_suggestions(tmp_path, "vault_manager", None)
        dups = [f for f in findings if f["check"] == "duplicate"]
        assert dups, "expected a duplicate finding"
        # The disambiguation guidance lives in the suggestion field (detail is
        # the factual count).
        suggestion = dups[0]["suggestion"]
        assert "Disambiguate" in suggestion
        assert "wikilinks" in suggestion
        assert "Merge into one note" not in suggestion
