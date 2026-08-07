"""Test fixtures — a synthetic vault mirroring the shipped preset shapes.

Built in a tmp dir so tests never touch the real vault.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT_CONFIG = """
fields:
  type:    { required: true, vocabulary: true, allowed: [index, note] }
  kind:    { required: true, multi: true, vocabulary: true, allowed: [note, index, reference, issue] }
  status:  { required: true, allowed: [draft, active, paused, completed, reference] }
  tags:    { required: true, multi: true }
  created: { required: true, format: date }
defaults:
  status: draft
  created: "@today"
tags:
  mode: suggest
validation:
  fields: blocking
  tags: advisory
status_overrides:
  issue: [open, in-progress, resolved]
  decision: [proposed, adopted, rejected]
"""

SYSTEM_CONFIG = """
fields:
  type: { allowed: [spec, record, knowledge] }
  kind: { allowed: [spec, log, decision, api-reference] }
"""

CREATIVE_CONFIG = """
fields:
  type: { allowed: [work, idea, project, knowledge] }
  kind: { allowed: [concept, essay, poem, script] }
"""

# the KNOWLEDGE config is byte-identical in both domains
KNOWLEDGE_CONFIG = """
fields:
  type:       { allowed_only: [knowledge] }
  source:     { required: true }
  retrieved:  { required: true, format: date }
  confidence: { allowed: [high, medium, low] }
defaults:
  status: reference
  kind: [reference]
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip(), encoding="utf-8")


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """A minimal vault exercising root → tree → leaf inheritance."""
    _write(tmp_path / ".vault/config.yaml", ROOT_CONFIG)
    _write(tmp_path / "SYSTEM/.vault/config.yaml", SYSTEM_CONFIG)
    _write(tmp_path / "CREATIVE/.vault/config.yaml", CREATIVE_CONFIG)
    _write(tmp_path / "SYSTEM/KNOWLEDGE/.vault/config.yaml", KNOWLEDGE_CONFIG)
    _write(tmp_path / "CREATIVE/KNOWLEDGE/.vault/config.yaml", KNOWLEDGE_CONFIG)

    _write(tmp_path / "CREATIVE/PHILOSOPHY/recurrence.md", """
---
type: work
kind: [concept, essay]
status: draft
tags: [nietzsche, time]
created: 2026-08-02
---
Links to [[kant-on-time]] and `[[not-a-link]]` in code.
""")

    _write(tmp_path / "CREATIVE/PHILOSOPHY/aphorism.md", """
---
type: work
kind: [aphorism]
status: draft
tags: [form, nietzsche]
created: 2026-08-02
---
An unregistered kind — exercises the observed state.
""")

    _write(tmp_path / "CREATIVE/KNOWLEDGE/kant-on-time.md", """
---
type: knowledge
kind: [reference]
status: reference
tags: [kant, time]
created: 2026-08-02
source: https://plato.stanford.edu/
retrieved: 2026-08-02
confidence: high
---
Body.
""")

    return tmp_path


ROLES_YAML = """
agents:
  system:
    write:  ["SYSTEM/**"]
    read:   ["**"]
    append: ["*/ISSUES/**"]

  tww:
    write:  ["CREATIVE/**"]
    config: ["CREATIVE/**"]   # D-5/P7: the domain owner evolves its own config
    read:   ["CREATIVE/**", "*/KNOWLEDGE/**"]
    append: ["*/ISSUES/**"]

  vault_manager:
    meta:   ["**"]
    write:  [".state/**"]
    config: ["**"]
    append: ["*/ISSUES/**"]
    read:   ["**"]
"""


@pytest.fixture
def para_vault_no_state(tmp_path: Path) -> Path:
    """A vault that configures no state path — audit must stay silent."""
    _write(tmp_path / ".vault/config.yaml",
           "fields:\n  title: { required: true }\n")
    return tmp_path


@pytest.fixture
def vault_with_roles(vault: Path) -> Path:
    """The same vault plus roles.yaml and the folders grants refer to."""
    _write(vault / ".vault/roles.yaml", ROLES_YAML)
    # This vault opts into a state dir so audit tests have somewhere to write.
    # (The engine now defaults to root STATE/, so this is belt-and-braces.)
    _write(vault / ".vault/config.yaml",
           (vault / ".vault/config.yaml").read_text() + "\npaths:\n  state: .state\n")

    for folder in ("SYSTEM/ISSUES", "CREATIVE/ISSUES", ".state"):
        (vault / folder).mkdir(parents=True, exist_ok=True)

    _write(vault / "SYSTEM/HANDBOOK/design.md", """
---
type: spec
kind: [spec]
status: draft
tags: [design]
created: 2026-08-02
---
Design body.
""")
    return vault


@pytest.fixture
def roles(vault_with_roles):
    from vault.grants import load_roles
    return load_roles(vault_with_roles)
