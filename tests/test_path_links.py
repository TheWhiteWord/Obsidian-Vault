"""Path-qualified wikilink resolution in the graph + census.

Regression cover for the dangling-link false positives: the engine must
resolve Obsidian-style path links (../, sibling/sub, vault-root-relative)
rather than flagging them as dangling, and must not flag links to generated
files (e.g. INDEX) that exist on disk.
"""
import pytest
from pathlib import Path

from vault import graph as graph_mod, maintain


@pytest.fixture
def vault_with_paths(tmp_path: Path) -> Path:
    """A vault using path-qualified cross-folder links."""
    v = tmp_path
    (v / ".vault").mkdir()
    (v / ".vault/config.yaml").write_text(
        "fields:\n  type: {required: true, allowed: [note, work]}\n"
        "  kind: {required: true, multi: true, allowed: [concept]}\n"
        "  status: {required: true, allowed: [draft]}\n"
        "  tags: {required: true, multi: true}\n  created: {required: true, format: date}\n",
        encoding="utf-8",
    )

    def note(rel: str, body: str, extra_front=""):
        p = v / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            f"---\ntype: note\nkind: [concept]\nstatus: draft\ntags: [x]\n"
            f"created: 2026-08-02\n{extra_front}---\n{body}\n",
            encoding="utf-8",
        )

    # a/start.md links up-and-over to b/target.md via ../
    note("a/start.md", "See [[../b/target]] and [[b/other]].")
    note("b/target.md", "Target note.")
    note("b/other.md", "Other note in b.")
    # root README links to a generated-style INDEX that exists on disk
    note("README.md", "Index: [[system/INDEX]].")
    # system/INDEX.md exists on disk (simulating a generated file)
    note("system/INDEX.md", "Generated index.", extra_front="generated: true\n")
    return v


def test_path_qualified_links_resolve_not_dangling(vault_with_paths: Path):
    v = vault_with_paths
    notes = list(graph_mod.iter_notes(v))
    g = graph_mod.build_graph(v, notes)
    dangling_labels = {l for _, l in g.dangling}
    assert ".." not in str(dangling_labels) or "../b/target" not in dangling_labels
    # the ../b/target link must resolve to a real edge
    targets = [t for (t, l) in g.outgoing.get("a/start.md", []) if l == "../b/target"]
    assert targets and targets[0] == "b/target.md"


def test_sibling_subfolder_link_resolves(vault_with_paths: Path):
    v = vault_with_paths
    notes = list(graph_mod.iter_notes(v))
    g = graph_mod.build_graph(v, notes)
    targets = [t for (t, l) in g.outgoing.get("a/start.md", []) if l == "b/other"]
    assert targets and targets[0] == "b/other.md"


def test_link_to_generated_file_is_not_dangling(vault_with_paths: Path):
    v = vault_with_paths
    census = maintain.run_census(v)
    dangling = [f for f in census if f["check"] == "dangling"]
    assert all("system/INDEX" not in f.get("detail", "") for f in dangling)
    # README -> system/INDEX must not produce a dangling finding
    assert not any(f["path"] == "README.md" for f in dangling)


def test_census_reports_no_false_dangling(vault_with_paths: Path):
    v = vault_with_paths
    census = maintain.run_census(v)
    dangling = [f for f in census if f["check"] == "dangling"]
    assert dangling == [], f"unexpected dangling: {dangling}"
