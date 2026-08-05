"""Growth-protocol tests (P5c) — the setup.py growth subcommands.

Pure functions against a scratch HERMES_HOME / vault, mirroring
test_setup.py. Grant correctness is asserted through the engine's real
``load_roles`` (the subcommands must produce grants the engine enforces).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import setup as installer

from vault.grants import load_roles  # noqa: E402  (plugin root on sys.path via conftest)


# --- helpers ---------------------------------------------------------------

def _scratch(tmp_path: Path, with_vault: bool = True) -> tuple[Path, Path]:
    """A scratch HERMES_HOME and (optionally) a scaffolded blank vault."""
    hermes = tmp_path / "hermes"
    vault = tmp_path / "vault"
    if with_vault:
        installer.scaffold_vault(vault, "blank")
    return hermes, vault


def _profile_dir(hermes: Path, name: str) -> Path:
    """Pre-create a profile dir so add_contributor skips the hermes CLI."""
    home = installer.profile_home(hermes, name)
    (home / "skills").mkdir(parents=True, exist_ok=True)
    (home / "SOUL.md").write_text("# SOUL\n", encoding="utf-8")
    return home


# --- vault_conventions_name / ensure_conventions_file ----------------------

def test_vault_conventions_name_uses_vault_dir_name():
    assert installer.vault_conventions_name(Path("/x/TWW")) == "TWW-conventions.md"


def test_ensure_conventions_file_creates_from_template_and_survives(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "creative")
    first = installer.ensure_conventions_file(profile / "skills", vault)
    assert first.name == f"{vault.name}-conventions.md"
    text = first.read_text(encoding="utf-8")
    assert vault.name in text          # <Vault name> substituted
    assert "## Rules" in text          # template body intact

    # Growth through interaction must survive a re-run.
    first.write_text("# my grown conventions\n", encoding="utf-8")
    again = installer.ensure_conventions_file(profile / "skills", vault)
    assert again == first
    assert again.read_text(encoding="utf-8") == "# my grown conventions\n"


def test_ensure_conventions_file_dry_run_creates_nothing(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "creative")
    installer.ensure_conventions_file(profile / "skills", vault, dry_run=True)
    assert not (profile / "skills" / "obsidian-vault" / "conventions").exists()


# --- append_manifest_entry -------------------------------------------------

def test_append_manifest_entry_before_marker_and_idempotent(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "creative")
    installer.ensure_soul_sections(profile / "SOUL.md", "contributor")
    soul = (profile / "SOUL.md").read_text(encoding="utf-8")
    assert "<!-- add:" in soul

    line = (f"- `conventions/{vault.name}-conventions.md` — "
            f"recipes domain conventions (work/recipes/**)")
    assert installer.append_manifest_entry(profile / "SOUL.md", line) is True
    text = (profile / "SOUL.md").read_text(encoding="utf-8")
    assert line in text
    assert text.index(line) < text.index("<!-- add:")   # above the marker
    # The marker stays as the directed placeholder.
    assert "<!-- add:" in text

    assert installer.append_manifest_entry(profile / "SOUL.md", line) is False
    assert (profile / "SOUL.md").read_text(encoding="utf-8") == text


def test_append_manifest_entry_refuses_manager_soul(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "vault-manager")
    installer.ensure_soul_sections(profile / "SOUL.md", "manager")
    line = (f"- `conventions/{vault.name}-conventions.md` — "
            f"recipes domain conventions (work/recipes/**)")
    with pytest.raises(ValueError, match="no convention-manifest add-marker"):
        installer.append_manifest_entry(profile / "SOUL.md", line)


def test_append_manifest_entry_requires_soul_file(tmp_path):
    hermes, _vault = _scratch(tmp_path, with_vault=False)
    with pytest.raises(FileNotFoundError, match="SOUL not found"):
        installer.append_manifest_entry(hermes / "nope" / "SOUL.md", "- x")


# --- _append_agent_grant ---------------------------------------------------

def test_append_agent_grant_adds_block_and_parses(tmp_path):
    hermes, vault = _scratch(tmp_path)
    roles = vault / ".vault" / "roles.yaml"
    assert installer._append_agent_grant(roles, "bob", "recipes") is True
    text = roles.read_text(encoding="utf-8")
    assert 'write:  ["work/recipes/**"]' in text
    assert 'config: ["work/recipes/**"]' in text
    assert '"work/*/knowledge/**"' in text

    # The engine must accept the result — via the real OPERATION_GRANTS
    # (create/edit/edit_config), not grant-kind names.
    registry = load_roles(vault)
    assert registry.allows("bob", "create", "work/recipes/note.md")
    assert registry.allows("bob", "edit", "work/recipes/note.md")
    assert registry.allows("bob", "edit_config",
                           "work/recipes/.vault/config.yaml")
    assert registry.allows("bob", "read", "work/recipes/note.md")

    # Idempotent: same owner + glob already present → no change.
    assert installer._append_agent_grant(roles, "bob", "recipes") is False


def test_append_agent_grant_refuses_existing_owner(tmp_path):
    hermes, vault = _scratch(tmp_path)
    roles = vault / ".vault" / "roles.yaml"
    installer._append_agent_grant(roles, "bob", "recipes")
    with pytest.raises(ValueError, match="already has grants"):
        installer._append_agent_grant(roles, "bob", "coding")


def test_append_agent_grant_refuses_key_after_agents(tmp_path):
    hermes, vault = _scratch(tmp_path)
    roles = vault / ".vault" / "roles.yaml"
    roles.write_text(roles.read_text(encoding="utf-8")
                     + "\nother_top: x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="top-level key after 'agents:'"):
        installer._append_agent_grant(roles, "bob", "recipes")


def test_append_agent_grant_dry_run_writes_nothing(tmp_path):
    hermes, vault = _scratch(tmp_path)
    roles = vault / ".vault" / "roles.yaml"
    before = roles.read_text(encoding="utf-8")
    assert installer._append_agent_grant(roles, "bob", "recipes",
                                         dry_run=True) is True
    assert roles.read_text(encoding="utf-8") == before


# --- manager grant activation (blank preset fix, 2026-08-04) --------------

def test_ensure_manager_grant_activates_blank_stub(tmp_path):
    """The blank preset ships the manager block commented; the installer must
    activate it so a custom-install manager holds meta/config/read."""
    hermes, vault = _scratch(tmp_path)   # blank preset
    roles = vault / ".vault" / "roles.yaml"
    assert "  vault-manager:" not in roles.read_text(encoding="utf-8")
    assert "# vault-manager:" in roles.read_text(encoding="utf-8")

    assert installer._ensure_manager_grant(roles, "vault-manager") is True
    text = roles.read_text(encoding="utf-8")
    assert "  vault-manager:" in text          # block active
    assert "# vault-manager:" not in text      # stub replaced, not duplicated
    assert 'meta:   ["**"]' in text

    registry = load_roles(vault)
    assert registry.allows("vault-manager", "edit_meta", "system/x.md")
    assert registry.allows("vault-manager", "edit_config", ".vault/config.yaml")

    # Idempotent: an active block is left alone.
    assert installer._ensure_manager_grant(roles, "vault-manager") is False


def test_ensure_manager_grant_noop_on_starter(tmp_path):
    """The starter preset already ships the manager active — nothing to do."""
    hermes, vault = _scratch(tmp_path, with_vault=False)
    installer.scaffold_vault(vault, "default")
    scaffolded = vault / ".vault" / "roles.yaml"
    text = scaffolded.read_text(encoding="utf-8")
    assert "  vault-manager:" in text
    assert installer._ensure_manager_grant(scaffolded, "vault-manager") is False
    assert scaffolded.read_text(encoding="utf-8") == text


# --- add_contributor -------------------------------------------------------

def test_add_contributor_installs_overlay_and_soul(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "creative")
    installer.add_contributor(hermes, "creative", vault)

    target = profile / "skills" / "obsidian-vault"
    assert (target / "SKILL.md").is_symlink()
    soul_text = (profile / "SOUL.md").read_text(encoding="utf-8")
    assert "## Vault" in soul_text
    assert "### Convention manifest" in soul_text
    assert "conventions/contributor.md" in soul_text
    assert "conventions/manager.md" not in soul_text


def test_add_contributor_dry_run_creates_no_profile(tmp_path):
    hermes, vault = _scratch(tmp_path)
    installer.add_contributor(hermes, "bob", vault, dry_run=True)
    assert not (hermes / "profiles" / "bob").exists()


# --- add_domain ------------------------------------------------------------

def test_add_domain_full_flow(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "creative")
    installer.ensure_soul_sections(profile / "SOUL.md", "contributor")

    installer.add_domain(hermes, vault, "recipes", "creative")

    # Tree + config.
    cfg = vault / "work" / "recipes" / ".vault" / "config.yaml"
    assert cfg.is_file()
    assert "work/recipes" in cfg.read_text(encoding="utf-8")

    # Grant correctness through the engine — real operations: owner can
    # create/edit/config inside, cannot reach root .vault/ or roles.yaml.
    registry = load_roles(vault)
    assert registry.allows("creative", "create", "work/recipes/note.md")
    assert registry.allows("creative", "edit", "work/recipes/note.md")
    assert registry.allows("creative", "edit_config",
                           "work/recipes/.vault/config.yaml")
    assert not registry.allows("creative", "edit_config", ".vault/config.yaml")
    assert not registry.allows("creative", "edit", ".vault/roles.yaml")

    # Conventions file + manifest entry.
    conv = (profile / "skills" / "obsidian-vault" / "conventions"
            / f"{vault.name}-conventions.md")
    assert conv.is_file()
    soul_text = (profile / "SOUL.md").read_text(encoding="utf-8")
    assert "recipes domain conventions (work/recipes/**)" in soul_text

    # Idempotent re-run: no duplicate manifest entry, no double grant.
    installer.add_domain(hermes, vault, "recipes", "creative")
    soul_text2 = (profile / "SOUL.md").read_text(encoding="utf-8")
    assert soul_text2.count("recipes domain conventions") == 1
    assert load_roles(vault).allows("creative", "create", "work/recipes/note.md")


def test_add_domain_custom_config_file(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "dev")
    installer.ensure_soul_sections(profile / "SOUL.md", "contributor")

    cfg_file = tmp_path / "recipes.yaml"
    cfg_file.write_text("fields:\n  type:\n    allowed: [recipe, test]\n",
                        encoding="utf-8")
    installer.add_domain(hermes, vault, "recipes", "dev",
                         config_file=str(cfg_file))
    written = (vault / "work" / "recipes" / ".vault" / "config.yaml"
               ).read_text(encoding="utf-8")
    assert "allowed: [recipe, test]" in written


def test_add_domain_refuses_broken_config(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _profile_dir(hermes, "dev")
    cfg_file = tmp_path / "bad.yaml"
    cfg_file.write_text("fields: [unclosed\n", encoding="utf-8")
    with pytest.raises(Exception):
        installer.add_domain(hermes, vault, "recipes", "dev",
                             config_file=str(cfg_file))


def test_add_domain_requires_scaffolded_vault_and_owner(tmp_path):
    hermes, vault = _scratch(tmp_path, with_vault=False)
    with pytest.raises(FileNotFoundError, match="scaffold the vault first"):
        installer.add_domain(hermes, vault, "recipes", "dev")

    hermes2, vault2 = _scratch(tmp_path / "b")
    with pytest.raises(FileNotFoundError, match="does not exist"):
        installer.add_domain(hermes2, vault2, "recipes", "dev")


def test_add_domain_dry_run_writes_nothing(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "creative")
    installer.ensure_soul_sections(profile / "SOUL.md", "contributor")

    installer.add_domain(hermes, vault, "recipes", "creative", dry_run=True)
    assert not (vault / "work" / "recipes").exists()
    assert "recipes domain conventions" not in (
        profile / "SOUL.md").read_text(encoding="utf-8")


# --- add_subdomain ---------------------------------------------------------

def _owner_seeded(vault: Path, owner: str, domain: str) -> None:
    """Seed the owner's grant over work/<domain>/** — the state that exists
    before a subdomain is scaffolded (the owner was added via --add-domain)."""
    installer._append_agent_grant(vault / ".vault" / "roles.yaml",
                                  owner, domain)


def test_add_subdomain_rides_scaffold_and_records_manifest(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "creative")
    installer.ensure_soul_sections(profile / "SOUL.md", "contributor")
    _owner_seeded(vault, "creative", "creative")

    # The tool's side: a scaffolded subdirectory inside the owner's domain.
    (vault / "work" / "creative" / "recipes").mkdir(parents=True)

    installer.add_subdomain(hermes, vault, "work/creative/recipes", "creative")
    soul_text = (profile / "SOUL.md").read_text(encoding="utf-8")
    assert "work/creative/recipes conventions" in soul_text


def test_add_subdomain_requires_existing_dir(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _profile_dir(hermes, "creative")
    with pytest.raises(FileNotFoundError, match="run obsidian_scaffold first"):
        installer.add_subdomain(hermes, vault, "work/creative/recipes",
                                "creative")


def test_add_subdomain_refuses_non_owner(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _profile_dir(hermes, "creative")
    _profile_dir(hermes, "dev")
    _owner_seeded(vault, "creative", "creative")
    (vault / "work" / "creative" / "recipes").mkdir(parents=True)

    # dev has no write over creative's tree.
    with pytest.raises(PermissionError, match="holds no write"):
        installer.add_subdomain(hermes, vault, "work/creative/recipes", "dev")


def test_add_subdomain_dry_run_writes_nothing(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "creative")
    installer.ensure_soul_sections(profile / "SOUL.md", "contributor")
    _owner_seeded(vault, "creative", "creative")
    (vault / "work" / "creative" / "recipes").mkdir(parents=True)

    installer.add_subdomain(hermes, vault, "work/creative/recipes", "creative",
                            dry_run=True)
    assert "work/creative/recipes conventions" not in (
        profile / "SOUL.md").read_text(encoding="utf-8")
