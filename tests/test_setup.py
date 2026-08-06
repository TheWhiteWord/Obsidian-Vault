"""Installer tests (P3.7) — pure functions of scripts/setup.py.

The interactive flow (main) is deliberately not tested; the pure functions —
compose_skill, install_skill, ensure_soul_directive, scaffold_vault — are
what carry the design, and they run against a scratch HERMES_HOME / vault.

The bundled skill fragments are the real ones (read from the plugin dir), so
these tests double as a check that the bundle ships what the installer needs.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import vault_ops as installer

BUNDLED = installer.BUNDLED_SKILL
assert BUNDLED.is_dir(), "bundled skill missing — installer has nothing to overlay"


# --- bundle base -----------------------------------------------------------

def test_bundle_skill_is_contributor_base():
    """The contributor bundle SKILL.md: writing loop + contributor tools.
    No manager tool routing, no conventions_ref, no role routing (the split
    owns the role)."""
    text = (BUNDLED / "SKILL.md").read_text(encoding="utf-8")
    assert "obsidian_context" in text
    assert "obsidian_issue_list" in text
    assert "conventions_ref" not in text
    assert "obsidian_maintain" not in text
    assert "## Role routing" not in text


def test_manager_bundle_skill():
    """The manager bundle SKILL.md: management loop + manager tools."""
    mgr = BUNDLED.parent / "obsidian-vault-management" / "SKILL.md"
    text = mgr.read_text(encoding="utf-8")
    assert "obsidian_maintain" in text
    assert "obsidian_issue_list" in text
    assert "conventions_ref" not in text


# --- install_skill (P5a overlay) -------------------------------------------

def test_install_skills_symlinks_base(tmp_path):
    """Each role's skill dir symlinks to its own bundle (the split)."""
    targets = installer.install_skills(tmp_path, role="contributor")
    assert len(targets) == 1
    contrib = targets[0]
    assert contrib == tmp_path / "note-taking" / "obsidian-vault"
    assert contrib.joinpath("SKILL.md").is_symlink()
    assert contrib.joinpath("SKILL.md").resolve() == (BUNDLED / "SKILL.md").resolve()
    for sub in ("references", "templates"):
        link = contrib / sub
        assert link.is_symlink()
        assert link.resolve() == (BUNDLED / sub).resolve()

    mgr_targets = installer.install_skills(tmp_path / "mgr", role="manager")
    assert len(mgr_targets) == 1
    mgr = mgr_targets[0]
    assert mgr == tmp_path / "mgr" / "note-taking" / "obsidian-vault-management"
    assert mgr.joinpath("SKILL.md").resolve() == \
        (installer.MANAGER_SKILL / "SKILL.md").resolve()


def test_install_skills_combined_installs_both(tmp_path):
    """A one-profile setup (combined) holds both skills."""
    targets = installer.install_skills(tmp_path, role="combined")
    assert sorted(t.name for t in targets) == \
        ["obsidian-vault", "obsidian-vault-management"]
    for t in targets:
        assert t.joinpath("SKILL.md").is_symlink()


def test_install_skills_conventions_dir(tmp_path):
    """Only the contributor skill carries a real conventions/ dir — the
    maintained file's home. The manager skill has none (2026-08-05)."""
    contrib = installer.install_skills(tmp_path, role="contributor")[0]
    conv = contrib / "conventions"
    assert conv.is_dir() and not conv.is_symlink()

    mgr = installer.install_skills(tmp_path / "mgr", role="manager")[0]
    assert not (mgr / "conventions").exists()

    both = installer.install_skills(tmp_path / "both", role="combined")
    contrib2 = next(t for t in both if t.name == "obsidian-vault")
    mgr2 = next(t for t in both if t.name == "obsidian-vault-management")
    assert (contrib2 / "conventions").is_dir()
    assert not (mgr2 / "conventions").exists()


