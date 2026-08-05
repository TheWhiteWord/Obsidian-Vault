"""Engine configuration reference.

The single source of truth for *what options the engine understands*. Generated
from this module, not written by hand, so documentation cannot drift from the
code (principle 1 — derive, don't declare).

Why this exists: a fresh user, or an AI setup-assistant bootstrapping a new
vault, must be able to discover capabilities like `summary_field` without
reading the plugin source. The engine describes itself; setup tooling reads
this.
"""

from __future__ import annotations

from typing import Dict, List

# (key, where, default, meaning) — "where" is the config file it lives in.
CONFIG_OPTIONS: List[Dict[str, str]] = [
    {
        "key": "summary_field",
        "where": ".vault/config.yaml (root or any folder)",
        "default": "(none)",
        "meaning": (
            "Name of the frontmatter field used as each note's one-line summary. "
            "When set, INDEX files render the value so agents can triage notes "
            "without opening them. The field name is yours; the engine only "
            "knows 'there is a summary field'. Recommended: set it to "
            "'description' and add that field as advisory in `fields`."
        ),
    },
    {
        "key": "fields.<name>.vocabulary",
        "where": ".vault/config.yaml → fields",
        "default": "false",
        "meaning": (
            "Mark a field as vocabulary-carrying. Its values become a controlled "
            "set with declared/observed/unknown states (§3.7). Unknown values are "
            "recorded as 'observed', not rejected."
        ),
    },
    {
        "key": "paths.state",
        "where": ".vault/config.yaml (root)",
        "default": "(none)",
        "meaning": (
            "Vault-relative folder for machine-written state (audit log, graph). "
            "Omit it and the engine keeps no state — logging is opt-in and the "
            "engine never creates folders in your vault unasked."
        ),
    },
    {
        "key": "conventions.skill",
        "where": ".vault/config.yaml (root)",
        "default": "plugin:obsidian-vault",
        "meaning": (
            "Skill owning this vault's writing conventions; obsidian_context "
            "returns it as `conventions_ref` (pointer, never content). "
            "Default: the plugin's bundled skill."
        ),
    },
    {
        "key": "value_overrides",
        "where": ".vault/config.yaml",
        "default": "(none)",
        "meaning": (
            "Per-class allowed-value override: {field, by, map}. Shorthand "
            "'status_overrides: {issue: [...]}' expands to this. Keeps the engine "
            "free of field names (principle 7)."
        ),
    },
]

ROLES_OPTIONS: List[Dict[str, str]] = [
    {"key": "read", "meaning": "Read notes, query context."},
    {"key": "write", "meaning": "Create, edit, delete notes and folders."},
    {"key": "append", "meaning": "Create only — never edit or delete. Escalation: raising ledger issues requires no grant beyond registration."},
    {"key": "meta", "meaning": "Edit frontmatter, links, tags — never body prose."},
    {"key": "config", "meaning": "Extend vocabulary sections of config. Never grants or field definitions."},
]


def describe() -> Dict[str, List[Dict[str, str]]]:
    """Return the engine's configuration vocabulary as data."""
    return {"config_options": CONFIG_OPTIONS, "grant_kinds": ROLES_OPTIONS}
