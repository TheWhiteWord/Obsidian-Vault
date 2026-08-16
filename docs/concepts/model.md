# The vault data model

Everything the plugin does follows one split: **mechanism in code,
policy in config**. The engine is a general vault engine — it reads
trees, fields, vocabularies, and grants from the vault's `.vault/`
configs at runtime. This page describes that model: how configs merge,
how fields and vocabularies behave, and which artifacts are derived
rather than authored.

## Derive, don't declare

Anything computable from the notes is **computed**, never
hand-maintained. INDEX files, the config registry, the wikilink graph,
and tag lists are all derived from the live vault — a generated file
carries a `<!-- generated: do not edit -->` marker and is overwritten
without warning. This is what makes the derived layer unable to drift:
a hand-maintained TAXONOMY goes stale the moment someone writes a note
without updating it; a file that regenerates cannot.

## Configuration discovery & inheritance

A `.vault/config.yaml` may sit at **any depth**. The effective config
for a folder is the merge of every config from the vault root down to
that folder (`resolve_config`). A child never starts from zero — it
*adjusts* what it inherits.

| Key | Merge behaviour |
|---|---|
| `fields.*.allowed` | **union** — child extends the parent's vocabulary (order-preserving, deduped) |
| `fields.*.allowed_only` | **replace** — child's list *is* the vocabulary; marks the field `restricted` |
| `defaults` | child overrides key-by-key |
| `fields.*.required` | **nearest declaration wins** — a child may add a requirement or drop an inherited one |
| `fields.*.multi` / `format` | child wins, but **redefining them is a `ConfigError`** (uniformity contract) |
| `tags.mode` | child overrides wholly |

`allowed` and `allowed_only` are mutually exclusive per field block —
both target the same resolved `allowed` slot. A folder with no config
is the default state, not an omission: it simply inherits everything.

## Fields & the uniformity contract

The five core fields are identical everywhere in the vault:

| Field | Answers | Format |
|---|---|---|
| `type` | What class of note, within its tree? | one enum value |
| `kind` | What is its nature / genre / form? | one or more controlled values |
| `status` | Where is it in its lifecycle? | one lifecycle value |
| `tags` | What is it about? | list, topic vocabulary |
| `created` | When was it conceived? | `YYYY-MM-DD` |

Children may constrain or extend the **allowed values** of a field and
may add extra fields beyond the five. They may never rename a field,
remove one, or change its meaning or format — `format` and `multi` are
immutable once any ancestor sets them. This is the **uniformity
contract**, and it is what makes `status: active` mean one thing
vault-wide.

## Vocabulary lifecycle

A field carries a controlled vocabulary when `fields.<name>.vocabulary:
true` is set — it is the *flag*, never the field name, that the engine
knows. Values then have three states:

| State | Meaning | On write |
|---|---|---|
| **declared** | present in some config's `allowed` | accepted silently |
| **observed** | in use in notes, in no config | accepted, flagged as unregistered |
| **unknown** | neither | refused, with declared + observed options offered |

Registering a new value — `obsidian_write(..., register={"kind":
"aphorism"})` — requires the `config` grant and enters the value as
**observed**, not declared: promotion is a separate act. Promotion
(observed → declared) happens in the maintenance sweep once a value
passes `vocabulary.promote_after_uses` (default 3), and also requires
the `config` grant.

`value_overrides` provides per-class allowed-value overrides
(`{field, by, map}`); the shorthand `status_overrides` (e.g.
`{decision: [proposed, adopted, rejected]}`) expands to it
automatically.

Why the lifecycle exists: `obsidian_context` returns the live
vocabulary for a folder with `declared` and `observed` distinguished,
so an agent writing a note reuses settled terms instead of inventing
near-duplicates. An agent that can see `essay` will not invent
`essai` — the same goal v1's hand-maintained taxonomy was attempting,
delivered at the point of decision instead of as a prerequisite read.

## Tags

Tags are **never declared in a file** — the tag vocabulary for a
folder is computed from the frontmatter of notes in scope, so it
cannot drift. Per-folder mode:

| Mode | Behaviour |
|---|---|
| `open` | any tag accepted; list derived from usage |
| `suggest` (default) | derived + near-duplicate warning at write time (`#Project` → "did you mean `project`?") |
| `closed` | only tags in `allowed:` accepted; anything else refused |

Near-duplicate detection is deterministic — case-folding,
singular/plural, trigram similarity. No embeddings anywhere; the
deterministic signal is what makes tag consolidation unnecessary: it is
prevented at write, not repaired after.

## Validation

Two severities, per config:

- `validation.fields: blocking` (default) — a missing or invalid
  required field **refuses the write**, with the specific problems
  listed (and `did_you_mean` suggestions).
- `validation.fields: advisory` — the write proceeds with warnings.
- `validation.tags: advisory` (default) — near-duplicate tags warn,
  the write proceeds.

## Generated vs authored

| Artifact | Author | Notes |
|---|---|---|
| Note bodies | agents / the human | the actual content |
| `.vault/*.yaml` | the human (via tools) | the only hand-written config |
| `INDEX.md` (any folder) | **generated** | regenerated on every content write; never hand-edited |
| the registry | **generated** | human-readable view of the merged configs |
| `.state/audit-log.jsonl` | **engine** | append-only JSONL, created on first write |

An INDEX records only what is *in its own folder*: its immediate notes
(under `## Notes`, each with its `summary_field` one-liner), and under
`## Folders` a pointer to each immediate subfolder, expanded one level to
show that subfolder's own direct notes and subfolders. It does not recurse
— descent through the tree happens by following a child's INDEX — so a note
appears in exactly one INDEX (its own folder's), never duplicated into every
ancestor. Notes shown under `## Folders` carry their `· *type* — summary`
suffix; subfolders render as plain links.

`summary_field` is a config key naming the frontmatter field whose
value INDEX renders as each note's one-line summary, so notes are
triageable without opening them. Advisory, never required — the field
name is policy (e.g. `description`); only the `summary_field` key is
engine.

## Machinery folders

`.vault` (config discovery) and `.state` (audit ledger, issue ledger,
protocol registry, maintenance checkpoints) are **engine machinery**:
both are in `SKIP_DIRS`, so note-walks, INDEX generation, search, and
the graph never enter them. No content-derived INDEX is ever written
into a machinery folder.

The state directory defaults to the vault root's `.state/` and is
created on first use — the installer never scaffolds it. It is
relocatable via `paths.state` but never optional: the audit trail and
the issue ledger depend on it, and the manager reads them.

## Case-insensitive path semantics

Paths are matched **case-insensitively but written with the real
on-disk case**. Grant globs, ownership globs, and query scopes match
casefolded;
`safe_join` case-corrects every path to the real on-disk name (so a
case-only rename never creates a second copy of a tree);
`obsidian_maintain` flags sibling folders that differ only by case as a
`case_collision`. The invariant: input case-insensitive, output
real-case, never two copies of a tree.