def test_install_skills_never_touches_bundled(tmp_path):
    bundled_before = (BUNDLED / "SKILL.md").read_text(encoding="utf-8")
    installer.install_skills(tmp_path, role="contributor")
    assert (BUNDLED / "SKILL.md").read_text(encoding="utf-8") == bundled_before


def test_maintained_conventions_survive_rerun(tmp_path):
    """The survival regression (2026-08-04 model): the maintained file is
    `<vault>-conventions.md` — the installer never touches it, so a planted
    convention survives a re-install."""
    target = installer.install_skills(tmp_path, role="contributor")[0]
    planted = target / "conventions" / "TWW-conventions.md"
    planted.write_text("# my accumulated conventions\n", encoding="utf-8")

    installer.install_skills(tmp_path, role="contributor")  # re-run

    assert planted.read_text(encoding="utf-8") == "# my accumulated conventions\n"


def _pre_p5a_install(tmp_path: Path) -> Path:
    """Simulate a pre-P5a install: a real copy of the whole bundle dir."""
    target = tmp_path / "note-taking" / "obsidian-vault"
    shutil.copytree(BUNDLED, target)
    return target


def test_stale_copy_replaced_by_symlink(tmp_path):
    """A content-identical pre-P5a copy is replaced by symlinks; conventions/
    survives as a real dir."""
    _pre_p5a_install(tmp_path)
    installer.install_skills(tmp_path, role="contributor")
    target = tmp_path / "note-taking" / "obsidian-vault"
    assert target.joinpath("SKILL.md").is_symlink()
    assert (target / "references").is_symlink()
    assert (target / "templates").is_symlink()
    assert not (target / "conventions").is_symlink()


def test_cow_reference_dir_preserved(tmp_path):
    """A modified real references/ dir is the copy-on-write escape hatch
    (06-growth-design §2.3) — the installer leaves it alone."""
    _pre_p5a_install(tmp_path)
    target = tmp_path / "note-taking" / "obsidian-vault"
    (target / "references" / "custom.md").write_text("custom", encoding="utf-8")
    installer.install_skills(tmp_path, role="contributor")
    assert not (target / "references").is_symlink()
    assert (target / "references" / "custom.md").is_file()


def test_install_skills_role_alignment_drops_other_skill(tmp_path):
    """A contributor promoted to manager loses the contributor skill's
    surface; the manager skill appears (2026-08-05 skill-level alignment)."""
    installer.install_skills(tmp_path, role="contributor")
    contrib = tmp_path / "note-taking" / "obsidian-vault"
    assert contrib.joinpath("SKILL.md").is_symlink()

    installer.install_skills(tmp_path, role="manager")
    assert not contrib.joinpath("SKILL.md").exists()  # surface removed
    mgr = tmp_path / "note-taking" / "obsidian-vault-management"
    assert mgr.joinpath("SKILL.md").is_symlink()


def test_install_skills_alignment_preserves_conventions(tmp_path):
    """Role alignment never deletes the maintained conventions file: the
    contributor skill's conventions/ survives a manager transition."""
    installer.install_skills(tmp_path, role="contributor")
    conv = tmp_path / "note-taking" / "obsidian-vault" / "conventions"
    (conv / "TWW-conventions.md").write_text("# rules\n", encoding="utf-8")

    installer.install_skills(tmp_path, role="manager")

    assert (conv / "TWW-conventions.md").read_text(encoding="utf-8") == "# rules\n"


# --- profile_home -----------------------------------------------------------

def test_profile_home_default_is_hermes_home_root():
    home = Path("/some/hermes")
    assert installer.profile_home(home, "default") == home


def test_profile_home_named_is_under_profiles():
    home = Path("/some/hermes")
    assert installer.profile_home(home, "vault-manager") == \
        home / "profiles" / "vault-manager"


# --- link_plugin ------------------------------------------------------------

