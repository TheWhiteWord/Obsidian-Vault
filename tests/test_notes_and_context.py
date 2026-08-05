"""Note parsing, vocabulary derivation, and the context call."""

from __future__ import annotations

from vault.context import build_context
from vault.notes import derive_tags, derive_vocabulary, iter_notes, parse_note


class TestNoteParsing:
    def test_frontmatter_and_body_split(self, vault):
        note = parse_note(vault / "CREATIVE/PHILOSOPHY/recurrence.md", vault)
        assert note.frontmatter["type"] == "work"
        assert note.tags == ["nietzsche", "time"]
        assert note.error is None
        assert "---" not in note.content

    def test_wikilinks_exclude_code_spans(self, vault):
        note = parse_note(vault / "CREATIVE/PHILOSOPHY/recurrence.md", vault)
        assert note.links == ["kant-on-time"]        # `[[not-a-link]]` stripped

    def test_paths_are_vault_relative_posix(self, vault):
        note = parse_note(vault / "CREATIVE/PHILOSOPHY/recurrence.md", vault)
        assert note.path == "CREATIVE/PHILOSOPHY/recurrence.md"
        assert note.folder == "CREATIVE/PHILOSOPHY"
        assert note.title == "recurrence"

    def test_malformed_frontmatter_does_not_raise(self, vault):
        bad = vault / "CREATIVE/PHILOSOPHY/broken.md"
        bad.write_text("---\ntype: [unclosed\n---\nbody\n")
        note = parse_note(bad, vault)
        assert note.error is not None
        assert note.frontmatter == {}

    def test_scan_skips_config_and_system_dirs(self, vault):
        paths = [n.path for n in iter_notes(vault)]
        assert not any(".vault" in p for p in paths)
        assert all(p.endswith(".md") for p in paths)


class TestVocabularyDerivation:
    """Spec §3.7 — declared / observed / unused."""

    def test_unregistered_value_is_observed(self, vault):
        notes = list(iter_notes(vault, scope=vault / "CREATIVE/PHILOSOPHY"))
        vocab = derive_vocabulary(notes, "kind", ["concept", "essay", "poem"])
        observed = {e["name"] for e in vocab["observed"]}
        assert observed == {"aphorism"}

    def test_declared_and_in_use_carries_a_count(self, vault):
        notes = list(iter_notes(vault, scope=vault / "CREATIVE/PHILOSOPHY"))
        vocab = derive_vocabulary(notes, "kind", ["concept", "essay", "poem"])
        used = {e["name"]: e["count"] for e in vocab["declared"] if not e.get("unused")}
        assert used == {"concept": 1, "essay": 1}

    def test_declared_but_unused_is_flagged(self, vault):
        notes = list(iter_notes(vault, scope=vault / "CREATIVE/PHILOSOPHY"))
        vocab = derive_vocabulary(notes, "kind", ["concept", "essay", "poem"])
        unused = {e["name"] for e in vocab["declared"] if e.get("unused")}
        assert "poem" in unused          # retirement candidate for vault_manager

    def test_tags_are_derived_not_declared(self, vault):
        notes = list(iter_notes(vault, scope=vault / "CREATIVE/PHILOSOPHY"))
        tags = {t["name"]: t["count"] for t in derive_tags(notes)}
        assert tags["nietzsche"] == 2    # counted across both notes
        assert derive_tags(notes)[0]["name"] == "nietzsche"   # sorted by count


class TestContextCall:
    """Spec §5."""

    def test_returns_merged_schema_for_the_folder(self, vault):
        ctx = build_context(vault, "CREATIVE/KNOWLEDGE")
        fields = ctx["schema"]["fields"]
        assert fields["type"]["restricted"] is True
        assert fields["source"]["required"] is True

    def test_vocabulary_is_scoped_to_the_domain(self, vault):
        creative = build_context(vault, "CREATIVE/PHILOSOPHY")
        kinds = str(creative["schema"]["fields"]["kind"])
        assert "concept" in kinds
        assert "api-reference" not in kinds     # SYSTEM's vocabulary stays out

    def test_template_uses_placeholders_not_real_data(self, vault):
        ctx = build_context(vault, "CREATIVE/PHILOSOPHY")
        template = ctx["template"]
        assert "<type>" in template
        assert "nietzsche" not in template      # never copy a sibling's tags
        assert "status: draft" in template      # defaults ARE filled

    def test_missing_folder_returns_error_not_exception(self, vault):
        ctx = build_context(vault, "NOPE/MISSING")
        assert "error" in ctx
        assert "scaffold" in ctx["hint"]

    def test_malformed_notes_are_surfaced(self, vault):
        (vault / "CREATIVE/PHILOSOPHY/broken.md").write_text("---\na: [b\n---\n")
        ctx = build_context(vault, "CREATIVE/PHILOSOPHY")
        assert any("broken" in p for p in ctx["malformed_notes"])

    def test_payload_stays_small(self, vault):
        import json
        size = len(json.dumps(build_context(vault, "CREATIVE/PHILOSOPHY")))
        # The ceiling guards the VARIABLE part of the payload (schema, tags,
        # siblings) against accidental bloat (e.g. verbose vocabulary objects).
        # The `engine_options` reference block is a deliberate constant
        # (~2000 chars, one entry per real engine option — summary_field,
        # vocabulary, paths.state, value_overrides, conventions.skill) and is
        # documented, not accidental. 3400 = ~2000 reference + ~1400 variable.
        assert size < 3400, f"context payload grew to {size} chars"
