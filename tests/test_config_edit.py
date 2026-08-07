"""Tests for obsidian_edit_config (P5b) — the config-gated sibling of scaffold.

Covers: propose-only vs confirm, structural confirmation, vocabulary without
confirmation, grants (config kind), roles.yaml/non-config/missing refusals,
uniformity contract (inherited required, format/multi immutability), audit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vault.scaffold import ScaffoldRefused, edit_config
from vault.paths import VaultPathError
from vault.grants import PermissionDenied


@pytest.fixture
def loaded(vault_with_roles, roles):
    return vault_with_roles, roles


def _propose(root, roles, path, proposed, agent="tww", confirm=False):
    # P7: config edits inside an owned scope are the owner's — tww owns
    # CREATIVE in the fixture; the manager's config authority is root-level.
    return edit_config(root, agent, roles, path, proposed=proposed,
                       confirm=confirm)


# --- propose vs apply ------------------------------------------------------

def test_propose_only_returns_delta_and_writes_nothing(loaded):
    root, roles = loaded
    cfg = root / "CREATIVE/.vault/config.yaml"
    before = cfg.read_text(encoding="utf-8")

    out = _propose(root, roles, "CREATIVE/.vault/config.yaml",
                   {"fields": {"type": {"allowed": ["recipe"]}}})

    assert out["proposal"] is True
    assert out["delta"]["fields"]["type"]["allowed"] == ["recipe"]
    assert cfg.read_text(encoding="utf-8") == before  # untouched


def test_apply_writes_delta(loaded):
    root, roles = loaded
    cfg = root / "CREATIVE/.vault/config.yaml"
    before = cfg.read_text(encoding="utf-8")

    out = _propose(root, roles, "CREATIVE/.vault/config.yaml",
                   {"fields": {"type": {"allowed": ["recipe"]}},
                    "user_confirmed": True},
                   confirm=True)
    assert out["ok"] is True and out["changed"] is True
    after = cfg.read_text(encoding="utf-8")
    assert after != before
    assert "recipe" in after


# --- confirmation semantics (mirrors scaffold: any fields delta is
# structural; defaults/tags flow freely) ------------------------------------

def test_fields_change_needs_user_confirmation(loaded):
    root, roles = loaded
    out = _propose(root, roles, "CREATIVE/.vault/config.yaml",
                   {"fields": {"type": {"allowed": ["recipe"]}}})
    assert out["requires_user_confirmation"] is True

    with pytest.raises(ScaffoldRefused):
        _propose(root, roles, "CREATIVE/.vault/config.yaml",
                 {"fields": {"type": {"allowed": ["recipe"]}}},
                 confirm=True)  # no user_confirmed


def test_defaults_flow_without_confirmation(loaded):
    """Non-fields sections (defaults, tags) are not structural — they apply
    without user_confirmed, mirroring scaffold's STRUCTURAL_KEYS."""
    root, roles = loaded
    out = _propose(root, roles, "CREATIVE/.vault/config.yaml",
                   {"defaults": {"status": "active"}})
    assert out["requires_user_confirmation"] is False

    out = _propose(root, roles, "CREATIVE/.vault/config.yaml",
                   {"defaults": {"status": "active"}}, confirm=True)
    assert out["ok"] is True and out["changed"] is True
    assert "status: active" in (root / "CREATIVE/.vault/config.yaml").read_text()


def test_fields_change_applies_with_user_confirmed(loaded):
    root, roles = loaded
    out = _propose(root, roles, "CREATIVE/.vault/config.yaml",
                   {"fields": {"source": {"required": True}},
                    "user_confirmed": True},
                   confirm=True)
    assert out["ok"] is True and out["changed"] is True
    assert "required: true" in (root / "CREATIVE/.vault/config.yaml").read_text()


# --- grants (config kind) ----------------------------------------------------

def test_manager_cannot_edit_owned_config(loaded):
    """P7: config resolves for the derived owner — the
    manager's config ** no longer reaches inside an owned scope."""
    root, roles = loaded
    with pytest.raises(PermissionDenied, match="scope is owned by system"):
        _propose(root, roles, "SYSTEM/.vault/config.yaml",
                 {"fields": {"kind": {"allowed": ["api-reference"]}}},
                 agent="vault_manager", confirm=True)


def test_manager_can_edit_root_config(loaded):
    """The root config is unowned — the manager's config ** applies there."""
    root, roles = loaded
    out = _propose(root, roles, ".vault/config.yaml",
                   {"fields": {"kind": {"allowed": ["api-reference"]}},
                    "user_confirmed": True},
                   agent="vault_manager", confirm=True)
    assert out["ok"] is True