def test_link_plugin_symlinks_bundle(tmp_path):
    plugins = tmp_path / "plugins"
    link = installer.link_plugin(plugins)
    assert link.is_symlink()
    assert link.resolve() == installer.PLUGIN_DIR.resolve()
    # idempotent — second call returns the same link, no error
    assert installer.link_plugin(plugins) == link


# --- ensure_profile_env -----------------------------------------------------

def test_ensure_profile_env_writes_both_vars(tmp_path):
    env = tmp_path / ".env"
    assert installer.ensure_profile_env(env, Path("/vault/root"), "creative") is True
    text = env.read_text(encoding="utf-8")
    assert "OBSIDIAN_VAULT_PATH=/vault/root" in text
    assert "OBSIDIAN_VAULT_AGENT=creative" in text
    # idempotent
    assert installer.ensure_profile_env(env, Path("/vault/root"), "creative") is False


def test_ensure_profile_env_upserts_existing_keys(tmp_path):
    env = tmp_path / ".env"
    env.write_text("OBSIDIAN_VAULT_PATH=/old\nSOME_KEY=keep\n", encoding="utf-8")
    installer.ensure_profile_env(env, Path("/new"), "dev")
    text = env.read_text(encoding="utf-8")
    assert "OBSIDIAN_VAULT_PATH=/new" in text
    assert "OBSIDIAN_VAULT_AGENT=dev" in text
    assert "SOME_KEY=keep" in text  # unrelated lines preserved


# --- seed_profile_config ----------------------------------------------------

