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
import vault_ops as installer

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


# --- ensure_root_conventions (P7 §4.2) -------------------------------------

def test_ensure_root_conventions_seeds_from_template_and_survives(tmp_path):
    hermes, vault = _scratch(tmp_path, with_vault=False)
    conv = installer.ensure_root_conventions(vault)
    assert conv == vault / ".vault" / "conventions.md"
    text = conv.read_text(encoding="utf-8")
    assert vault.name in text          # <Vault name> substituted
    assert "## Rules" in text          # template body intact

    # Growth through interaction must survive a re-run.
    conv.write_text("# my grown conventions\n", encoding="utf-8")
    again = installer.ensure_root_conventions(vault)
    assert again == conv
    assert again.read_text(encoding="utf-8") == "# my grown conventions\n"


def test_ensure_root_conventions_dry_run_creates_nothing(tmp_path):
    hermes, vault = _scratch(tmp_path, with_vault=False)
    installer.ensure_root_conventions(vault, dry_run=True)
    assert not (vault / ".vault" / "conventions.md").exists()


def test_scaffold_seeds_root_conventions(tmp_path):
    """Both presets get the seeded root conventions file (P7 §4.2)."""
    root = tmp_path / "vault"
    installer.scaffold_vault(root, "blank")
    assert (root / ".vault" / "conventions.md").is_file()
    text = (root / ".vault" / "conventions.md").read_text(encoding="utf-8")
    assert root.name in text           # <Vault name> substituted


# --- _append_agent_grant ---------------------------------------------------

def test_append_agent_grant_adds_block_and_parses(tmp_path):
    hermes, vault = _scratch(tmp_path)
    roles = vault / ".vault" / "roles.yaml"
    assert installer._append_agent_grant(roles, "bob", "recipes") is True
    text = roles.read_text(encoding="utf-8")
    assert 'write: ["work/recipes/**"]' in text
    assert 'config: ["work/recipes/**"]' in text
    assert 'meta: ["work/recipes/**"]' in text   # P7: the backstop grant
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


# --- P7: subdomain bind/unbind (nested ownership) ------------

def test_append_agent_grant_subdomain_shape(tmp_path):
    """P7 N-4: subdomain bind = write/config/meta on the subdomain + read
    over the parent; no shared-knowledge glob."""
    hermes, vault = _scratch(tmp_path)
    roles = vault / ".vault" / "roles.yaml"
    installer._append_agent_grant(roles, "bob", "recipes/knowledge")
    text = roles.read_text(encoding="utf-8")
    assert 'write: ["work/recipes/knowledge/**"]' in text
    assert 'config: ["work/recipes/knowledge/**"]' in text
    assert 'meta: ["work/recipes/knowledge/**"]' in text
    assert 'read: ["work/recipes/**"]' in text
    assert '"work/*/knowledge/**"' not in text

    registry = load_roles(vault)
    assert registry.allows("bob", "create", "work/recipes/knowledge/k.md")
    assert registry.allows("bob", "read", "work/recipes/projects/idea.md")
    assert not registry.allows("bob", "create", "work/recipes/projects/x.md")


def test_validate_domain_bind_refusals(tmp_path):
    hermes, vault = _scratch(tmp_path)
    roles = vault / ".vault" / "roles.yaml"
    with pytest.raises(ValueError, match="one-level subdomain"):
        installer._validate_domain_bind(roles, "bob", "recipes/knowledge/deep")
    with pytest.raises(ValueError, match="one-level subdomain"):
        installer._validate_domain_bind(roles, "bob", "recipes/*")
    installer._validate_domain_bind(roles, "bob", "recipes")  # fine


