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
    assert not (profile / "skills" / "note-taking" / "obsidian-vault" / "conventions").exists()


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
    assert 'write: ["work/recipes/**"]' in text
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


def test_append_agent_grant_extends_existing_owner(tmp_path):
    """Role accumulation is first-class: an owner with grants is EXTENDED
    (unioned), never refused (P6; old behavior refused with ValueError)."""
    hermes, vault = _scratch(tmp_path)
    roles = vault / ".vault" / "roles.yaml"
    installer._append_agent_grant(roles, "bob", "recipes")
    assert installer._append_agent_grant(roles, "bob", "coding") is True
    text = roles.read_text(encoding="utf-8")
    assert '"work/recipes/**"' in text
    assert '"work/coding/**"' in text
    registry = load_roles(vault)
    assert registry.allows("bob", "create", "work/recipes/note.md")
    assert registry.allows("bob", "create", "work/coding/note.md")
    # idempotent after extension too
    assert installer._append_agent_grant(roles, "bob", "coding") is False


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
    installer.scaffold_vault(vault, "standard")
    scaffolded = vault / ".vault" / "roles.yaml"
    text = scaffolded.read_text(encoding="utf-8")
    assert "  vault-manager:" in text
    assert installer._ensure_manager_grant(scaffolded, "vault-manager") is False
    assert scaffolded.read_text(encoding="utf-8") == text


# --- role_bind (P6, 06-growth-design §4.5) ---------------------------------

def _bound_contributor(hermes: Path, vault: Path, name: str) -> Path:
    """Pre-create a profile and bind it as a bare contributor."""
    profile = _profile_dir(hermes, name)
    installer.role_bind(hermes, vault, name)
    return profile


def test_bind_new_profile_installs_overlay_and_soul(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "creative")   # pre-created → CLI skipped
    installer.role_bind(hermes, vault, "creative", new=True)

    target = profile / "skills" / "note-taking" / "obsidian-vault"
    assert (target / "SKILL.md").is_symlink()
    soul_text = (profile / "SOUL.md").read_text(encoding="utf-8")
    assert "## Vault" in soul_text
    assert "### Convention manifest" in soul_text
    assert "<vault>-conventions.md" in soul_text


def test_bind_existing_profile_without_new(tmp_path):
    """The flagged gap (2026-08-05): a pre-existing profile can be bound."""
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "bob")
    installer.role_bind(hermes, vault, "bob")     # no --new
    assert (profile / "skills" / "note-taking" / "obsidian-vault"
            / "SKILL.md").is_symlink()


def test_bind_requires_profile_or_new(tmp_path):
    hermes, vault = _scratch(tmp_path)
    with pytest.raises(FileNotFoundError, match="use --new"):
        installer.role_bind(hermes, vault, "ghost")


