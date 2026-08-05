"""Graph + query (P3) — deterministic navigation."""

from __future__ import annotations

import pytest

from vault.grants import load_roles
from vault.graph import Graph, build_graph
from vault.query import search
from vault.notes import iter_notes

FM = {"type": "work", "kind": ["essay"], "status": "draft",
      "tags": ["nietzsche"], "created": "2026-08-02"}


@pytest.fixture
def vault_with_notes(vault_with_roles):
    # a small linked web across two trees (the TWW cross-domain case)
    from vault.write import write_note

    write_note(vault_with_roles, "tww", load_roles(vault_with_roles),
               "CREATIVE/PHILOSOPHY/a.md",
               {**FM, "kind": ["essay"]}, "Links to [[b]] and [[Missing Note]].")
    write_note(vault_with_roles, "tww", load_roles(vault_with_roles),
               "CREATIVE/PHILOSOPHY/b.md",
               {**FM, "kind": ["concept"]}, "Back to [[a]].")
    write_note(vault_with_roles, "system", load_roles(vault_with_roles),
               "SYSTEM/KNOWLEDGE/k.md",
               {**FM, "kind": ["reference"], "type": "knowledge", "source": "x",
                "retrieved": "2026-08-02"},
               "References [[a]] across the tree.")
    # Non-word-boundary terms (C#, C++) — the old \b regex never matched these.
    write_note(vault_with_roles, "tww", load_roles(vault_with_roles),
               "CREATIVE/PHILOSOPHY/csharp.md",
               {**FM, "kind": ["note"], "tags": ["programming"]},
               "Learning C# and C++ today for the plugin.")
    # Long body with the distinctive term buried past the opening — snippet probe.
    long_body = ("The essay opens with a preamble about retrieval. " * 10 +
                 "The hidden token is xyzzy, buried past the opening. " +
                 "It concludes with reflections on indexing. " * 5)
    write_note(vault_with_roles, "tww", load_roles(vault_with_roles),
               "CREATIVE/PHILOSOPHY/long-note.md",
               {**FM, "kind": ["essay"]}, long_body)
    # Relevance probe: term in title AND body outranks term in title only.
    write_note(vault_with_roles, "tww", load_roles(vault_with_roles),
               "CREATIVE/PHILOSOPHY/time-notes.md",
               {**FM, "kind": ["note"]},
               "Time is the topic of this essay about time and time again.")
    return vault_with_roles


class TestSearch:
    def test_empty_query_returns_all_readable(self, vault_with_notes, roles):
        out = search(vault_with_notes, "", agent="tww", roles=roles)
        # tww reads CREATIVE + */KNOWLEDGE, not SYSTEM/HANDBOOK or STATE
        paths = {r["path"] for r in out["results"]}
        assert any(p.startswith("CREATIVE/") for p in paths)
        assert any(p.startswith("SYSTEM/KNOWLEDGE/") for p in paths)
        assert not any("SYSTEM/HANDBOOK" in p for p in paths)

    def test_term_match_is_whole_word(self, vault_with_notes, roles):
        out = search(vault_with_notes, "essay", agent="tww", roles=roles)
        assert out["count"] >= 1

    def test_grant_intersection_silently_filters(self, vault_with_notes, roles):
        # searching unfiltered sees SYSTEM/HANDBOOK; tww does not
        unfiltered = search(vault_with_notes, "", agent="system", roles=roles)
        as_tww = search(vault_with_notes, "", agent="tww", roles=roles)
        assert unfiltered["count"] >= as_tww["count"]
        assert not any("SYSTEM/HANDBOOK" in r["path"] for r in as_tww["results"])

    def test_scope_glob_limits_the_scan(self, vault_with_notes, roles):
        # regression: scope used to be treated as a literal path, returning
        # zero results — the empty set satisfied the old vacuous assertion.
        out = search(vault_with_notes, "", scope="CREATIVE/**", agent="tww", roles=roles)
        assert out["count"] > 0
        assert all(p["path"].startswith("CREATIVE/") for p in out["results"])

    def test_scope_glob_crosses_trees(self, vault_with_notes, roles):
        # */KNOWLEDGE/** matches the KNOWLEDGE folder under any tree
        out = search(vault_with_notes, "", scope="*/KNOWLEDGE/**",
                     agent="system", roles=roles)
        paths = {r["path"] for r in out["results"]}
        assert any(p.startswith("CREATIVE/KNOWLEDGE/") for p in paths)
        assert any(p.startswith("SYSTEM/KNOWLEDGE/") for p in paths)

    def test_scope_glob_does_not_widen_grants(self, vault_with_notes, roles):
        # scope='**' plus tww's read grants still hides SYSTEM/HANDBOOK
        out = search(vault_with_notes, "", scope="**", agent="tww", roles=roles)
        assert not any("SYSTEM/HANDBOOK" in r["path"] for r in out["results"])

    def test_non_word_terms_match(self, vault_with_notes, roles):
        # \b never matched C#/C++; the lookaround boundary does
        out = search(vault_with_notes, "C#", agent="tww", roles=roles)
        assert any(r["path"].endswith("csharp.md") for r in out["results"])
        out2 = search(vault_with_notes, "C++", agent="tww", roles=roles)
        assert any(r["path"].endswith("csharp.md") for r in out2["results"])

    def test_snippet_windows_around_match(self, vault_with_notes, roles):
        out = search(vault_with_notes, "xyzzy", agent="tww", roles=roles)
        long = [r for r in out["results"] if r["path"].endswith("long-note.md")]
        assert long
        assert "xyzzy" in long[0]["snippet"]
        assert long[0]["snippet"].startswith("…")

    def test_relevance_ranks_title_hits_first(self, vault_with_notes, roles):
        # 'time' is in time-notes' title AND body → must rank above notes
        # that only carry it in a title or a link.
        out = search(vault_with_notes, "time", agent="tww", roles=roles)
        assert out["results"][0]["path"].endswith("time-notes.md")

    def test_fields_restrict_match_surface(self, vault_with_notes, roles):
        # 'nietzsche' is a tag, not in body — tag-only search finds it
        tagged = search(vault_with_notes, "nietzsche", fields=["tags"],
                        agent="tww", roles=roles)
        assert tagged["count"] >= 1
        # body-only search for the same tag term finds nothing
        body_only = search(vault_with_notes, "nietzsche", fields=["body"],
                           agent="tww", roles=roles)
        assert body_only["count"] == 0

    def test_group_by_folder(self, vault_with_notes, roles):
        out = search(vault_with_notes, "", group_by="folder", agent="tww", roles=roles)
        assert "CREATIVE/PHILOSOPHY" in out["buckets"]
        assert "SYSTEM/KNOWLEDGE" in out["buckets"]

    def test_group_by_kind(self, vault_with_notes, roles):
        out = search(vault_with_notes, "", group_by="kind", agent="tww", roles=roles)
        assert "essay" in out["buckets"] and "concept" in out["buckets"]

    def test_cross_domain_link_is_findable(self, vault_with_notes, roles):
        # the SYSTEM/KNOWLEDGE note links [[a]]; tww can read it and a
        out = search(vault_with_notes, "across the tree", agent="tww", roles=roles)
        assert any(p["path"].startswith("SYSTEM/KNOWLEDGE/") for p in out["results"])