def test_role_bind_subdomain_flow(tmp_path):
    """bind --domain creative/knowledge: tree + grants + parent read."""
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "researcher")

    installer.role_bind(hermes, vault, "researcher",
                        domain="recipes/knowledge")

    assert (vault / "work" / "recipes" / "knowledge").is_dir()
    registry = load_roles(vault)
    assert registry.allows("researcher", "create",
                           "work/recipes/knowledge/k.md")
    assert registry.allows("researcher", "read", "work/recipes/projects/x.md")
    assert not registry.allows("researcher", "create",
                               "work/recipes/projects/x.md")
    from vault.ownership import owner_of
    globs = {n: g.globs("write") for n, g in registry.agents.items()}
    assert owner_of(globs, "work/recipes/knowledge/k.md") == "researcher"


def test_role_bind_refuses_content_as_subdomain(tmp_path):
    """N-1: same owner as the parent ⇒ content, not a subdomain."""
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "creative")
    installer.role_bind(hermes, vault, "creative", domain="recipes")
    with pytest.raises(ValueError, match="content, not a subdomain"):
        installer.role_bind(hermes, vault, "creative",
                            domain="recipes/knowledge")
    assert not (vault / "work" / "recipes" / "knowledge").exists()


def test_role_bind_refuses_duplicate_ownership(tmp_path):
    """A subdomain needs a single owner — a second bind is refused."""
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "researcher")
    _bound_contributor(hermes, vault, "editor")
    installer.role_bind(hermes, vault, "researcher",
                        domain="recipes/knowledge")
    with pytest.raises(ValueError, match="single owner"):
        installer.role_bind(hermes, vault, "editor",
                            domain="recipes/knowledge")


def test_role_bind_refuses_deep_path_before_writing(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "creative")
    with pytest.raises(ValueError, match="one-level subdomain"):
        installer.role_bind(hermes, vault, "creative",
                            domain="recipes/knowledge/deep")
    assert not (vault / "work" / "recipes").exists()


def test_role_unbind_subdomain_revokes_and_lifts_shadowing(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "writer")
    _bound_contributor(hermes, vault, "researcher")
    installer.role_bind(hermes, vault, "writer", domain="recipes")
    installer.role_bind(hermes, vault, "researcher",
                        domain="recipes/knowledge")

    installer.role_unbind(hermes, vault, "researcher",
                          domain="recipes/knowledge")

    registry = load_roles(vault)
    assert not registry.allows("researcher", "create",
                               "work/recipes/knowledge/k.md")
    assert not registry.allows("researcher", "read",
                               "work/recipes/projects/x.md")
    # shadowing lifts: the writer regains write inside knowledge/
    assert registry.allows("writer", "create", "work/recipes/knowledge/k.md")


def test_role_unbind_subdomain_keeps_parent_read_with_sibling(tmp_path):
    """Unbinding one subdomain keeps the parent read when another remains."""
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "researcher")
    installer.role_bind(hermes, vault, "researcher",
                        domain="recipes/knowledge")
    installer.role_bind(hermes, vault, "researcher", domain="recipes/art")

    installer.role_unbind(hermes, vault, "researcher",
                          domain="recipes/knowledge")

    registry = load_roles(vault)
    assert not registry.allows("researcher", "create",
                               "work/recipes/knowledge/k.md")
    assert registry.allows("researcher", "create", "work/recipes/art/a.md")
    assert registry.allows("researcher", "read", "work/recipes/projects/x.md")


def test_role_unbind_after_manual_case_rename(tmp_path):
    """A case-only folder rename never breaks unbind — globs are found
    case-insensitively, so no unbind/bind dance is needed."""
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "writer")
    installer.role_bind(hermes, vault, "writer", domain="recipes")

    (vault / "work" / "recipes").rename(vault / "work" / "Recipes")

    installer.role_unbind(hermes, vault, "writer", domain="Recipes")

    registry = load_roles(vault)
    assert not registry.allows("writer", "create", "work/recipes/note.md")


