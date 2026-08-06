"""Setup stage machine tests (P6 redesign, 2026-08-05).

The setup questionnaire is a deterministic stage machine: the script owns
the sequence, validation, and every fs decision; the agent only relays
questions. These tests pin the stage list, answer validation (loop-back
alerts), role accumulation (combined), grant extension, and the full
`_run_setup` drive against a scratch HERMES_HOME.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import setup as installer

from vault_ops import BUNDLED_SKILL, _grant_role, _role_skill  # noqa: E402

BUNDLED = BUNDLED_SKILL
assert BUNDLED.is_dir(), "bundled skill missing — installer has nothing to overlay"


@pytest.fixture
def scratch_home(tmp_path: Path) -> Path:
    """A fake HERMES_HOME: default profile dirs + a fake profile."""
    home = tmp_path / "hermes"
    (home / "skills").mkdir(parents=True)
    (home / "SOUL.md").write_text("# SOUL\n", encoding="utf-8")
    (home / "profiles" / "alice").mkdir(parents=True)
    return home


def _drive(installer, home: Path, answers: list[str]) -> list[str]:
    """Run the stage machine through a full answer sequence.

    Mirrors the agent relay loop: query question → answer → build.
    Returns all printed lines.
    """
    out: list[str] = []
    while True:
        q = installer._run_setup(home, None, False, False)
        assert q == 0
        # find the question marker in the printed output is not possible
        # without capsys — instead drive by stage list directly.
        break
    return out


class TestStageList:
    def test_standard_sequence(self):
        stages = installer._stage_list({"answers": {}})
        assert stages == ["location", "name", "preset",
                          "profile:manager", "profile:creative",
                          "profile:dev", "profile:researcher", "finalize"]

    def test_blank_sequence_single_manager(self):
        stages = installer._stage_list({"answers": {"preset": "blank"}})
        assert stages == ["location", "name", "preset",
                          "profile:manager", "finalize"]


class TestValidation:
    def test_location_nonempty(self, scratch_home):
        ok, alert = installer._validate_answer(
            "location", "  ", scratch_home)
        assert not ok and "cannot be empty" in alert
        ok, _ = installer._validate_answer("location", "/tmp/v", scratch_home)
        assert ok

    def test_name_rejects_slashes(self, scratch_home):
        ok, alert = installer._validate_answer(
            "name", "a/b", scratch_home)
        assert not ok and "slashes" in alert
        ok, _ = installer._validate_answer("name", "TWW", scratch_home)
        assert ok

    def test_preset_choice(self, scratch_home):
        ok, alert = installer._validate_answer("preset", "banana", scratch_home)
        assert not ok
        for good in ("standard", "blank"):
            ok, _ = installer._validate_answer("preset", good, scratch_home)
            assert ok

    def test_create_collides_with_existing_profile(self, scratch_home):
        # 'creative' exists → create must loop back.
        (scratch_home / "profiles" / "creative").mkdir(parents=True)
        ok, alert = installer._validate_answer(
            "profile:creative", "create", scratch_home)
        assert not ok and "already exists" in alert

    def test_existing_must_exist(self, scratch_home):
        ok, alert = installer._validate_answer(
            "profile:manager", "existing:ghost", scratch_home)
        assert not ok and "does not exist" in alert
        ok, _ = installer._validate_answer(
            "profile:manager", "existing:alice", scratch_home)
        assert ok

    def test_default_is_always_valid(self, scratch_home):
        ok, _ = installer._validate_answer(
            "profile:manager", "default", scratch_home)
        assert ok

    def test_bad_profile_answer(self, scratch_home):
        ok, alert = installer._validate_answer(
            "profile:dev", "banana", scratch_home)
        assert not ok and "create" in alert


class TestAccumulation:
    def test_skill_roles(self):
        assert _role_skill({"manager"}) == "manager"
        assert _role_skill({"manager", "creative"}) == "combined"
        assert _role_skill({"creative"}) == "contributor"
        assert _role_skill({"system"}) == "contributor"
        assert _role_skill({"system", "manager"}) == "combined"

    def test_assignments_map_accumulates(self):
        state = {"answers": {
            "profile:manager": "default",
            "profile:creative": "default",
            "profile:dev": "create",
        }}
        a = installer._assignments(state)
        assert a["default"] == {"manager", "creative"}
        assert a["dev"] == {"dev"}

    def test_resolve_profile(self):
        assert installer._resolve_profile("creative", "create") == "creative"
        assert installer._resolve_profile("manager", "create") == "vault-manager"
        assert installer._resolve_profile("dev", "default") == "default"
        assert installer._resolve_profile("dev", "existing:alice") == "alice"


class TestGrantRole:
    def test_fresh_profile_appends_block(self, tmp_path):
        roles = tmp_path / "roles.yaml"
        roles.write_text("agents:\n  default:\n    read: [\"**\"]\n",
                         encoding="utf-8")
        changed = _grant_role(roles, "bob", "creative")
        assert changed
        text = roles.read_text(encoding="utf-8")
        assert "  bob:" in text
        assert '"work/creative/**"' in text
        assert '"work/*/knowledge/**"' in text  # read glob union included
        import yaml
        parsed = yaml.safe_load(text)
        assert parsed["agents"]["bob"]["write"] == ["work/creative/**"]

    def test_existing_profile_extended_not_refused(self, tmp_path):
        # default already holds system/** — the role-accumulation case.
        # Both grant paths (_grant_role, _append_agent_grant) extend an
        # existing block by union; nothing refuses an owner anymore.
        roles = tmp_path / "roles.yaml"
        roles.write_text(
            "agents:\n  default:\n    write: [\"system/**\"]\n"
            "    read: [\"**\"]\n", encoding="utf-8")
        changed = _grant_role(roles, "default", "creative")
        assert changed
        text = roles.read_text(encoding="utf-8")
        assert '"system/**"' in text and '"work/creative/**"' in text
        import yaml
        parsed = yaml.safe_load(text)
        assert parsed["agents"]["default"]["write"] == [
            "system/**", "work/creative/**"]

    def test_idempotent_no_change(self, tmp_path):
        roles = tmp_path / "roles.yaml"
        roles.write_text(
            "agents:\n  bob:\n    write: [\"work/creative/**\"]\n"
            "    config: [\"work/creative/**\"]\n"
            "    meta: [\"work/creative/**\"]\n"
            '    read: ["work/creative/**", "work/*/knowledge/**"]\n',
            encoding="utf-8")
        changed = _grant_role(roles, "bob", "creative")
        assert not changed
        assert '["work/creative/**"]' in roles.read_text(encoding="utf-8")

    def test_manager_role_delegates(self, tmp_path):
        roles = tmp_path / "roles.yaml"
        roles.write_text("agents:\n  default:\n    read: [\"**\"]\n",
                         encoding="utf-8")
        changed = _grant_role(roles, "vault-manager", "manager")
        assert changed
        import yaml
        parsed = yaml.safe_load(roles.read_text(encoding="utf-8"))
        assert parsed["agents"]["vault-manager"]["meta"] == ["**"]


class TestRunSetup:
    def test_question_query_then_answer_drive(self, scratch_home, capsys):
        # q1: location
        rc = installer._run_setup(scratch_home, None, False, False)
        assert rc == 0
        assert 'SETUP:question' in capsys.readouterr().out
        # answer location
        vault = scratch_home / "vault"
        rc = installer._run_setup(scratch_home, str(vault), False, False)
        assert rc == 0
        state = installer._load_setup_state(scratch_home)
        assert state["answers"]["location"] == str(vault)
        assert state["stage"] == 1

    def test_location_rejects_relative(self, scratch_home):
        # a relative location would scaffold into the cwd (real bug found
        # in a live drive — bad/name/ appeared in the repo root)
        ok, alert = installer._validate_answer(
            "location", "bad/name", scratch_home)
        assert not ok and "absolute" in alert

    def test_invalid_answer_loops_back(self, scratch_home, capsys):
        rc = installer._run_setup(scratch_home, "bad/name", False, False)
        # location rejects relative paths → loop-back, stage stays 0
        assert rc == 1
        out = capsys.readouterr().out
        assert "SETUP:alert" in out
        state = installer._load_setup_state(scratch_home)
        assert state["stage"] == 0
        # valid location, then force loop-back on stage 3 (preset)
        installer._run_setup(scratch_home, str(scratch_home / "v"), False, False)
        installer._run_setup(scratch_home, "ok", False, False)  # name
        rc = installer._run_setup(scratch_home, "nonsense", False, False)
        assert rc == 1
        out = capsys.readouterr().out
        assert "SETUP:alert" in out
        # stage did not advance past preset (stage 2)
        state = installer._load_setup_state(scratch_home)
        assert state["stage"] == 2

    def test_reset_clears_state(self, scratch_home, capsys):
        installer._run_setup(scratch_home, "/tmp/v", False, False)
        assert installer._setup_state_path(scratch_home).is_file()
        rc = installer._run_setup(scratch_home, None, True, False)
        assert rc == 0 and "reset" in capsys.readouterr().out
        assert not installer._setup_state_path(scratch_home).exists()

    def test_answer_creates_virgin_home(self, tmp_path, capsys):
        # a fresh machine has NO hermes home yet — the first --answer must
        # create it (real bug found by the fresh-machine E2E, 2026-08-05:
        # _save_setup_state crashed with FileNotFoundError)
        home = tmp_path / "no-such-home"
        vault = tmp_path / "vault"
        rc = installer._run_setup(home, str(vault), False, False)
        assert rc == 0
        state = installer._load_setup_state(home)
        assert state["stage"] == 1
        assert state["answers"]["location"] == str(vault)

    def test_full_standard_drive(self, scratch_home, capsys, monkeypatch):
        """The whole questionnaire against a scratch home, one-agent setup:
        every role on the default profile → combined + grants unioned."""
        vault = scratch_home / "vault"
        # fake profile creation + plugin enable (real CLI is out of scope)
        monkeypatch.setattr(installer, "_create_profile",
                            lambda name, desc: None)
        monkeypatch.setattr(installer, "enable_plugin_for_profile",
                            lambda home, name, vault_root: None)
        answers = [str(vault), "TWW", "standard",
                   "default",  # manager → default
                   "default",  # creative → default
                   "default",  # dev → default
                   "default",  # researcher → default
                   ]
        # finalize runs on the 8th invocation with no answer needed — the
        # stage machine asks 8 questions; the last (finalize) is answered
        # with an empty string meaning "proceed".
        from io import StringIO
        captured = StringIO()
        monkeypatch.setattr(sys, "stdout", captured)
        for i, a in enumerate(answers):
            rc = installer._run_setup(scratch_home, a, False, False)
            assert rc == 0, f"answer {i} ({a}) rejected"
        rc = installer._run_setup(scratch_home, "", False, False)
        assert rc == 0
        out = captured.getvalue()
        assert "SETUP:done" in out or "combined" in out
        # vault scaffolded
        assert (vault / ".vault" / "roles.yaml").is_file()
        # default (combined role) got BOTH skills; conventions live on the
        # contributor skill only
        default_contrib = (scratch_home / "skills" / "note-taking"
                           / "obsidian-vault")
        assert default_contrib.joinpath("SKILL.md").is_symlink()
        assert (default_contrib / "conventions").is_dir()
        default_mgr = (scratch_home / "skills" / "note-taking"
                       / "obsidian-vault-management")
        assert default_mgr.joinpath("SKILL.md").is_symlink()
        # grants unioned: default holds system + creative + coding globs
        import yaml
        parsed = yaml.safe_load(
            (vault / ".vault" / "roles.yaml").read_text(encoding="utf-8"))
        assert "system/**" in parsed["agents"]["default"]["write"]
        assert "work/creative/**" in parsed["agents"]["default"]["write"]
        assert "work/coding/**" in parsed["agents"]["default"]["write"]
        # state reset after finalize (next --setup starts a fresh run)
        state = installer._load_setup_state(scratch_home)
        assert state["stage"] == 0 and state["answers"] == {}

    def test_dry_run_touches_nothing(self, scratch_home, capsys):
        vault = scratch_home / "vault"
        rc = installer._run_setup(scratch_home, str(vault), False, True)
        assert rc == 0
        assert not vault.exists()
        state = installer._load_setup_state(scratch_home)
        assert state["answers"]["location"] == str(vault)