def test_bind_domain_full_flow(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _bound_contributor(hermes, vault, "creative")

    installer.role_bind(hermes, vault, "creative", domain="recipes")

    # Tree + config.
    cfg = vault / "work" / "recipes" / ".vault" / "config.yaml"
    assert cfg.is_file()
    assert "work/recipes" in cfg.read_text(encoding="utf-8")

    # Grant correctness through the engine — real operations.
    registry = load_roles(vault)
    assert registry.allows("creative", "create", "work/recipes/note.md")
    assert registry.allows("creative", "edit", "work/recipes/note.md")
    assert registry.allows("creative", "edit_config",
                           "work/recipes/.vault/config.yaml")
    assert not registry.allows("creative", "edit_config", ".vault/config.yaml")
    assert not registry.allows("creative", "edit", ".vault/roles.yaml")

    # Conventions file + manifest entry.
    conv = (profile / "skills" / "note-taking" / "obsidian-vault" / "conventions"
            / f"{vault.name}-conventions.md")
    assert conv.is_file()
    soul_text = (profile / "SOUL.md").read_text(encoding="utf-8")
    assert "recipes domain conventions (work/recipes/**)" in soul_text

    # Idempotent re-run: no duplicate manifest entry, no double grant.
    installer.role_bind(hermes, vault, "creative", domain="recipes")
    soul_text2 = (profile / "SOUL.md").read_text(encoding="utf-8")
    assert soul_text2.count("recipes domain conventions") == 1
    assert load_roles(vault).allows("creative", "create",
                                    "work/recipes/note.md")


def test_bind_domain_on_existing_tree_grants_only(tmp_path):
    """bind --domain on an already-scaffolded tree = grant + manifest."""
    hermes, vault = _scratch(tmp_path)
    profile = _bound_contributor(hermes, vault, "creative")
    (vault / "work" / "notes").mkdir(parents=True)   # pre-existing tree

    installer.role_bind(hermes, vault, "creative", domain="notes")
    assert load_roles(vault).allows("creative", "create", "work/notes/a.md")
    soul_text = (profile / "SOUL.md").read_text(encoding="utf-8")
    assert "notes domain conventions (work/notes/**)" in soul_text


def test_bind_domain_custom_config_file(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "dev")

    cfg_file = tmp_path / "recipes.yaml"
    cfg_file.write_text("fields:\n  type:\n    allowed: [recipe, test]\n",
                        encoding="utf-8")
    installer.role_bind(hermes, vault, "dev", domain="recipes",
                        config_file=str(cfg_file))
    written = (vault / "work" / "recipes" / ".vault" / "config.yaml"
               ).read_text(encoding="utf-8")
    assert "allowed: [recipe, test]" in written


def test_bind_domain_refuses_broken_config(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "dev")
    cfg_file = tmp_path / "bad.yaml"
    cfg_file.write_text("fields: [unclosed\n", encoding="utf-8")
    with pytest.raises(Exception):
        installer.role_bind(hermes, vault, "dev", domain="recipes",
                            config_file=str(cfg_file))


def test_bind_refuses_manager_flag_with_domain(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _profile_dir(hermes, "bob")
    with pytest.raises(ValueError, match="mutually exclusive"):
        installer.role_bind(hermes, vault, "bob", manager_role=True,
                            domain="recipes")


def test_bind_domain_refused_on_manager_profile(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "bob")
    installer.role_bind(hermes, vault, "bob", manager_role=True)
    assert "### Convention manifest" not in (
        profile / "SOUL.md").read_text(encoding="utf-8")   # manager SOUL
    with pytest.raises(ValueError, match="managers hold no content grants"):
        installer.role_bind(hermes, vault, "bob", domain="recipes")


def test_bind_manager_grants_and_soul(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "vault-manager")
    installer.role_bind(hermes, vault, "vault-manager", manager_role=True)

    registry = load_roles(vault)
    assert registry.allows("vault-manager", "edit_meta", "system/x.md")
    assert registry.allows("vault-manager", "edit_config",
                           ".vault/config.yaml")
    soul_text = (profile / "SOUL.md").read_text(encoding="utf-8")
    assert "obsidian-vault-management" in soul_text      # manager surface
    assert "### Convention maintenance" not in soul_text  # manager: none


def test_bind_manager_on_contributor_becomes_combined(tmp_path):
    """A contributor who becomes the manager gets the combined surface."""
    hermes, vault = _scratch(tmp_path)
    profile = _bound_contributor(hermes, vault, "creative")
    installer.role_bind(hermes, vault, "creative", domain="creative")

    installer.role_bind(hermes, vault, "creative", manager_role=True)
    skills = profile / "skills" / "note-taking"
    assert (skills / "obsidian-vault" / "SKILL.md").is_symlink()
    assert (skills / "obsidian-vault-management" / "SKILL.md").is_symlink()
    soul_text = (profile / "SOUL.md").read_text(encoding="utf-8")
    assert "Dual role" in soul_text                     # combined variant
    registry = load_roles(vault)
    assert registry.allows("creative", "edit_meta", "system/x.md")
    assert registry.allows("creative", "create", "work/creative/note.md")


def test_bind_dry_run_writes_nothing(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _profile_dir(hermes, "bob")
    installer.role_bind(hermes, vault, "bob", domain="recipes", dry_run=True)
    assert not (vault / "work" / "recipes").exists()
    assert not (vault / ".vault" / "roles.yaml").read_text(
        encoding="utf-8").count("bob:")


# --- remove_soul_sections --------------------------------------------------

def test_remove_soul_sections_removes_block_keeps_rest(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "creative")
    installer.ensure_soul_sections(profile / "SOUL.md", "contributor")
    soul = profile / "SOUL.md"
    text = soul.read_text(encoding="utf-8")
    assert installer.SOUL_ANCHOR in text

    # user content after the block must survive
    soul.write_text(text + "\n## Personal\n- keep me\n", encoding="utf-8")
    assert installer.remove_soul_sections(soul) is True
    rest = soul.read_text(encoding="utf-8")
    assert installer.SOUL_ANCHOR not in rest
    assert "## Personal" in rest
    assert "keep me" in rest

    assert installer.remove_soul_sections(soul) is False  # idempotent


# --- role_unbind -----------------------------------------------------------

def test_unbind_full_revokes_and_cleans(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _bound_contributor(hermes, vault, "creative")
    installer.role_bind(hermes, vault, "creative", domain="recipes")
    _profile_dir(hermes, "vault-manager")   # manager must exist
    installer.role_bind(hermes, vault, "vault-manager", manager_role=True)
    soul = profile / "SOUL.md"
    env = profile / ".env"
    env.write_text(f"OBSIDIAN_VAULT_PATH={vault}\nOTHER=x\n"
                   f"OBSIDIAN_VAULT_AGENT=creative\n", encoding="utf-8")

    installer.role_unbind(hermes, vault, "creative")

    roles_text = (vault / ".vault" / "roles.yaml").read_text(
        encoding="utf-8")
    assert "# creative:" in roles_text          # commented, deny-by-default
    assert "  creative:" not in roles_text      # no active block
    registry = load_roles(vault)
    assert not registry.allows("creative", "create", "work/recipes/a.md")
    assert installer.SOUL_ANCHOR not in soul.read_text(encoding="utf-8")
    assert not (profile / "skills" / "note-taking" / "obsidian-vault"
                / "SKILL.md").is_symlink()
    assert not (profile / "skills" / "note-taking").exists()
    env_text = env.read_text(encoding="utf-8")
    assert "OBSIDIAN_VAULT_PATH" not in env_text
    assert "OTHER=x" in env_text                # other env preserved
    # the manager is untouched
    assert load_roles(vault).allows("vault-manager", "edit_meta",
                                    "system/x.md")


def test_unbind_refuses_manager(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _profile_dir(hermes, "vault-manager")
    installer.role_bind(hermes, vault, "vault-manager", manager_role=True)
    with pytest.raises(ValueError, match="must keep a manager"):
        installer.role_unbind(hermes, vault, "vault-manager")


def test_unbind_domain_unowns_keeps_tree(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _bound_contributor(hermes, vault, "creative")
    installer.role_bind(hermes, vault, "creative", domain="recipes")
    installer.role_bind(hermes, vault, "creative", domain="notes")
    tree = vault / "work" / "recipes"
    assert tree.is_dir()

    installer.role_unbind(hermes, vault, "creative", domain="recipes")

    assert tree.is_dir()                        # tree kept + notice
    registry = load_roles(vault)
    assert not registry.allows("creative", "create", "work/recipes/a.md")
    assert registry.allows("creative", "create", "work/notes/a.md")
    soul_text = (profile / "SOUL.md").read_text(encoding="utf-8")
    assert "recipes domain conventions" not in soul_text
    assert "notes domain conventions" in soul_text
    assert installer.SOUL_ANCHOR in soul_text   # SOUL untouched


def test_unbind_domain_nothing_held(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "creative")
    with pytest.raises(ValueError, match="holds no grants under"):
        installer.role_unbind(hermes, vault, "creative", domain="recipes")


def test_unbind_domain_allowed_on_combined_manager(tmp_path):
    """A manager who ALSO owns a domain (combined) may unown it — the
    refusal is reserved for PURE managers (regression from the E2E)."""
    hermes, vault = _scratch(tmp_path)
    profile = _bound_contributor(hermes, vault, "dev")
    installer.role_bind(hermes, vault, "dev", domain="coding")
    installer.role_bind(hermes, vault, "dev", manager_role=True)  # combined
    assert (vault / "work" / "coding").is_dir()

    installer.role_unbind(hermes, vault, "dev", domain="coding")

    registry = load_roles(vault)
    assert not registry.allows("dev", "create", "work/coding/x.md")
    assert registry.allows("dev", "edit_meta", "system/x.md")  # still manager
    assert installer.SOUL_ANCHOR in (profile / "SOUL.md").read_text(
        encoding="utf-8")


def test_unbind_domain_refused_on_pure_manager(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _profile_dir(hermes, "vault-manager")
    installer.role_bind(hermes, vault, "vault-manager", manager_role=True)
    with pytest.raises(ValueError, match="pure manager"):
        installer.role_unbind(hermes, vault, "vault-manager",
                              domain="recipes")


def test_unbind_default_warns(tmp_path, capsys):
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "default")
    installer.role_bind(hermes, vault, "default")
    _profile_dir(hermes, "vault-manager")
    installer.role_bind(hermes, vault, "vault-manager", manager_role=True)

    installer.role_unbind(hermes, vault, "default")
    out = capsys.readouterr().out
    assert "default was the system owner" in out
    assert not (profile / "skills" / "note-taking").exists()


def test_unbind_dry_run_writes_nothing(tmp_path):
    hermes, vault = _scratch(tmp_path)
    profile = _bound_contributor(hermes, vault, "creative")
    installer.role_bind(hermes, vault, "creative", domain="recipes")
    soul = profile / "SOUL.md"
    before = soul.read_text(encoding="utf-8")

    installer.role_unbind(hermes, vault, "creative", dry_run=True)
    assert soul.read_text(encoding="utf-8") == before
    assert "  creative:" in (vault / ".vault" / "roles.yaml").read_text(
        encoding="utf-8")


# --- role_transfer ---------------------------------------------------------

def test_transfer_manager_handoff_combined(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _profile_dir(hermes, "vault-manager")
    installer.role_bind(hermes, vault, "vault-manager", manager_role=True)
    profile = _bound_contributor(hermes, vault, "creative")
    installer.role_bind(hermes, vault, "creative", domain="creative")

    installer.role_transfer(hermes, vault, "vault-manager", "creative")

    registry = load_roles(vault)
    assert registry.allows("creative", "edit_meta", "system/x.md")
    assert registry.allows("creative", "create", "work/creative/a.md")
    assert not registry.allows("vault-manager", "edit_meta", "system/x.md")
    assert "  vault-manager:" not in (vault / ".vault" / "roles.yaml"
                                      ).read_text(encoding="utf-8")
    # creative: combined surface; old manager: fully unbound
    skills = profile / "skills" / "note-taking"
    assert (skills / "obsidian-vault" / "SKILL.md").is_symlink()
    assert (skills / "obsidian-vault-management" / "SKILL.md").is_symlink()
    assert "Dual role" in (profile / "SOUL.md").read_text(encoding="utf-8")
    old_home = installer.profile_home(hermes, "vault-manager")
    assert installer.SOUL_ANCHOR not in (old_home / "SOUL.md").read_text(
        encoding="utf-8")
    assert not (old_home / "skills" / "note-taking").exists()


def test_transfer_manager_handoff_demotes_source_to_contributor(tmp_path):
    """A manager who also owns a domain keeps the contributor surface."""
    hermes, vault = _scratch(tmp_path)
    profile = _bound_contributor(hermes, vault, "bob")
    installer.role_bind(hermes, vault, "bob", domain="recipes")
    installer.role_bind(hermes, vault, "bob", manager_role=True)  # combined
    _profile_dir(hermes, "carol")
    installer.role_bind(hermes, vault, "carol")   # bare contributor

    installer.role_transfer(hermes, vault, "bob", "carol")

    registry = load_roles(vault)
    assert not registry.allows("bob", "edit_meta", "system/x.md")
    assert registry.allows("bob", "create", "work/recipes/a.md")
    assert registry.allows("carol", "edit_meta", "system/x.md")
    # bob: back to contributor surface (manager skill symlinks removed)
    skills = profile / "skills" / "note-taking"
    assert (skills / "obsidian-vault" / "SKILL.md").is_symlink()
    assert not (skills / "obsidian-vault-management" / "SKILL.md").exists()
    soul_text = (profile / "SOUL.md").read_text(encoding="utf-8")
    assert "### Convention maintenance" in soul_text   # contributor block
    assert "Dual role" not in soul_text
    # carol: manager surface
    carol = installer.profile_home(hermes, "carol")
    assert "obsidian-vault-management" in (carol / "SOUL.md").read_text(
        encoding="utf-8")


def test_transfer_domain_moves_ownership_and_manifest(tmp_path):
    hermes, vault = _scratch(tmp_path)
    a = _bound_contributor(hermes, vault, "alice")
    installer.role_bind(hermes, vault, "alice", domain="recipes")
    b = _bound_contributor(hermes, vault, "bob")

    installer.role_transfer(hermes, vault, "alice", "bob", domain="recipes")

    registry = load_roles(vault)
    assert not registry.allows("alice", "create", "work/recipes/a.md")
    assert registry.allows("bob", "create", "work/recipes/a.md")
    assert (vault / "work" / "recipes").is_dir()        # tree untouched
    assert "recipes domain conventions" not in (a / "SOUL.md").read_text(
        encoding="utf-8")
    assert "recipes domain conventions" in (b / "SOUL.md").read_text(
        encoding="utf-8")


def test_transfer_refuses_non_manager_without_domain(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "alice")
    _bound_contributor(hermes, vault, "bob")
    with pytest.raises(ValueError, match="not the manager"):
        installer.role_transfer(hermes, vault, "alice", "bob")


def test_transfer_same_profile_refused(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "alice")
    with pytest.raises(ValueError, match="same profile"):
        installer.role_transfer(hermes, vault, "alice", "alice")


def test_transfer_domain_on_manager_refused(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _profile_dir(hermes, "vault-manager")
    installer.role_bind(hermes, vault, "vault-manager", manager_role=True)
    _bound_contributor(hermes, vault, "bob")
    with pytest.raises(ValueError, match="--domain transfer"):
        installer.role_transfer(hermes, vault, "vault-manager", "bob",
                                domain="recipes")


def test_transfer_requires_existing_target(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _profile_dir(hermes, "vault-manager")
    installer.role_bind(hermes, vault, "vault-manager", manager_role=True)
    with pytest.raises(FileNotFoundError, match="bind it first"):
        installer.role_transfer(hermes, vault, "vault-manager", "ghost")


# --- role_list -------------------------------------------------------------

def test_role_list_shows_bindings(tmp_path, capsys):
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "creative")
    installer.role_bind(hermes, vault, "creative", domain="recipes")
    _profile_dir(hermes, "vault-manager")
    installer.role_bind(hermes, vault, "vault-manager", manager_role=True)

    installer.role_list(hermes, vault)
    out = capsys.readouterr().out
    assert "manager: vault-manager" in out
    assert "creative: role=contributor" in out
    assert "domains=['recipes']" in out
    assert "soul=yes" in out