def _make_default_config(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    (home / "config.yaml").write_text(
        "model:\n  default: deepseek/deepseek-v4-flash-0731\n"
        "memory:\n  memory_enabled: true\n"
        "plugins:\n  enabled: [obsidian-vault]\n",
        encoding="utf-8")
    return home


def test_seed_fills_bare_stub(tmp_path):
    """A stub config (model only, no memory) gets the full default baseline."""
    home = _make_default_config(tmp_path)
    prof = home / "profiles" / "creative"
    prof.mkdir(parents=True)
    (prof / "config.yaml").write_text("model:\n  provider: nous\n",
                                      encoding="utf-8")
    assert installer.seed_profile_config(home, "creative") is True
    text = (prof / "config.yaml").read_text(encoding="utf-8")
    assert "memory:" in text
    assert "deepseek/deepseek-v4-flash-0731" in text


def test_seed_creates_missing_config(tmp_path):
    """The `dev` case — no config.yaml at all; seed must create it."""
    home = _make_default_config(tmp_path)
    prof = home / "profiles" / "dev"
    prof.mkdir(parents=True)
    assert installer.seed_profile_config(home, "dev") is True
    assert "memory:" in (prof / "config.yaml").read_text(encoding="utf-8")


def test_seed_preserves_customised_config(tmp_path):
    """A config already declaring memory: is user-policy — never clobbered."""
    home = _make_default_config(tmp_path)
    prof = home / "profiles" / "researcher"
    prof.mkdir(parents=True)
    custom = "model:\n  default: claude\nmemory:\n  memory_enabled: false\n"
    (prof / "config.yaml").write_text(custom, encoding="utf-8")
    assert installer.seed_profile_config(home, "researcher") is False
    assert (prof / "config.yaml").read_text(encoding="utf-8") == custom


def test_seed_skips_default_profile(tmp_path):
    """default is the source, never a seed target."""
    home = _make_default_config(tmp_path)
    assert installer.seed_profile_config(home, "default") is False


def test_seed_warns_when_no_default_config(tmp_path):
    """No system default config → warn and skip, don't crash."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    prof = home / "profiles" / "x"
    prof.mkdir(parents=True)
    assert installer.seed_profile_config(home, "x") is False
    assert not (prof / "config.yaml").exists()


# --- enable_plugin_for_profile ----------------------------------------------

def test_enable_plugin_default_uses_bare_command(tmp_path, monkeypatch):
    """default is enabled via bare `hermes plugins enable` (no --profile).

    2026-08-04 fix (fresh-machine E2E): default ALSO gets the plugin linked
    into its root plugins dir — plugin discovery scans <home>/plugins, so
    without the link a fresh install's bare enable fails with "not installed
    or bundled". The old "no symlink" assertion encoded the dev-machine
    assumption (bundle already present at the root)."""
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.yaml").write_text("plugins:\n  enabled: []\n",
                                      encoding="utf-8")
    calls = []
    import subprocess
    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)

    installer.enable_plugin_for_profile(home, "default", Path("/vault"))

    assert calls and calls[0][:2] == ["hermes", "plugins"]
    assert "--profile" not in calls[0]
    assert "obsidian-vault" in calls[0]
    link = home / "plugins" / "obsidian-vault"
    assert link.is_symlink()                     # linked — discovery needs it
    assert link.resolve() == installer.PLUGIN_DIR.resolve()
    env = (home / ".env").read_text(encoding="utf-8")
    assert "OBSIDIAN_VAULT_AGENT=default" in env
    assert "OBSIDIAN_VAULT_PATH=/vault" in env


def test_enable_plugin_named_uses_profile_flag(tmp_path, monkeypatch):
    """Named profiles: symlink + `hermes --profile <name> plugins enable`."""
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.yaml").write_text("plugins:\n  enabled: []\n",
                                      encoding="utf-8")
    calls = []
    import subprocess
    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)

    installer.enable_plugin_for_profile(home, "creative", Path("/vault"))

    assert calls and calls[0][:4] == ["hermes", "--profile", "creative",
                                      "plugins"]
    link = home / "profiles" / "creative" / "plugins" / "obsidian-vault"
    assert link.is_symlink()
    env = (home / "profiles" / "creative" / ".env").read_text(encoding="utf-8")
    assert "OBSIDIAN_VAULT_AGENT=creative" in env


def test_enable_plugin_surfaces_failure(tmp_path, monkeypatch, capsys):
    """A failing plugins enable is a visible warning, not silent success."""
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.yaml").write_text("", encoding="utf-8")
    import subprocess
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, "", "boom")
    monkeypatch.setattr(subprocess, "run", fake_run)

    installer.enable_plugin_for_profile(home, "default", Path("/vault"))

    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "boom" in out


# --- install_cron_jobs -----------------------------------------------------

def _fake_run_recorder(calls, list_stdout=""):
    """A subprocess.run fake recording commands; list returns list_stdout."""
    import subprocess
    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        if cmd[-2:] == ["cron", "list"]:
            return subprocess.CompletedProcess(cmd, 0, list_stdout, "")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return fake_run


def _is_create(cmd):
    """Whether a recorded command is a `cron create` (works with and
    without a --profile scope prefix)."""
    return any(cmd[i:i + 2] == ["cron", "create"]
               for i in range(len(cmd) - 1))


def _create_schedule(cmd):
    """The positional schedule right after `cron create`."""
    i = next(i for i in range(len(cmd) - 1)
             if cmd[i:i + 2] == ["cron", "create"])
    return cmd[i + 2]


def test_install_cron_jobs_creates_both_on_named_profile(monkeypatch):
    """Named manager profile: `--profile` scoped create with the two jobs,
    deliver=local, and the manager skill pinned."""
    calls = []
    monkeypatch.setattr(subprocess, "run",
                        _fake_run_recorder(calls, list_stdout=""))

    lines = installer.install_cron_jobs("vault-manager")

    creates = [c for c in calls if _is_create(c)]
    assert len(creates) == 2
    assert {_create_schedule(c) for c in creates} == {"0 5 * * *", "0 6 * * 1"}
    for cmd in creates:
        assert cmd[0] == "hermes" and cmd[1:3] == ["--profile", "vault-manager"]
        assert cmd[cmd.index("--deliver") + 1] == "local"
        assert cmd[cmd.index("--skill") + 1] == "obsidian-vault-management"
        assert "--name" in cmd
    assert all("created on vault-manager" in l for l in lines)


def test_install_cron_jobs_default_uses_bare_command(monkeypatch):
    """One-agent installs: the manager role on `default` → bare hermes cron
    (no --profile), mirroring enable_plugin_for_profile."""
    calls = []
    monkeypatch.setattr(subprocess, "run",
                        _fake_run_recorder(calls, list_stdout=""))

    installer.install_cron_jobs("default")

    creates = [c for c in calls if _is_create(c)]
    assert len(creates) == 2
    for cmd in creates:
        assert cmd[0] == "hermes"
        assert "--profile" not in cmd


def test_install_cron_jobs_skips_existing_by_name(monkeypatch):
    """Idempotency: a job whose name already exists is left untouched; the
    other is still created."""
    calls = []
    monkeypatch.setattr(
        subprocess, "run",
        _fake_run_recorder(
            calls, list_stdout="    Name:      vault-maintain-daily\n"))

    lines = installer.install_cron_jobs("vault-manager")

    creates = [c for c in calls if _is_create(c)]
    assert len(creates) == 1
    assert _create_schedule(creates[0]) == "0 6 * * 1"  # optimize only
    assert any("vault-maintain-daily already exists" in l for l in lines)


def test_install_cron_jobs_dry_run_never_shells(monkeypatch):
    """--dry-run reports the creates without touching the CLI."""
    calls = []
    monkeypatch.setattr(subprocess, "run",
                        _fake_run_recorder(calls))

    lines = installer.install_cron_jobs("vault-manager", dry_run=True)

    assert calls == []
    assert len(lines) == 2 and all("[dry-run]" in l for l in lines)


def test_install_cron_jobs_create_failure_warns(monkeypatch):
    """A failing cron create is a visible WARNING recap line, not a crash."""
    import subprocess
    def fake_run(cmd, **kw):
        if cmd[-2:] == ["cron", "list"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 1, "", "boom")
    monkeypatch.setattr(subprocess, "run", fake_run)

    lines = installer.install_cron_jobs("vault-manager")

    assert len(lines) == 2
    assert all("WARNING" in l and "boom" in l for l in lines)


# --- _create_profile -------------------------------------------------------

def test_create_profile_warns_on_existing(tmp_path, monkeypatch, capsys):
    """Re-running the installer against an existing profile must surface a
    visible warning (the CLI errors with exit 1), not silent success."""
    import subprocess
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(
            cmd, 1, "", "Error: Profile 'vault-manager' already exists")
    monkeypatch.setattr(subprocess, "run", fake_run)

    installer._create_profile("vault-manager", "probe")

    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "already exists" in out


def test_create_profile_silent_on_success(tmp_path, monkeypatch, capsys):
    """A successful profile creation is printed without a warning."""
    import subprocess
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)

    installer._create_profile("creative", "probe")

    out = capsys.readouterr().out
    assert "WARNING" not in out
    assert "create profile: hermes profile create creative" in out


# --- ensure_soul_sections (P5b: role-aware, anchored) -----------------------

def test_soul_sections_contributor_has_lean_sections(tmp_path):
    soul = tmp_path / "SOUL.md"
    assert installer.ensure_soul_sections(soul, "contributor") is True
    text = soul.read_text(encoding="utf-8")
    assert installer.SOUL_ANCHOR in text
    # One `## Vault` umbrella with `###` subsections (2026-08-04); the
    # Convention manifest is retired (P7 — conventions are in-tree).
    assert "## Vault\n" in text
    for section in ("### Vault operations", "### Issues",
                    "### Convention maintenance"):
        assert section in text
    assert "### Convention manifest" not in text
    # Lean pointers: tools/references, not prose instruction.
    assert "obsidian_issue" in text
    assert "references/issues.md" in text
    # Contributor must NOT see the sweep as its job.
    assert "obsidian_maintain" not in text
    # No role-directive files exist anymore; the manifest machinery
    # (and its directed add-marker) is retired (P7).
    assert "conventions/contributor.md" not in text
    assert "conventions/manager.md" not in text
    assert "<!-- add:" not in text
    # Maintained conventions point at the in-tree file (P7).
    assert ".vault/conventions.md" in text


def test_soul_sections_manager_sees_sweep_only(tmp_path):
    soul = tmp_path / "SOUL.md"
    installer.ensure_soul_sections(soul, "manager")
    text = soul.read_text(encoding="utf-8")
    assert "obsidian_maintain" in text
    assert "references/maintenance.md" in text
    # A manager is not a contributor (2026-08-05): no conventions sections,
    # no manifest, no per-vault convention maintenance.
    assert "conventions/contributor.md" not in text
    assert "conventions/manager.md" not in text
    assert "### Convention manifest" not in text
    assert "<vault>-conventions.md" not in text


def test_soul_sections_combined_dedicated_text(tmp_path):
    soul = tmp_path / "SOUL.md"
    installer.ensure_soul_sections(soul, "combined")
    text = soul.read_text(encoding="utf-8")
    assert "obsidian_maintain" in text
    assert "references/issues.md" in text
    # Dedicated combined text: the dual role stated once, conventions kept.
    assert "Dual role" in text
    assert "obsidian_conventions" in text   # in-tree pointer (P7)
    assert "conventions/<vault>" not in text
    assert "conventions/manager.md" not in text
    assert "### Convention manifest" not in text   # retired (P7)


def test_soul_sections_anchor_replace_is_idempotent(tmp_path):
    soul = tmp_path / "SOUL.md"
    soul.write_text("Existing soul.\n", encoding="utf-8")
    assert installer.ensure_soul_sections(soul, "contributor") is True
    text = soul.read_text(encoding="utf-8")
    assert text.startswith("Existing soul.")
    assert installer.SOUL_ANCHOR in text
    # Second call: anchored block replaced in place → no change, no dup.
    assert installer.ensure_soul_sections(soul, "contributor") is False
    assert soul.read_text(encoding="utf-8") == text
    assert text.count(installer.SOUL_ANCHOR) == 1


def test_soul_sections_upgrades_old_single_paragraph(tmp_path):
    """A pre-P5b SOUL with only the old directive gets the full block in
    place — the old paragraph is removed, not duplicated."""
    old = (
        "## Vault operations\n"
        "For any task touching an Obsidian vault (reading/writing notes, "
        "search, graph, index, audit, scaffold), load the `obsidian-vault` "
        "skill first — it routes to the right tools and conventions.\n"
    )
    soul = tmp_path / "SOUL.md"
    soul.write_text(old, encoding="utf-8")
    assert installer.ensure_soul_sections(soul, "manager") is True
    text = soul.read_text(encoding="utf-8")
    assert installer.SOUL_ANCHOR in text
    assert text.count("## Vault operations") == 1
    assert "## Issues" in text


def test_soul_sections_creates_missing_soul(tmp_path):
    soul = tmp_path / "SOUL.md"
    assert installer.ensure_soul_sections(soul, "contributor") is True
    assert soul.is_file()


# --- scaffold_vault --------------------------------------------------------

def test_scaffold_standard_creates_tree(tmp_path):
    root = tmp_path / "vault"
    created = installer.scaffold_vault(root, "standard")
    assert (root / ".vault" / "config.yaml").is_file()
    assert (root / ".vault" / "roles.yaml").is_file()
    for rel in ("system/handbook", "work/creative/knowledge",
                "work/coding/projects"):
        assert (root / rel).is_dir()
    # The issue layer is a ledger (records, not notes) — no note-issue
    # folders, no ISSUES channel configs in the starter (spec 05 v4).
    assert not (root / "system/issues").exists()
    assert not (root / "work/creative/issues").exists()
    assert created  # non-empty


def test_scaffold_blank_creates_only_config(tmp_path):
    """Blank = custom install: bare root, neutral config, deny-by-default
    roles. No starter tree, no five-agent set, no domain configs (P5b)."""
    root = tmp_path / "blank"
    created = installer.scaffold_vault(root, "blank")
    assert (root / ".vault" / "config.yaml").is_file()
    assert (root / ".vault" / "roles.yaml").is_file()
    assert not (root / "system").exists()
    assert not (root / "work").exists()
    assert len(created) == 1  # just the root
    # Neutral roles: only `default` active; the manager is a commented stub.
    import yaml
    agents = yaml.safe_load((root / ".vault" / "roles.yaml").read_text())["agents"]
    assert set(agents) == {"default"}
    assert "vault-manager" not in agents
    # No standing system grant (2026-08-06): a blank preset pre-claims no
    # tree — `default` cannot create in system/** until a --system bind.
    from vault.grants import load_roles
    assert not load_roles(root).allows("default", "create", "system/x.md")
    # D1 (2026-08-05): no conventions pointer in configs — the writing
    # rules live in the loaded skill, not in the vault config.
    cfg = (root / ".vault" / "config.yaml").read_text(encoding="utf-8")
    assert "conventions:" not in cfg


def test_scaffold_copies_readme(tmp_path):
    """The starter README (orientation doc) is scaffolded into a new vault,
    and a customised one survives re-runs (copy-if-missing)."""
    root = tmp_path / "vault"
    installer.scaffold_vault(root, "standard")
    readme = root / "README.md"
    assert readme.is_file()
    assert readme.read_text(encoding="utf-8").strip()
    # customise, re-run, keep
    readme.write_text("# My vault README", encoding="utf-8")
    installer.scaffold_vault(root, "standard")
    assert readme.read_text(encoding="utf-8") == "# My vault README"


def test_scaffold_rerun_preserves_edited_roles(tmp_path):
    """The .vault configs are policy; re-scaffolding must not clobber edits
    (e.g. a customised contributor grant in roles.yaml)."""
    root = tmp_path / "vault"
    installer.scaffold_vault(root, "standard")
    roles = root / ".vault" / "roles.yaml"
    roles.write_text(roles.read_text(encoding="utf-8")
                     .replace('write:  ["work/creative/**"]',
                              'write:  ["work/creative/**", "work/creative/extra/**"]'),
                     encoding="utf-8")
    edited = roles.read_text(encoding="utf-8")

    installer.scaffold_vault(root, "standard")  # re-run — idempotent for policy

    assert roles.read_text(encoding="utf-8") == edited
    assert "work/creative/extra/**" in roles.read_text(encoding="utf-8")
    assert (root / "work" / "creative" / "knowledge").is_dir()  # tree still ensured


def test_scaffold_standard_copies_domain_configs(tmp_path):
    """Per-domain .vault configs (spec §3.3/§3.4/§3.6) ship with the starter."""
    root = tmp_path / "vault"
    installer.scaffold_vault(root, "standard")
    for rel in installer.DOMAIN_CONFIGS:
        assert (root / rel).is_file(), f"missing domain config: {rel}"
    # KNOWLEDGE schema is identical in every domain (the §3.3/§3.6 case).
    creative_k = (root / "work/creative/knowledge/.vault/config.yaml").read_text()
    coding_k = (root / "work/coding/knowledge/.vault/config.yaml").read_text()
    assert creative_k == coding_k
    assert "allowed_only: [knowledge]" in creative_k


def test_scaffold_rerun_preserves_domain_configs(tmp_path):
    """Domain configs are policy too — re-scaffold must not wipe edits."""
    root = tmp_path / "vault"
    installer.scaffold_vault(root, "standard")
    cfg = root / "work/creative/.vault/config.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8") + "\n# custom\n", encoding="utf-8")
    edited = cfg.read_text(encoding="utf-8")

    installer.scaffold_vault(root, "standard")

    assert cfg.read_text(encoding="utf-8") == edited
    assert "# custom" in cfg.read_text(encoding="utf-8")


def test_scaffold_does_not_wire_conventions(tmp_path):
    """D1 (2026-08-05): scaffolded configs carry no conventions pointer —
    the writing rules live in the loaded skill."""
    root = tmp_path / "vault"
    installer.scaffold_vault(root, "standard")
    cfg = (root / ".vault" / "config.yaml").read_text(encoding="utf-8")
    assert "conventions:" not in cfg


# --- starter roles globs (regression: they must reach 2-level-deep paths) ---

def _starter_roles_agents(root: Path) -> dict:
    import yaml
    raw = (root / ".vault" / "roles.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(raw)["agents"]


def test_starter_roles_ship_full_agent_set_active(tmp_path):
    """The standard install ships the full agent set ACTIVE — the vault is
    built for exactly these five profiles (D8/D9). Nothing is commented:
    custom profile sets are a future design consideration, not the default."""
    root = tmp_path / "vault"
    installer.scaffold_vault(root, "standard")
    agents = _starter_roles_agents(root)

    expected = {"default", "vault-manager", "creative", "dev", "researcher"}
    assert set(agents) == expected
    # every agent has at least one grant — no commented shells
    for name, grants in agents.items():
        assert grants, f"{name} has no grants (commented shell?)"


def test_starter_roles_globs_reach_domain_paths(tmp_path):
    from vault.grants import path_matches, load_roles
    root = tmp_path / "vault"
    installer.scaffold_vault(root, "standard")

    # default: owns the system tree, reads all. No issues-channel grants —
    # the issue layer is a ledger (records, not notes); raising requires no
    # grant beyond registration (spec 05 v4).
    agents = _starter_roles_agents(root)
    assert path_matches(agents["default"]["write"][0],
                        "system/handbook/x.md")
    assert path_matches(agents["default"]["read"][0], "work/creative/projects/y.md")
    assert "append" not in agents["default"]

    # The deep-glob fix (P3.7): knowledge folders are two levels under root.
    # NOTE: allows()/check() take OPERATIONS (create/edit/delete/read/...),
    # not grant kinds — "write" is a grant kind, not an operation.
    # Contributors ship ACTIVE in the starter (standard install), so the
    # grant checks below run directly on the scaffolded roles.yaml.
    roles = load_roles(root)
    assert roles.allows("creative", "read", "work/creative/knowledge/kant.md")
    assert roles.allows("creative", "read", "work/coding/knowledge/rust.md")
    assert roles.allows("creative", "create", "work/creative/projects/idea.md")
    assert not roles.allows("creative", "create", "work/coding/projects/x.md")
    # P7 shadowing (spec 07 §2.2): the wildcard write glob is capability-only
    # — inside creative's owned scope it grants nothing. The P7.6 preset
    # restructure makes the researcher the literal owner of knowledge/
    # (enumerated globs), restoring its write there while the domain
    # owners' write is shadowed to it.
    assert roles.allows("researcher", "create",
                        "work/creative/knowledge/kant.md")
    assert not roles.allows("creative", "create",
                            "work/creative/knowledge/kant.md")
    assert roles.allows("researcher", "read", "system/handbook/design.md")
    assert not roles.allows("researcher", "create", "work/creative/projects/idea.md")
    # P7.5: the root conventions file is a system document like README.md —
    # the system owner (default) edits it; contributors and the manager
    # read it only (writes are grant-gated).
    assert roles.allows("default", "edit", ".vault/conventions.md")
    assert not roles.allows("creative", "edit", ".vault/conventions.md")
    assert not roles.allows("vault-manager", "edit", ".vault/conventions.md")