class TestScopeNegation:
    """P3.8 — `!pattern` exclusions in the search scope glob language (D9)."""

    def test_scope_list_excludes_a_subtree(self, vault_with_notes, roles):
        # the shared-folder case: search the tree minus the shared knowledge folder
        out = search(vault_with_notes, "",
                     scope=["CREATIVE/**", "!CREATIVE/KNOWLEDGE/**"],
                     agent="system", roles=roles)
        paths = [r["path"] for r in out["results"]]
        assert paths
        assert all(p.startswith("CREATIVE/") for p in paths)
        assert not any(p.startswith("CREATIVE/KNOWLEDGE/") for p in paths)

    def test_negation_wins_over_inclusion(self, vault_with_notes, roles):
        # '!**' excludes everything even though '**' includes it — a scope
        # cannot be widened by an inclusion that negation cancels
        out = search(vault_with_notes, "", scope=["**", "!**"],
                     agent="system", roles=roles)
        assert out["count"] == 0

    def test_only_exclusions_match_nothing(self, vault_with_notes, roles):
        # an exclusion-only scope has no positive glob — absence of an
        # inclusion never widens a query
        out = search(vault_with_notes, "", scope=["!**/design.md"],
                     agent="system", roles=roles)
        assert out["count"] == 0

    def test_cross_tree_exclusion(self, vault_with_notes, roles):
        # '!*/KNOWLEDGE/**' removes the shared folder under every tree
        out = search(vault_with_notes, "", scope=["**", "!*/KNOWLEDGE/**"],
                     agent="system", roles=roles)
        assert not any("/KNOWLEDGE/" in r["path"] for r in out["results"])

    def test_scope_negation_never_widens_grants(self, vault_with_notes, roles):
        # tww cannot read SYSTEM/HANDBOOK; even a scope whose positives
        # cover the vault cannot reveal it — grants filter after scope
        out = search(vault_with_notes, "", scope=["**", "!**/design.md"],
                     agent="tww", roles=roles)
        assert not any("SYSTEM/HANDBOOK" in r["path"] for r in out["results"])


class TestGraph:
    def _graph(self, vault_with_notes):
        return build_graph(vault_with_notes)

    def test_outgoing_and_incoming(self, vault_with_notes):
        g = self._graph(vault_with_notes)
        a = "CREATIVE/PHILOSOPHY/a.md"
        b = "CREATIVE/PHILOSOPHY/b.md"
        assert b in {e["to"] for e in g.linked(a, "out")}
        assert a in {e["to"] for e in g.linked(b, "in")}

    def test_dangling_link_recorded(self, vault_with_notes):
        g = self._graph(vault_with_notes)
        labels = {label for _, label in g.dangling}
        assert "Missing Note" in labels

    def test_traverse_two_hops(self, vault_with_notes):
        g = self._graph(vault_with_notes)
        a = "CREATIVE/PHILOSOPHY/a.md"
        # a -> b -> (nothing further in PHILOSOPHY); but SYSTEM/KNOWLEDGE -> a
        # so from a, 2 hops reaches the SYSTEM note via b? No: b->a only.
        # Reachability: a's 1-hop = {b}; 2-hop = {a} (back) — excluded.
        one = g.traverse(a, hops=1)
        assert "CREATIVE/PHILOSOPHY/b.md" in one
        # k links to a, so from k 1 hop = {a}, 2 hops = {b}
        k = "SYSTEM/KNOWLEDGE/k.md"
        two = g.traverse(k, hops=2)
        assert "CREATIVE/PHILOSOPHY/b.md" in two

    def test_neighbors_are_undirected(self, vault_with_notes):
        g = self._graph(vault_with_notes)
        a = "CREATIVE/PHILOSOPHY/a.md"
        nbrs = g.neighbors(a)
        assert "CREATIVE/PHILOSOPHY/b.md" in nbrs
        assert "SYSTEM/KNOWLEDGE/k.md" in nbrs   # k links to a