def test_bind_domain_reuses_renamed_container(tmp_path):
    """A manually renamed `work` container is reused, never shadow-created:
    a new domain lands under the real container, and the case-insensitive
    grants still cover it."""
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "creative")

    installer.role_bind(hermes, vault, "creative", domain="recipes")
    (vault / "work").rename(vault / "Work")   # user renames the container

    installer.role_bind(hermes, vault, "creative", domain="ideas")

    # The new domain lives under the real container; no shadow `work/`.
    assert (vault / "Work" / "ideas" / ".vault" / "config.yaml").is_file()
    assert not (vault / "work").exists()
    assert (vault / "Work" / "recipes").is_dir()   # original tree untouched

    registry = load_roles(vault)
    assert registry.allows("creative", "create", "work/ideas/note.md")
    assert registry.allows("creative", "create", "work/recipes/note.md")


# --- role_bind (P6) ---------------------------------

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
    assert "### Convention maintenance" in soul_text
    assert "obsidian_conventions" in soul_text
    assert "Convention manifest" not in soul_text   # retired (P7)


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

    # Conventions are in-tree (P7): the root file was seeded by scaffold;
    # the SOUL carries the pointer, never domain entries.
    assert (vault / ".vault" / "conventions.md").is_file()
    soul_text = (profile / "SOUL.md").read_text(encoding="utf-8")
    assert "### Convention maintenance" in soul_text
    assert "domain conventions" not in soul_text

    # Idempotent re-run: no double grant.
    installer.role_bind(hermes, vault, "creative", domain="recipes")
    assert load_roles(vault).allows("creative", "create",
                                    "work/recipes/note.md")


def test_bind_system_tree_full_flow(tmp_path):
    """--system: creates the reserved tree + config and grants write/config
    over system/** — the standard preset's default block as a growth
    action (2026-08-06: blank no longer ships a standing system grant)."""
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "default")

    installer.role_bind(hermes, vault, "default", system_tree=True)

    cfg = vault / "system" / ".vault" / "config.yaml"
    assert cfg.is_file()
    assert "system" in cfg.read_text(encoding="utf-8")

    registry = load_roles(vault)
    assert registry.allows("default", "create", "system/handbook/x.md")
    assert registry.allows("default", "edit_config",
                           "system/.vault/config.yaml")
    assert not registry.allows("default", "edit", ".vault/roles.yaml")


def test_bind_system_tree_uses_config_file(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "default")
    cfg_file = tmp_path / "system-config.yaml"
    cfg_file.write_text("fields:\n  kind:\n    allowed: [spec, log]\n",
                        encoding="utf-8")

    installer.role_bind(hermes, vault, "default", system_tree=True,
                        config_file=str(cfg_file))

    raw = (vault / "system" / ".vault" / "config.yaml").read_text(
        encoding="utf-8")
    assert "allowed: [spec, log]" in raw


def test_bind_system_tree_idempotent(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "default")
    installer.role_bind(hermes, vault, "default", system_tree=True)
    before = (vault / ".vault" / "roles.yaml").read_text(encoding="utf-8")
    installer.role_bind(hermes, vault, "default", system_tree=True)
    assert (vault / ".vault" / "roles.yaml").read_text(
        encoding="utf-8") == before


def test_bind_system_tree_refuses_duplicate_owner(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "bob")
    installer.role_bind(hermes, vault, "bob", system_tree=True)
    _bound_contributor(hermes, vault, "default")
    with pytest.raises(ValueError, match="single owner"):
        installer.role_bind(hermes, vault, "default", system_tree=True)


def test_bind_system_tree_refuses_manager(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _profile_dir(hermes, "vault-manager")
    installer.role_bind(hermes, vault, "vault-manager", manager_role=True)
    with pytest.raises(ValueError, match="no content grants"):
        installer.role_bind(hermes, vault, "vault-manager", system_tree=True)


def test_bind_system_tree_refuses_with_domain(tmp_path):
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "bob")
    with pytest.raises(ValueError, match="mutually exclusive"):
        installer.role_bind(hermes, vault, "bob", system_tree=True,
                            domain="recipes")


def test_bind_domain_on_existing_tree_grants_only(tmp_path):
    """bind --domain on an already-scaffolded tree = grant only (P7)."""
    hermes, vault = _scratch(tmp_path)
    _bound_contributor(hermes, vault, "creative")
    (vault / "work" / "notes").mkdir(parents=True)   # pre-existing tree

    installer.role_bind(hermes, vault, "creative", domain="notes")
    assert load_roles(vault).allows("creative", "create", "work/notes/a.md")


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


