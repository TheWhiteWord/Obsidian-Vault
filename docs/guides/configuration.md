# Configuration — the `.vault/config.yaml` DSL

A vault is shaped by two policy files: `.vault/config.yaml` (schema,
vocabularies, defaults, validation) and `.vault/roles.yaml` (grants).
This page is the config-authoring reference: every key, how files
inherit and merge, and what each statement does once the engine
digests it.

The authoritative option list always lives in the engine itself —
`obsidian_reference` returns it, self-describing, so it cannot drift
from the code.

## Files and inheritance

A `.vault/config.yaml` may sit at **any depth**. The effective config
for a folder is the merge of every config from the vault root down to
that folder — a child never starts from zero, it *adjusts* what it
inherits. `obsidian_context(folder)` shows the **resolved** result, so
check it before proposing changes and delta only against what actually
exists.

Merge rules are per-key (see below); a child can constrain or extend
values but never rename a field, remove one, or change its meaning —
violations raise `ConfigError` at load. The deep mechanics live in
[concepts/model.md](../concepts/model.md); this page is the practical
reference.

## Top-level keys

| Key | What it does |
|---|---|
| `fields` | The schema: per-field definitions (below) |
| `defaults` | Frontmatter defaults applied on write (e.g. `status: draft`, `created: "@today"`); `@today` is substituted with today's date |
| `tags` | `mode`: `open` (any tag) / `suggest` (warn on new) / `closed` (block non-canonical) |
| `validation` | `fields: blocking` (default) / `advisory`; `tags: advisory` (default) / `blocking` |
| `vocabulary` | Promotion threshold (`promote_after_uses`, default 3): observed → declared |
| `paths` | Relocate machine state (default: vault-root `.state/`) |
| `summary_field` | Which field INDEX renders as the one-line summary (e.g. `description`) |
| `scopes` | Reserved — merged but unused |
| `status_overrides` / `value_overrides` | Per-class allowed-value maps (generalised: `{field, by, map}`) |
| `maintenance` | Scope exemptions for the maintenance sweep (`exempt` union / `exempt_only` replace — see below) |

`roles.yaml` is a separate sibling file — grants only, no field
schema. It is changed by the growth CLI, never by hand
([concepts/grants.md](../concepts/grants.md)).

## Per-field keys and merge rules

```yaml
fields:
  type:
    required: true
    vocabulary: true        # declared/observed lifecycle applies
    allowed: [note, index]  # union with parent
    # allowed_only: [note]  # REPLACES parent's list — restriction
  kind:
    required: true
    multi: true             # list value
  created:
    required: true
    format: date            # immutable once set by any ancestor
```

| Key | Merge behaviour | Effect on the vault |
|---|---|---|
| `allowed` | **union** — child adds to the inherited list (order-preserving, deduped) | broadens what passes validation |
| `allowed_only` | **replace** — child's list *is* the vocabulary; marks `restricted` | narrows the field to exactly these values (e.g. `allowed_only: [knowledge]`) |
| `required` | **relaxable** — nearest declaration wins: a child may add a requirement or drop an inherited one | makes a field mandatory for future notes |
| `multi` / `format` | **immutable** once any ancestor sets them (uniformity contract) | the shape of the value cannot drift down the tree |
| `vocabulary: true` | flag | the field participates in declared/observed tracking |

`allowed` and `allowed_only` are mutually exclusive per field block —
both target the same resolved `allowed` slot.

## What a statement does once digested

| Engine surface | Effect of a config statement |
|---|---|
| `obsidian_write` | `fields` + `validation.fields: blocking` refuse non-conforming notes with structured errors and `did_you_mean` suggestions; `required` gates the write; `defaults` pre-fill frontmatter |
| `obsidian_context` | returns the **resolved** schema, vocabulary, tags, and your grants for the folder — the ground truth you write against |
| `obsidian_search` / `obsidian_graph` | vocabulary field values are searchable (frontmatter surface); config never widens what you can read — grants bound results |
| INDEX / registry | `summary_field` surfaces as the one-line note summary; malformed notes are flagged |
| `obsidian_maintain` | observed values past `promote_after_uses` become declared (config grant, automatic); unused declared values are flagged |
| `tags.mode` / `validation.tags` | open/suggest/closed gates how strict tag checks are at write time |

Search and creation are affected, never silently. Every statement
changes what *validates* and what *surfaces*; it cannot change what an
agent can *read* — that is grants, deny-by-default.

## May / must not

**May** (with the right grant):

- `obsidian_scaffold` — new folder + config delta (write or append
  grant; structural keys need user confirmation).
- `obsidian_edit_config` — edit an existing config (config grant;
  structural keys need user confirmation).
- `obsidian_reference` — the self-documented options; `obsidian_context`
  — the resolved view. Always check these first.

**Must not:**

- Hand-edit raw YAML config files — the tools exist precisely to keep
  config engine-digestible and audit-trailed.
- Redefine `format`/`multi`, or remove a field — `ConfigError` and
  refused.
- Hand-edit `roles.yaml` — the config grant never covers it; the
  growth CLI changes it.

## Anchor examples (from the standard preset)

**Root config** — broad; the base schema every tree adjusts:

```yaml
fields:
  type:    {required: true, vocabulary: true, allowed: [index, note]}
  kind:    {required: true, multi: true, vocabulary: true,
            allowed: [note, index, reference]}   # issues live in the ledger, not as notes
  status:  {required: true, allowed: [draft, active, paused, completed, reference]}
  tags:    {required: true, multi: true}
  created: {required: true, format: date}
  description: {required: false}      # advisory summary field
defaults:
  status: draft
  created: "@today"
tags: {mode: suggest}
validation: {fields: blocking, tags: advisory}
paths: {state: .state}
summary_field: description
vocabulary: {promote_after_uses: 3}
```

**The shared `knowledge/` schema** — restrictive; the inheritance
proving case (`allowed_only` replaces, extra required fields):

```yaml
fields:
  type:  {allowed_only: [knowledge]}
  source:    {required: true}
  retrieved: {required: true, format: date}
  confidence:{allowed: [high, medium, low]}
defaults:
  status: reference
  kind: [reference]
```

When proposing fields for a new folder, resolve the parent first
(`obsidian_context`), then propose only the delta —
`obsidian_scaffold` / `obsidian_edit_config` compute exactly that.
