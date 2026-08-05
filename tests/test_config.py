"""Config inheritance — spec §3.2, §3.3, §3.6."""

from __future__ import annotations

import pytest

from vault.config import ConfigError, resolve_config
from vault.paths import VaultPathError, safe_join


class TestFalsificationTest:
    """Spec §3.6 — the case that would break the inheritance model.

    One byte-identical child config, two different parents. If this cannot be
    expressed cleanly, §3.3's merge semantics are wrong.
    """

    def test_allowed_only_replaces_inherited_vocabulary(self, vault):
        for tree in ("SYSTEM", "CREATIVE"):
            cfg = resolve_config(vault, vault / tree / "KNOWLEDGE")
            assert cfg.allowed_values("type") == ["knowledge"], tree
            assert cfg.fields["type"]["restricted"] is True, tree

    def test_allowed_unions_against_each_parent(self, vault):
        system = resolve_config(vault, vault / "SYSTEM/KNOWLEDGE")
        creative = resolve_config(vault, vault / "CREATIVE/KNOWLEDGE")

        # each inherits its OWN tree's vocabulary from the same child file
        assert "api-reference" in system.allowed_values("kind")
        assert "api-reference" not in creative.allowed_values("kind")
        assert "poem" in creative.allowed_values("kind")
        assert "poem" not in system.allowed_values("kind")

        # root universals reach both
        for cfg in (system, creative):
            assert "issue" in cfg.allowed_values("kind")

    def test_required_accumulates(self, vault):
        for tree in ("SYSTEM", "CREATIVE"):
            required = set(resolve_config(vault, vault / tree / "KNOWLEDGE").required_fields)
            assert {"source", "retrieved"} <= required, tree   # added by child
            assert {"type", "kind", "status", "tags", "created"} <= required, tree

    def test_defaults_override_key_by_key(self, vault):
        cfg = resolve_config(vault, vault / "CREATIVE/KNOWLEDGE")
        assert cfg.defaults["status"] == "reference"   # child overrode draft
        assert cfg.defaults["created"] == "@today"     # root default survived


class TestInheritanceChain:
    def test_folder_without_config_inherits_ancestors(self, vault):
        cfg = resolve_config(vault, vault / "CREATIVE/PHILOSOPHY")
        assert len(cfg.sources) == 2                    # root + CREATIVE
        assert "concept" in cfg.allowed_values("kind")  # from CREATIVE
        assert "issue" in cfg.allowed_values("kind")    # from root

    def test_root_alone_when_no_tree_config(self, vault):
        cfg = resolve_config(vault, vault)
        assert len(cfg.sources) == 1
        assert cfg.allowed_values("type") == ["index", "note"]

    def test_chain_is_root_first(self, vault):
        cfg = resolve_config(vault, vault / "CREATIVE/KNOWLEDGE")
        names = [p.parent.parent.name or "root" for p in cfg.sources]
        assert names[0] == vault.name          # root config first
        assert names[-1] == "KNOWLEDGE"        # leaf last (wins)


class TestUniformityContract:
    """Spec §3.2 — children constrain values, never redefine fields."""

    def test_child_cannot_change_field_format(self, vault, tmp_path):
        bad = vault / "CREATIVE/BAD/.vault/config.yaml"
        bad.parent.mkdir(parents=True)
        bad.write_text("fields:\n  created: { format: datetime }\n")

        with pytest.raises(ConfigError, match="may not redefine"):
            resolve_config(vault, vault / "CREATIVE/BAD")

    def test_child_cannot_drop_inherited_required(self, vault):
        bad = vault / "CREATIVE/LAX/.vault/config.yaml"
        bad.parent.mkdir(parents=True)
        bad.write_text("fields:\n  tags: { required: false }\n")

        with pytest.raises(ConfigError, match="cannot drop"):
            resolve_config(vault, vault / "CREATIVE/LAX")

    def test_malformed_yaml_names_the_file(self, vault):
        bad = vault / "CREATIVE/BROKEN/.vault/config.yaml"
        bad.parent.mkdir(parents=True)
        bad.write_text("fields: [this is not a mapping\n")

        with pytest.raises(ConfigError, match="BROKEN"):
            resolve_config(vault, vault / "CREATIVE/BROKEN")


class TestPathSafety:
    def test_traversal_is_refused(self, vault):
        with pytest.raises(VaultPathError, match="escapes"):
            safe_join(vault, "../../etc")

    def test_absolute_path_is_refused(self, vault):
        with pytest.raises(VaultPathError, match="escapes"):
            safe_join(vault, "/etc/passwd")

    def test_root_forms_resolve_to_root(self, vault):
        for form in ("", ".", "/"):
            assert safe_join(vault, form) == vault

    def test_outside_vault_is_refused(self, vault, tmp_path):
        with pytest.raises(VaultPathError, match="not inside vault"):
            resolve_config(vault, tmp_path.parent / "elsewhere")