def test_remove_soul_sections_full_soul_restores_default(tmp_path):
    """P8.1: unbinding a profile whose full soul is engine-written (prose
    matches a shipped template) restores DEFAULT_SOUL_MD — the pre-bind
    seed — rather than leaving a stale identity behind."""
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "creative")
    soul = profile / "SOUL.md"
    # The helper seeds "# SOUL\n" (customized) — restore the pristine
    # Hermes seed so the full-soul replace path fires.
    soul.write_text(installer.DEFAULT_SOUL_MD, encoding="utf-8")
    installer.ensure_soul_sections(soul, "contributor",
                                   profile_name="creative",
                                   identity="creative")
    text = soul.read_text(encoding="utf-8")
    assert text.startswith("# Identity")
    assert installer.SOUL_ANCHOR in text

    assert installer.remove_soul_sections(soul) is True
    rest = soul.read_text(encoding="utf-8")
    assert rest == installer.DEFAULT_SOUL_MD
    assert installer.SOUL_ANCHOR not in rest
    assert "# Identity" not in rest


def test_remove_soul_sections_full_soul_user_edited_prose_kept(tmp_path):
    """P8.1: once the user edits the identity prose, unbind removes only
    the vault block — the edited identity survives (never destroyed)."""
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "dev")
    soul = profile / "SOUL.md"
    soul.write_text(installer.DEFAULT_SOUL_MD, encoding="utf-8")
    installer.ensure_soul_sections(soul, "contributor",
                                   profile_name="dev", identity="dev")
    edited = soul.read_text(encoding="utf-8").replace(
        "You are the developer — you build software that works",
        "You are the developer — you build software that works, "
        "and I work on games.")
    soul.write_text(edited, encoding="utf-8")

    assert installer.remove_soul_sections(soul) is True
    rest = soul.read_text(encoding="utf-8")
    assert "and I work on games" in rest
    assert installer.SOUL_ANCHOR not in rest


def test_remove_soul_sections_manager_full_soul_restores_default(tmp_path):
    """P8.1 review: unbinding an engine-written manager full soul restores
    DEFAULT_SOUL_MD, like any other full soul."""
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "vault-manager")
    soul = profile / "SOUL.md"
    soul.write_text(installer.DEFAULT_SOUL_MD, encoding="utf-8")
    installer.ensure_soul_sections(soul, "manager",
                                   profile_name="vault-manager",
                                   identity="manager")
    assert soul.read_text(encoding="utf-8").startswith("# Identity")
    assert installer.remove_soul_sections(soul) is True
    assert soul.read_text(encoding="utf-8") == installer.DEFAULT_SOUL_MD


# --- --soul FILE (P8.1 review: note c) ------------------------------------

def test_apply_soul_prose_replaces_identity_keeps_block(tmp_path):
    """--soul FILE replaces the identity prose ahead of the anchor; the
    managed block (and anything after it) survives byte-for-byte."""
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "creative")
    soul = profile / "SOUL.md"
    soul.write_text(installer.DEFAULT_SOUL_MD, encoding="utf-8")
    installer.ensure_soul_sections(soul, "contributor",
                                   profile_name="creative",
                                   identity="creative")
    block_tail = soul.read_text(encoding="utf-8").split(
        installer.SOUL_ANCHOR, 1)[1]

    prose = tmp_path / "new-identity.md"
    prose.write_text("# Identity\nI now also cover recipes.\n", encoding="utf-8")
    assert installer._apply_soul_prose(soul, str(prose), "contributor") is True
    text = soul.read_text(encoding="utf-8")
    assert text.startswith("# Identity\nI now also cover recipes.")
    assert installer.SOUL_ANCHOR in text
    assert text.split(installer.SOUL_ANCHOR, 1)[1] == block_tail


