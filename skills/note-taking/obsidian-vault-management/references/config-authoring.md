# Config authoring

How `.vault/config.yaml` files work — alone and together — and what each
statement does once the engine digests it. Load before writing or editing
any config, and before asking `obsidian_edit_config` to change one.
The authoritative option list lives in `obsidian_reference`; this file
explains the semantics.

## 1. Files and inheritance

A `.vault/config.yaml` may sit at **any depth**. The effective config for a
folder is the merge of every config from the vault root down to that folder
(`resolve_config`). A child never starts from zero — it *adjusts* what it
inherits.

- `obsidian_context(folder)` shows the **resolved** result — always check it
  before proposing changes, so you only delta against what actually exists.
- Merge rules below are per-key; a child can constrain or extend values but
  never rename a field, remove one, or change its meaning (uniformity
  contract — violations raise `ConfigError` at load).

## 2. Top-level keys

| Key | What it does |
|---|---|
| `fields` | The schema: per-field definitions (below). |
| `defaults` | Frontmatter defaults applied on write (e.g. `status: draft`, `created: "@today"`). `@today` is substituted with today's date. |
| `tags` | `mode`: `open` (any tag) / `suggest` (warn on new) / `closed` (block non-canonical). |
| `validation` | `fields: blocking` (default) / `advisory`; `tags: advisory` (default) / `blocking`. |
| `vocabulary` | Promotion threshold (`promote_after_uses`): observed → declared. |
| `paths` | Relocate machine state (default: vault-root `.state/`). |
| `summary_field` | Which field INDEX renders as the one-line summary (e.g. `description`). |
| `scopes` | Reserved — merged but unused (deferred design). |
| `status_overrides` / `value_overrides` | Per-class allowed-value maps (generalised: `{field, by, map}`). |

`roles.yaml` is a separate sibling file — grants only, no field schema. It is
changed by the growth protocol, never by hand.

## 3. Per-field keys and their merge rules

```yaml
fields:
  type:
    required: true
    vocabulary: true        # declared/observed lifecycle applies
    allowed: [note, index]  # union with parent
    # allowed_only: [note]  # REPLACES parent's list — restriction
  kind:
    required: true
    multi: true             # list value (tags, kinds)
    format: date            # immutable once set by any ancestor
```

| Key | Merge behaviour | Effect on the vault |
|---|---|---|
| `allowed` | **union** — child adds to the inherited list (order-preserving, deduped) | broadens what passes validation |
| `allowed_only` | **replace** — child's list *is* the vocabulary; marks `restricted` | narrows the field to exactly these values (e.g. `allowed_only: [knowledge]`) |
| `required` | **relaxable** — nearest declaration wins: a child may add a requirement or drop an inherited one (P7.2) | makes a field mandatory for future notes |
| `multi` / `format` | **immutable** once any ancestor sets them (uniformity contract) | shape of the value cannot drift down the tree |
| `vocabulary: true` | flag | the field participates in declared/observed/unused tracking |

`allowed` and `allowed_only` are mutually exclusive per field block; both
target the same `allowed` slot in the resolved config.

## 4. What a statement does once digested — implications map

| Engine surface | Effect of a config statement |
|---|---|
| `obsidian_write` | `fields` + `validation.fields: blocking` refuse non-conforming notes with structured errors + `did_you_mean`; `required` gates the write; `defaults` pre-fill frontmatter |
| `obsidian_context` | returns the **resolved** schema, vocabulary, tags, your grants for the folder — the ground truth you write against |
| `obsidian_search` / `obsidian_graph` | vocabulary field values are searchable (frontmatter surface); config never widens what you can read — grants bound results |
| INDEX / registry | `summary_field` surfaces as the one-line note summary; vocabulary fields drive the tag cloud; malformed notes are flagged |
| `obsidian_maintain` | observed values past `promote_after_uses` become declared (config grant, AUTO); unused declared values are flagged |
| `tags.mode` / `validation.tags` | open/suggest/closed gates how strict tag checks are at write time |

**Search and creation are affected, never silently.** Every statement you
write changes what *validates* and what *surfaces*; it cannot change what an
agent can *read* (that is grants, deny-by-default).

## 5. May / must not

**May** (with the right grant):
- `obsidian_scaffold` — new folder + config delta (write grant; structural keys need user confirmation).
- `obsidian_edit_config` — edit an existing config (config grant; structural keys need user confirmation).
- `obsidian_reference` — self-documented options; `obsidian_context` — resolved view. Always check these first.

**Must not:**
- Hand-edit raw YAML config files — the tools exist precisely to keep config engine-digestible and audit-trailed.
- Drop an inherited `required`, redefine `format`/`multi`, or remove a field — `ConfigError` and refused.
- Hand-edit `roles.yaml` — your config grant never covers it; the growth protocol changes it.
- Write an issue as a note, or a note where the schema says otherwise (type/kind are enforced).

## 6. Anchor examples (from the starter)

**Root config** — broad, everything allowed; the base schema every tree adjusts:

```yaml
fields:
  type:    {required: true, vocabulary: true, allowed: [index, note]}
  kind:    {required: true, multi: true, vocabulary: true,
            allowed: [note, index, reference]}
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

**The shared `*/knowledge` schema** — restrictive; the inheritance proving
case (`allowed_only` replaces, `required` relaxes):

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

## 7. Field patterns per domain type

Common starter shapes to seed a suggestion (adapt, never copy blindly):

| Domain | Pattern |
|---|---|
| knowledge | `type.allowed_only: [knowledge]` + `source`/`retrieved` required + `confidence` |
| recipe / how-to | `type.allowed_only: [recipe]` (or per-domain value) + `source` required + `retrieved` |
| project | `status` lifecycle values + `owner`/`due` advisory fields |
| reference shelf | `kind: [reference]` default + `source` required |

When proposing fields for a new subdomain, resolve the parent first
(`obsidian_context`), then propose only the delta — `obsidian_scaffold` /
`obsidian_edit_config` will compute exactly that.
