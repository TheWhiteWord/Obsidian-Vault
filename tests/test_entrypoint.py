"""Entrypoint smoke test — the one test the suite was missing.

Every other test imports ``vault.*`` directly. Nothing exercised
``__init__.py``, so a handler referenced in ``register()`` but never
defined (``_handle_delete``) took the whole plugin down at load time
with a NameError — and 108 tests stayed green.

This test calls ``register()`` with a collecting fake context and
asserts every declared tool actually registers. It is the guard for
the whole class of "handler wired but missing" bugs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import __init__ as plugin  # the plugin entrypoint (sys.path via conftest)

_PLUGIN_DIR = Path(__file__).resolve().parent.parent


class _FakeCtx:
    """Collects tool registrations without touching Hermes internals."""

    def __init__(self) -> None:
        self.tools: list[str] = []
        self.skills: list[tuple[str, str]] = []

    def register_skill(self, name: str, path: str) -> None:  # noqa: D102
        self.skills.append((name, str(path)))

    def register_tool(self, **kwargs) -> None:  # noqa: D102
        self.tools.append(kwargs["name"])


EXPECTED_TOOLS = {
    "obsidian_context",
    "obsidian_write",
    "obsidian_edit_metadata",
    "obsidian_delete",
    "obsidian_scaffold",
    "obsidian_edit_config",
    "obsidian_conventions",
    "obsidian_index",
    "obsidian_audit",
    "obsidian_reference",
    "obsidian_search",
    "obsidian_graph",
    "obsidian_issue",
    "obsidian_issue_resolve",
    "obsidian_issue_list",
    "obsidian_protocol_list",
    "obsidian_protocol",
    "obsidian_maintain",
}


def test_register_registers_every_tool() -> None:
    ctx = _FakeCtx()
    # Must not raise: a NameError here means zero tools load in Hermes.
    plugin.register(ctx)
    assert set(ctx.tools) == EXPECTED_TOOLS


def test_register_bundles_the_skill() -> None:
    ctx = _FakeCtx()
    plugin.register(ctx)
    # The bundled skill is registered under the plain name; its path must
    # exist on disk and contain a SKILL.md.
    assert any(name == "obsidian-vault" for name, _ in ctx.skills)
    for name, path in ctx.skills:
        if name == "obsidian-vault":
            skill_dir = Path(path)
            assert (skill_dir / "SKILL.md").is_file()


def test_register_has_no_duplicates() -> None:
    ctx = _FakeCtx()
    plugin.register(ctx)
    assert len(ctx.tools) == len(set(ctx.tools))


def test_plugin_yaml_provides_tools_match_register() -> None:
    """plugin.yaml's provides_tools must never drift from register().

    The manifest drives `hermes plugins install` tool-surface metadata;
    a missing tool there is a fresh-machine gap that the dev symlink
    hides (2026-08-05: was stale at 10 of 15 tools).
    """
    import yaml as _yaml

    manifest = _yaml.safe_load(
        (_PLUGIN_DIR / "plugin.yaml").read_text(encoding="utf-8"))
    declared = set(manifest["provides_tools"])
    assert declared == EXPECTED_TOOLS
    # Every declared tool is a real registered handler name (catches
    # typos that set-membership against EXPECTED_TOOLS cannot).
    ctx = _FakeCtx()
    plugin.register(ctx)
    assert declared <= set(ctx.tools)