def test_apply_soul_prose_on_pristine_writes_full(tmp_path):
    """--soul FILE on a fresh/pristine profile writes prose + block."""
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "bob")
    soul = profile / "SOUL.md"
    soul.write_text(installer.DEFAULT_SOUL_MD, encoding="utf-8")
    prose = tmp_path / "bob-soul.md"
    prose.write_text("# Identity\nYou are the recipes keeper.\n", encoding="utf-8")
    assert installer._apply_soul_prose(soul, str(prose), "contributor") is True
    text = soul.read_text(encoding="utf-8")
    assert text.startswith("# Identity\nYou are the recipes keeper.")
    assert installer.SOUL_ANCHOR in text


def test_apply_soul_prose_refuses_customized_unmanaged(tmp_path):
    """--soul FILE refuses a customized SOUL with no managed block — never
    claims an identity the installer did not create."""
    hermes, vault = _scratch(tmp_path)
    profile = _profile_dir(hermes, "bob")
    soul = profile / "SOUL.md"
    soul.write_text("# My custom soul\n", encoding="utf-8")
    prose = tmp_path / "bob-soul.md"
    prose.write_text("# Identity\nprose\n", encoding="utf-8")
    with pytest.raises(ValueError):
        installer._apply_soul_prose(soul, str(prose), "contributor")


def test_bind_domain_notice_on_full_soul_profile(tmp_path, capsys):
    """Note c: binding a domain to a profile that already has identity
    prose ahead of the block (full role soul OR user-customised) prints a
    review notice; a pristine block-only profile does not."""
    hermes, vault = _scratch(tmp_path)
    # A profile with a full soul (pristine seed first).
    profile = _profile_dir(hermes, "creative")
    soul = profile / "SOUL.md"
    soul.write_text(installer.DEFAULT_SOUL_MD, encoding="utf-8")
    installer.ensure_soul_sections(soul, "contributor",
                                   profile_name="creative",
                                   identity="creative")
    installer.role_bind(hermes, vault, "creative", domain="recipes")
    out = capsys.readouterr().out
    assert "full role SOUL" in out
    assert "bind --soul FILE" in out

    # A user-customised soul (no template identity) also gets the notice —
    # its identity may need review after the domain add.
    capsys.readouterr()
    _profile_dir(hermes, "dev")
    (hermes / "profiles" / "dev" / "SOUL.md").write_text(
        "# My Own Soul\nI am custom.\n", encoding="utf-8")
    installer.role_bind(hermes, vault, "dev", domain="coding")
    out = capsys.readouterr().out
    assert "full role SOUL" in out

    # A pristine block-only profile (DEFAULT seed + block, no identity)
    # gets no notice — nothing to review.
    capsys.readouterr()
    _profile_dir(hermes, "researcher")
    (hermes / "profiles" / "researcher" / "SOUL.md").write_text(
        installer.DEFAULT_SOUL_MD, encoding="utf-8")
    installer.role_bind(hermes, vault, "researcher", domain="knowledge")
    out = capsys.readouterr().out
    assert "full role SOUL" not in out


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
    assert "domain conventions" not in soul_text   # manifest retired (P7)
    assert installer.SOUL_ANCHOR in soul_text      # SOUL untouched


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


def test_transfer_domain_moves_ownership(tmp_path):
    hermes, vault = _scratch(tmp_path)
    a = _bound_contributor(hermes, vault, "alice")
    installer.role_bind(hermes, vault, "alice", domain="recipes")
    b = _bound_contributor(hermes, vault, "bob")

    installer.role_transfer(hermes, vault, "alice", "bob", domain="recipes")

    registry = load_roles(vault)
    assert not registry.allows("alice", "create", "work/recipes/a.md")
    assert registry.allows("bob", "create", "work/recipes/a.md")
    assert (vault / "work" / "recipes").is_dir()        # tree untouched
    # conventions are in-tree (P7) — neither SOUL carries domain entries
    assert "domain conventions" not in (a / "SOUL.md").read_text(
        encoding="utf-8")
    assert "domain conventions" not in (b / "SOUL.md").read_text(
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
