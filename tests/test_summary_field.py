"""summary_field: config-named, engine-agnostic note summary (P2 addendum)."""

from __future__ import annotations

from vault.config import resolve_config
from vault.context import build_context
from vault.generate import build_index
from vault.reference import describe

import pytest


@pytest.fixture
def vault_with_summary(vault):
    cfg = vault / ".vault/config.yaml"
    cfg.write_text(cfg.read_text() + "\nsummary_field: blurb\n")
    (vault / "Projects/Alpha").mkdir(parents=True)
    (vault / "Projects/Alpha/a.md").write_text(
        "---\ntitle: a\ntype: note\nblurb: what this note is about\n---\nbody\n"
    )
    return vault


class TestSummaryIsConfigNamed:
    def test_engine_does_not_hardcode_a_field_name(self, vault_with_summary):
        cfg = resolve_config(vault_with_summary, vault_with_summary / "Projects/Alpha")
        assert cfg.summary_field == "blurb"

    def test_index_renders_the_configured_field(self, vault_with_summary):
        text = build_index(vault_with_summary, "Projects/Alpha")
        assert "[[a]]" in text
        assert "what this note is about" in text

    def test_absent_summary_field_produces_no_summary(self, vault):
        # default fixture has no summary_field — INDEX must not append a
        # summary to note entries (the em-dash in the header prose is fine)
        (vault / "X").mkdir()
        (vault / "X/n.md").write_text("---\ntitle: n\n---\nbody\n")
        text = build_index(vault, "X")
        assert "[[n]]" in text
        entry_lines = [l for l in text.splitlines() if l.strip().startswith("- [[")]
        assert entry_lines and "—" not in entry_lines[0]

    def test_template_prompts_the_summary_field(self, vault_with_summary):
        ctx = build_context(vault_with_summary, "Projects/Alpha")
        assert 'blurb: "one-line summary of the note"' in ctx["template"]


class TestDiscovery:
    def test_reference_lists_summary_field_as_an_option(self):
        opts = {o["key"] for o in describe()["config_options"]}
        assert "summary_field" in opts

    def test_reference_explains_grant_kinds(self):
        kinds = {g["key"] for g in describe()["grant_kinds"]}
        assert kinds == {"read", "write", "append", "meta", "config"}

    def test_context_does_not_ship_the_reference(self, vault_with_summary):
        # D1 cleanup (2026-08-05): the option list is a discovery call
        # (`obsidian_reference`), not folder context — context stays scoped
        # to the folder, the reference stays one call away.
        ctx = build_context(vault_with_summary, "Projects/Alpha")
        assert "engine_options" not in ctx
        opts = {o["key"] for o in describe()["config_options"]}
        assert "summary_field" in opts  # still discoverable via the tool
