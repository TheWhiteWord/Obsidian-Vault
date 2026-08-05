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
        "key": "fields.<name>.required",
        "where": ".vault/config.yaml → fields.<name>",
        "default": "false",
        "meaning": (
            "The field is mandatory for every note in the folder: a write "
            "missing it is refused with suggestions. Children accumulate — "
            "a required field can never be dropped down the tree."
        ),
    },
    {
        "key": "fields.<name>.allowed / allowed_only",
        "where": ".vault/config.yaml → fields.<name>",
        "default": "(none)",
        "meaning": (
            "The controlled vocabulary for a field. `allowed` unions with "
            "the parent's list; `allowed_only` replaces it and marks the "
            "field restricted. Mutually exclusive per field block."
        ),
    },
    {
        "key": "fields.<name>.multi / format",
        "where": ".vault/config.yaml → fields.<name>",
        "default": "false / (none)",
        "meaning": (
            "`multi` makes the field a list; `format` constrains the value "
            "shape (e.g. date). Both are immutable once any ancestor sets "
            "them (uniformity contract)."
        ),
    },
    {
        "key": "defaults",
        "where": ".vault/config.yaml (any folder)",
        "default": "(none)",
        "meaning": (
            "Frontmatter defaults applied on write. `@today` is substituted "
            "with today's date; children override per key."
        ),
    },
    {
        "key": "tags.mode",
        "where": ".vault/config.yaml (any folder)",
        "default": "suggest",
        "meaning": (
            "Tag gate at write time: `open` accepts any tag, `suggest` "
            "warns on new ones, `closed` blocks non-canonical tags."
        ),
    },
    {
        "key": "validation",
        "where": ".vault/config.yaml (any folder)",
        "default": "fields: blocking, tags: advisory",
        "meaning": (
            "Severity for schema violations: `blocking` refuses the write "
            "with field errors, `advisory` warns. Configurable per surface "
            "(fields / tags)."
        ),
    },
    {
        "key": "vocabulary.promote_after_uses",
        "where": ".vault/config.yaml (root)",
        "default": "3",
        "meaning": (
            "How many uses promote an observed value to declared. The "
            "maintenance sweep applies the promotion (config grant)."
        ),
    },
    {
        "key": "scopes",
        "where": ".vault/config.yaml",
        "default": "(none)",
        "meaning": (
            "Reserved — merged but unused (deferred design)."
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