def test_contributor_without_config_denied(loaded):
    root, roles = loaded
    # `system` (agent) holds write/read/append, no config → denied.
    with pytest.raises(PermissionDenied, match="requires 'config'"):
        _propose(root, roles, "SYSTEM/.vault/config.yaml",
                 {"fields": {"kind": {"allowed": ["x"]}}},
                 agent="system")


def test_agent_with_config_on_own_tree_allowed(loaded):
    """D-5/P7: a domain owner holding config on its own tree can edit it."""
    root, roles = loaded
    # `tww` owns CREATIVE and holds config on it — the D-5 shape.
    out = _propose(root, roles, "CREATIVE/.vault/config.yaml",
                   {"fields": {"type": {"allowed": ["recipe"]}},
                    "user_confirmed": True},
                   agent="tww", confirm=True)
    assert out["ok"] is True


# --- refusals ----------------------------------------------------------------

def test_roles_yaml_never_editable(loaded):
    root, roles = loaded
    with pytest.raises(VaultPathError):
        _propose(root, roles, ".vault/roles.yaml",
                 {"fields": {"type": {"allowed": ["x"]}}})


def test_non_config_target_refused(loaded):
    root, roles = loaded
    with pytest.raises(VaultPathError):
        _propose(root, roles, "CREATIVE/PHILOSOPHY/recurrence.md",
                 {"fields": {"type": {"allowed": ["x"]}}})


def test_missing_config_refused(loaded):
    root, roles = loaded
    with pytest.raises(ScaffoldRefused):
        _propose(root, roles, "CREATIVE/NEW/.vault/config.yaml",
                 {"fields": {"type": {"allowed": ["x"]}}})


# --- uniformity contract ------------------------------------------------------

def _child_of_knowledge(root) -> str:
    """A config UNDER the KNOWLEDGE schema: it inherits `source: required`
    and `retrieved: format: date` from the leaf config above it."""
    cfg = root / "CREATIVE/KNOWLEDGE/DEEP/.vault/config.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("fields:\n  type: { allowed: [deep] }\n", encoding="utf-8")
    return "CREATIVE/KNOWLEDGE/DEEP/.vault/config.yaml"


def test_dropping_inherited_required_is_a_relax(loaded):
    """P7: a child of KNOWLEDGE may drop the inherited
    `source: required` — nearest declaration wins; the parent is
    unaffected."""
    root, roles = loaded
    rel = _child_of_knowledge(root)
    out = _propose(root, roles, rel,
                   {"fields": {"source": {"required": False}},
                    "user_confirmed": True},
                   confirm=True)
    assert out["ok"] is True and out["changed"] is True
    text = (root / "CREATIVE/KNOWLEDGE/DEEP/.vault/config.yaml").read_text()
    assert "required: false" in text


def test_redefining_inherited_format_refused(loaded):
    """A child of KNOWLEDGE inherits `retrieved: format: date`; redefining
    it is refused (format is an immutable field key)."""
    root, roles = loaded
    rel = _child_of_knowledge(root)
    with pytest.raises(ScaffoldRefused):
        _propose(root, roles, rel,
                 {"fields": {"retrieved": {"format": "text"}},
                  "user_confirmed": True},
                 confirm=True)


def test_allowed_only_replace_semantics(loaded):
    """allowed_only replaces the vocabulary (not a union)."""
    root, roles = loaded
    out = _propose(root, roles, "CREATIVE/KNOWLEDGE/.vault/config.yaml",
                   {"fields": {"type": {"allowed_only": ["knowledge", "recipe"]}},
                    "user_confirmed": True},
                   confirm=True)
    assert out["ok"] is True
    text = (root / "CREATIVE/KNOWLEDGE/.vault/config.yaml").read_text()
    assert "allowed_only" in text and "recipe" in text


def test_allowed_union_semantics(loaded):
    """allowed unions with existing values (never drops)."""
    root, roles = loaded
    out = _propose(root, roles, "CREATIVE/.vault/config.yaml",
                   {"fields": {"type": {"allowed": ["recipe"]}},
                    "user_confirmed": True},
                   confirm=True)
    assert out["ok"] is True
    text = (root / "CREATIVE/.vault/config.yaml").read_text()
    assert "recipe" in text
    # existing value from the base config still present in resolved view
    from vault.config import resolve_config
    cfg = resolve_config(root, root / "CREATIVE")
    assert "work" in cfg.allowed_values("type")
    assert "recipe" in cfg.allowed_values("type")


# --- audit -------------------------------------------------------------------

def test_edit_config_is_audited(loaded):
    root, roles = loaded
    _propose(root, roles, "CREATIVE/.vault/config.yaml",
             {"fields": {"type": {"allowed": ["recipe"]}},
              "user_confirmed": True},
             confirm=True)
    entries = []
    log = root / ".state/audit-log.jsonl"
    for line in log.read_text(encoding="utf-8").splitlines():
        entries.append(json.loads(line))
    assert any(e["action"] == "edit_config" for e in entries)
