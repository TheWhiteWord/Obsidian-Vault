"""P7 — in-tree per-scope conventions: discovery, the
`obsidian_conventions` tool surface, and the write gate."""

from __future__ import annotations

import pytest

from vault import audit
from vault.config import resolve_config
from vault.constants import CONVENTIONS_FILENAME
from vault.context import build_context
from vault.conventions import (
    conventions_chain,
    fingerprint,
    nearest_conventions,
    resolved_conventions,
    write_conventions,
)
from vault.grants import Grants, PermissionDenied, RoleRegistry, load_roles
from vault.notes import iter_notes
from vault.paths import VaultPathError


@pytest.fixture
def roles(vault_with_roles):
    return load_roles(vault_with_roles)


class TestDiscovery:
    def test_no_files_no_chain(self, vault_with_roles):
        assert conventions_chain(
            vault_with_roles, vault_with_roles / "CREATIVE") == []

    def test_nearest_wins_chain_is_root_first(self, vault_with_roles):
        root = vault_with_roles
        (root / ".vault/conventions.md").write_text("root rules\n")
        (root / "CREATIVE/.vault/conventions.md").write_text("creative rules\n")

        chain = conventions_chain(root, root / "CREATIVE/PHILOSOPHY")
        assert [p.relative_to(root).as_posix() for p in chain] == [
            ".vault/conventions.md", "CREATIVE/.vault/conventions.md"]
        assert nearest_conventions(
            root, root / "CREATIVE/PHILOSOPHY") == chain[-1]

    def test_absent_rules_fall_back_up_the_chain(self, vault_with_roles):
        root = vault_with_roles
        (root / "CREATIVE/.vault/conventions.md").write_text("creative rules\n")
        # PHILOSOPHY has no file of its own — the domain's applies.
        assert nearest_conventions(root, root / "CREATIVE/PHILOSOPHY") == (
            root / "CREATIVE/.vault/conventions.md")

    def test_resolved_chain_includes_content(self, vault_with_roles):
        root = vault_with_roles
        (root / ".vault/conventions.md").write_text("root rules\n")
        (root / "CREATIVE/.vault/conventions.md").write_text("creative rules\n")

        out = resolved_conventions(root, root / "CREATIVE/PHILOSOPHY")
        assert out["nearest"] == "CREATIVE/.vault/conventions.md"
        assert out["chain"] == ["root rules\n", "creative rules\n"]

    def test_machinery_invisible_to_note_walks(self, vault_with_roles):
        root = vault_with_roles
        (root / "CREATIVE/.vault/conventions.md").write_text("rules\n")
        paths = [n.path for n in iter_notes(root)]
        assert not any(p.endswith(CONVENTIONS_FILENAME) for p in paths)

    def test_fingerprint_is_stable_and_sensitive(self):
        assert fingerprint("a") == fingerprint("a")
        assert fingerprint("a") != fingerprint("b")


