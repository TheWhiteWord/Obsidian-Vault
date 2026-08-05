"""Portability guard — the engine must work on ANY vault layout.

The plugin is a schema-driven vault engine; Davide's SYSTEM/CREATIVE setup is
one *configuration* of it. These tests fail if vault-specific policy leaks
into engine code, which is what would quietly make the plugin un-open-sourceable.

Mechanism (code) vs policy (config):
  code    — inheritance, uniformity contract, declared/observed, grants
  config  — which trees, which fields, which vocabularies, who may write where
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from vault.config import resolve_config
from vault.context import build_context
from vault.notes import iter_notes

ENGINE_DIR = Path(__file__).resolve().parents[1] / "vault"

#: Folder and field names from *a* vault, which must never appear in engine code.
POLICY_NAMES = [
    "SYSTEM", "CREATIVE", "KNOWLEDGE", "ISSUES", "HANDBOOK",
    "DECISIONS", "PHILOSOPHY", "PROJECTS",
]

#: Engine-reserved names — mechanism, not policy. `STATE` (the constant
#: `constants.STATE_DIRNAME`, value `.state`) is the machine ledger. `ISSUES`
#: (`constants.ISSUES_DIRNAME`) is the issue ledger — issues are records, not
#: notes, so the name is engine machinery too. `VAULT` appears in docstrings.
#: These are exempt from the policy-name guard.
RESERVED_NAMES = {"STATE", "ISSUES", "VAULT"}


class TestNoHardcodedPolicy:
    def test_engine_names_no_vault_folders(self):
        offenders = []
        for src in ENGINE_DIR.glob("*.py"):
            for lineno, line in enumerate(src.read_text().splitlines(), 1):
                code = line.split("#")[0]
                # Engine-reserved names (STATE / VAULT) are mechanism, not policy;
                # they appear as named constants (constants.STATE_DIRNAME). Exempt.
                if any(rn in re.findall(r"[A-Z_]+", code) for rn in RESERVED_NAMES):
                    stripped = code
                    for rn in RESERVED_NAMES:
                        stripped = stripped.replace(rn, "")
                    if not any(re.search(rf"\b{name}\b", stripped) for name in POLICY_NAMES):
                        continue
                # Skip illustrative glob examples and description/meaning string
                # values (e.g. ROLES_OPTIONS help text mentioning ISSUES). They
                # *describe* policy; they are not the engine assuming it.
                if "*/" in code or "**" in code:
                    continue
                if '"meaning":' in code or '"description":' in code or code.strip().startswith('"meaning"') or code.strip().startswith('"description"'):
                    continue
                for name in POLICY_NAMES:
                    if re.search(rf"\b{name}\b", code):
                        offenders.append(f"{src.name}:{lineno} → {name}")
        assert not offenders, (
            "vault-specific folder names leaked into engine code:\n  "
            + "\n  ".join(offenders)
        )

    def test_engine_hardcodes_no_field_names(self):
        """type/kind/status/tags/created are Davide's schema, not the engine's."""
        offenders = []
        for src in ENGINE_DIR.glob("*.py"):
            for lineno, line in enumerate(src.read_text().splitlines(), 1):
                code = line.split("#")[0]
                # A quoted literal equal to a core field name inside engine logic
                # is hardcoded policy. Ignore the JSON-schema `"description":`
                # keys (they are tool docs, not field logic) and docstring
                # prose, which the `#`-strip above does not catch (it is inside
                # the string, not a trailing comment).
                if code.strip().startswith('"description"'):
                    continue
                for m in re.finditer(r"""["'](type|kind|status|created)["']""", code):
                    if "get(" in code or "==" in code or "in (" in code:
                        offenders.append(f"{src.name}:{lineno} → {m.group(1)}")
        assert not offenders, (
            "field names hardcoded in engine code (should come from config):\n  "
            + "\n  ".join(offenders)
        )


class TestArbitraryVaultLayout:
    """A completely different vault shape must work with zero code change."""

    @pytest.fixture
    def para_vault(self, tmp_path: Path) -> Path:
        """PARA method: Projects / Areas / Resources / Archive, different fields."""
        def w(rel: str, text: str):
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text.lstrip(), encoding="utf-8")

        w(".vault/config.yaml", """
fields:
  category:
    required: true
    vocabulary: true
    allowed: [project, area, resource, archive]
  format:
    required: true
    multi: true
    vocabulary: true
    allowed: [meeting, checklist]
  owner:
    required: true
paths:
  state: Archive/_state
tags:
  mode: closed
validation:
  fields: advisory
""")
        w("Projects/.vault/config.yaml", """
fields:
  format: { allowed: [brief, retro] }
  due: { required: true, format: date }
""")
        w("Projects/launch.md", """
---
category: project
format: [brief, kanban]
owner: davide
due: 2026-09-01
tags: [launch]
---
Body.
""")
        return tmp_path

    def test_inheritance_works_with_foreign_field_names(self, para_vault):
        cfg = resolve_config(para_vault, para_vault / "Projects")
        assert set(cfg.required_fields) == {"category", "format", "owner", "due"}
        assert "brief" in cfg.allowed_values("format")     # child
        assert "meeting" in cfg.allowed_values("format")   # root, unioned

    def test_vocabulary_follows_the_flag_not_a_name(self, para_vault):
        ctx = build_context(para_vault, "Projects")
        fields = ctx["schema"]["fields"]

        # flagged fields get declared/observed
        assert "declared" in fields["category"] or "observed" in fields["category"]
        assert "kanban (1)" in fields["format"]["observed"]   # unregistered value

        # unflagged field gets no vocabulary treatment
        assert "observed" not in fields["owner"]

    def test_state_path_comes_from_config(self, para_vault):
        cfg = resolve_config(para_vault, para_vault)
        assert cfg.state_path() == "Archive/_state"

    def test_no_state_path_configured_defaults_to_root_STATE(self, vault):
        # A vault that configures no explicit state path still gets a trail —
        # the manager (P4) depends on it. Default is root-level `.state/`.
        assert resolve_config(vault, vault).state_path() == ".state"

    def test_tag_mode_and_validation_are_per_vault(self, para_vault):
        cfg = resolve_config(para_vault, para_vault / "Projects")
        assert cfg.tag_mode() == "closed"
        assert cfg.validation_mode("fields") == "advisory"

    def test_context_call_works_end_to_end(self, para_vault):
        ctx = build_context(para_vault, "Projects")
        assert ctx["note_count"] == 1
        assert "category: <category>" in ctx["template"]
        assert "due: <YYYY-MM-DD>" in ctx["template"]
