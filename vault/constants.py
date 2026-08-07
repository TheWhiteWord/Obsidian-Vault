"""Shared constants.

**Mechanism only.** Nothing here may name a tree, folder, or field belonging
to a particular vault — those are *policy* and live in ``.vault/config.yaml``.
The engine works on any vault layout; ``tests/test_portability.py`` enforces
this so it cannot regress.
"""

from __future__ import annotations

# -- config discovery -------------------------------------------------------
CONFIG_DIRNAME = ".vault"
CONFIG_FILENAME = "config.yaml"
ROLES_FILENAME = "roles.yaml"

# -- engine-reserved folders -------------------------------------------------
#: The machine-written state ledger (audit trail +, later, the manager pass).
#: Engine-reserved, like CONFIG_DIRNAME — not a vault content tree. Dot-prefixed
#: so it reads as machinery, not a content tree. Default location is a vault-root
#: `.state/`; a vault may relocate it via `paths.state`; only the concept is owned.
STATE_DIRNAME = ".state"

# -- schema mechanics -------------------------------------------
#: Keys inside a field definition a child may not change once a parent sets
#: them — the structural half of the uniformity contract. Which *fields* exist
#: is policy; that a field's shape is fixed vault-wide is mechanism.
IMMUTABLE_FIELD_KEYS = ("format", "multi")

#: Marks a field as carrying a controlled vocabulary with declared/observed
#: states. Set per-field in config: ``kind: { vocabulary: true }``.
VOCABULARY_FLAG = "vocabulary"

# -- traversal --------------------------------------------------------------
#: Never walked when scanning notes. Tool/VCS dirs only — no vault content.
#: `.state` is included: it is engine machinery (the audit ledger), not a
#: content tree, so it must never produce a derived INDEX of itself.
SKIP_DIRS = frozenset({".obsidian", ".vault", ".state", ".git", ".trash", "node_modules"})

MARKDOWN_SUFFIX = ".md"

# -- defaults -----------------------------------------------
DEFAULT_TAG_MODE = "suggest"          # open | suggest | closed
DEFAULT_FIELD_VALIDATION = "blocking"
DEFAULT_TAG_VALIDATION = "advisory"

#: Token substituted with today's date when it appears in ``defaults``.
TODAY_TOKEN = "@today"

# -- generated artifacts ------------------------------------------
GENERATED_MARKER = "<!-- generated: do not edit -->"

#: Config key under ``paths:`` naming where machine-written state lives.
#: The *value* is the user's choice; only the key name is fixed.
STATE_PATH_KEY = "state"

#: Sub-directory of the state dir holding the issue ledger.
#: Issues are *records*, not notes — engine machinery like the audit trail.
#: The name is engine-reserved (mechanism); a vault may relocate the whole
#: state dir via ``paths.state``, but the ledger's home within it is fixed.
ISSUES_DIRNAME = "issues"

#: Sub-directory of the state dir holding the protocol registry.
#: Handoffs are *structured records with parties*, not notes — engine
#: machinery like the issue ledger. Same residency rule: fixed within the
#: state dir, which itself may be relocated via ``paths.state``.
PROTOCOLS_DIRNAME = "protocols"

#: Filename of the per-scope conventions file inside `.vault/` (P7). Scope
#: directives are policy prose — engine-reserved like config.yaml; only the
#: concept is owned, the content is the scope owner's.
CONVENTIONS_FILENAME = "conventions.md"

#: Config key (engine concept) for the designated summary field. The *name*
#: of the field is policy; the key in config is mechanism (principle 7).
SUMMARY_FIELD_KEY = "summary_field"