class TestWrite:
    def test_owner_writes_own_scope(self, vault_with_roles, roles):
        out = write_conventions(vault_with_roles, "tww", roles,
                                "CREATIVE/.vault/conventions.md", "rules\n")
        assert out["ok"] is True
        text = (vault_with_roles
                / "CREATIVE/.vault/conventions.md").read_text()
        assert text == "rules\n"

    def test_non_owner_denied(self, vault_with_roles, roles):
        with pytest.raises(PermissionDenied, match="may not edit"):
            write_conventions(vault_with_roles, "tww", roles,
                              "SYSTEM/.vault/conventions.md", "rules\n")

    def test_manager_never_writes_conventions(self, vault_with_roles, roles):
        # meta/config/read only — no write grant, so not even the root file.
        with pytest.raises(PermissionDenied, match="may not edit"):
            write_conventions(vault_with_roles, "vault_manager", roles,
                              ".vault/conventions.md", "rules\n")

    def test_wrong_filename_refused(self, vault_with_roles, roles):
        with pytest.raises(VaultPathError):
            write_conventions(vault_with_roles, "tww", roles,
                              "CREATIVE/.vault/other.md", "rules\n")

    def test_write_is_audited_and_no_index_spawned(self, vault_with_roles, roles):
        write_conventions(vault_with_roles, "tww", roles,
                          "CREATIVE/.vault/conventions.md", "rules\n")
        entries = audit.read_entries(vault_with_roles)
        assert any(e["action"] == "edit_conventions" for e in entries)
        # machinery stays machinery — no content-derived INDEX inside .vault/
        assert not (vault_with_roles / "CREATIVE/.vault/INDEX.md").exists()
        assert not (vault_with_roles / "CREATIVE/INDEX.md").exists()

    def test_subdomain_owner_only_via_shadowing(self, vault_with_roles):
        """The researcher owns knowledge/ — the writer is shadowed there."""
        root = vault_with_roles
        nested = RoleRegistry(agents={
            "writer": Grants("writer", {
                "write": ["CREATIVE/**"], "config": ["CREATIVE/**"]}),
            "researcher": Grants("researcher", {
                "write": ["CREATIVE/KNOWLEDGE/**"],
                "config": ["CREATIVE/KNOWLEDGE/**"]}),
        })
        (root / "CREATIVE/KNOWLEDGE/.vault").mkdir(parents=True, exist_ok=True)
        with pytest.raises(PermissionDenied, match="scope is owned by researcher"):
            write_conventions(root, "writer", nested,
                              "CREATIVE/KNOWLEDGE/.vault/conventions.md",
                              "rules\n")
        out = write_conventions(root, "researcher", nested,
                                "CREATIVE/KNOWLEDGE/.vault/conventions.md",
                                "researcher rules\n")
        assert out["ok"] is True


class TestContextPointer:
    def test_pointer_present_when_file_exists(self, vault_with_roles):
        root = vault_with_roles
        (root / "CREATIVE/.vault/conventions.md").write_text("rules\n")
        ctx = build_context(root, "CREATIVE", agent="tww",
                            roles=load_roles(root))
        assert ctx["conventions"] == "CREATIVE/.vault/conventions.md"

    def test_pointer_omitted_when_absent(self, vault_with_roles):
        ctx = build_context(vault_with_roles, "CREATIVE", agent="tww",
                            roles=load_roles(vault_with_roles))
        assert "conventions" not in ctx


class TestToolSurface:
    def test_register_wires_the_tool(self):
        import __init__ as plugin

        class Ctx:
            def __init__(self):
                self.tools = []
                self.skills = []

            def register_tool(self, **kw):
                self.tools.append(kw["name"])

            def register_skill(self, name, path):
                self.skills.append(name)

        ctx = Ctx()
        plugin.register(ctx)
        assert "obsidian_conventions" in ctx.tools

    def test_handler_read_chain(self, vault_with_roles):
        import json
        import __init__ as plugin
        (vault_with_roles / "CREATIVE/.vault/conventions.md").write_text(
            "creative rules\n")
        out = json.loads(plugin._handle_conventions({
            "folder": "CREATIVE", "vault": str(vault_with_roles),
            "agent": "tww"}))
        assert out["nearest"] == "CREATIVE/.vault/conventions.md"

    def test_handler_edit_gate(self, vault_with_roles):
        import json
        import __init__ as plugin
        out = json.loads(plugin._handle_conventions({
            "path": "SYSTEM/.vault/conventions.md", "content": "x",
            "vault": str(vault_with_roles), "agent": "tww"}))
        assert out["ok"] is False
        assert out["error"] == "permission_denied"

    def test_handler_edit_requires_both_fields(self, vault_with_roles):
        import json
        import __init__ as plugin
        out = json.loads(plugin._handle_conventions({
            "path": "CREATIVE/.vault/conventions.md",
            "vault": str(vault_with_roles), "agent": "tww"}))
        assert out["ok"] is False
        assert out["error"] == "bad_request"
