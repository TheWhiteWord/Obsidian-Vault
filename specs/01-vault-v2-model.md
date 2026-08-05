# Vault v2 — Model Specification

**Status:** draft · iterate on DESK, does not enter the vault until settled
**Supersedes:** the vault model in `obsidian-vault` skill (v1, `hermes_workspace/`)
**Companion:** `00-original-plugin-idea.md` (feature ambitions), this doc (foundation)

> **Drift corrections (2026-08-03):** the *model* below is unchanged and load-bearing;
> the *names and shipped shapes* moved. §1 tree shape and §10.3 names → starter preset
> naming (D3: `system/`, `work/<domain>/`, `knowledge/`, `issues/`; agents `default`,
> `vault-manager`, `creative`, `dev`, `researcher`). §2.2 roles example, §2.3
> researcher, §3.4 `issue`-in-kind, and §5 grants note carry inline markers below.

---

## 0. Design principles

Five rules. Everything below follows from them; if a later decision contradicts one,
the rule wins or the rule changes explicitly.

1. **Derive, don't declare.** Anything computable from the notes (tag lists, indexes,
   graph, backlinks) is *computed*, never hand-maintained. No file exists solely to
   describe what other files already contain.
2. **Scope, don't globalise.** An agent working in one folder loads that folder's
   context only. Cost of context is proportional to the task, not to vault size.
3. **Validate at write time.** Enforcement happens at the door, not in a cleanup pass.
   Maintenance repairs genuine decay; it does not compensate for missing enforcement.
4. **Mechanism over instruction.** A rule the plugin can enforce must not be prose in
   a skill. Skills hold judgement; code holds rules.
5. **Ownership is the primary boundary.** Top-level trees are write-domains, not
   content categories. Boundaries that can be enforced are worth having; boundaries
   that rely on good behaviour are not.
6. **Borrow before building.** Before writing non-trivial logic, check whether a
   library, an existing implementation, or a data shape already solves it. Prefer the
   dependency. "I could write it myself" is not a reason to. This applies to parsing,
   indexing, diffing, and anything else that looks like solved work — hand-rolled
   versions of solved problems are where the fiddly bugs live.
7. **Mechanism in code, policy in config.** The plugin is a general vault engine;
   this vault is one configuration of it. No tree name, folder name, field name, or
   vocabulary value may appear in engine code — the engine reads them from
   `.vault/config.yaml`. Enforced by `tests/test_portability.py`, which runs the whole
   engine against a deliberately foreign vault layout (PARA folders, different field
   names) and greps engine sources for leaked policy names.

   | Mechanism — code | Policy — config |
   |---|---|
   | inheritance resolution | which trees exist |
   | the uniformity contract | which fields exist |
   | declared / observed / promotion | which fields carry vocabularies |
   | grant kinds and enforcement | who holds which grants |
   | derive-don't-declare | tag modes, validation strictness |

   Follow this and the plugin is open-sourceable by construction rather than by
   later extraction.

---

## 1. Tree shape

```
VAULT/
├── SYSTEM/                  owner: system profile (this one)
│   ├── HANDBOOK/              design docs, specs, how-tos — why things are
│   ├── ISSUES/                systemic defects  ← APPEND-OPEN TO ALL AGENTS (§1.3)
│   ├── DECISIONS/             ADRs
│   ├── LOGS/                  operational records
│   ├── KNOWLEDGE/             ingested external docs (Hermes/API/MCP references)
│   └── .state/               machine-written only (dot-prefixed) — see §6
├── CREATIVE/                owner: TWW (+ WRITER, later)
│   ├── ISSUES/                domain-local issues (§1.3)
│   └── KNOWLEDGE/             research TWW ingested and approved
└── .vault/                  root config — see §3
```

**Two top-level trees, one per writing agent.** A new writing agent means a new tree.

This is a **seed, not a plan.** Internal structure below these folders is deliberately
absent and grows on demand via §10 — no folder exists before there is something to put
in it.

### 1.1 Rationale for what changed from v1

| v1 | v2 | Why |
|---|---|---|
| `RESEARCH/` as a peer tree | per-domain `*/KNOWLEDGE/` | Researcher is stateless (§2.3); knowledge belongs to whoever asked for it. Eliminates cross-domain writes entirely. |
| `SYSTEM/CONFIG/config.md` | `.vault/` configs + `.state/` | Config is machine-read data, not a note. |
| `TAXONOMY.md` | derived per-folder | Principle 1. |
| `INDEX.md` per folder, hand-maintained | generated | Principle 1. Same artifact, no agent burden, cannot drift. |
| `SYSTEM/HANDBOOK/VAULT/SCHEMA.md` | generated from configs | Principle 1. Readable in Obsidian, authored nowhere. |
| `.private/` | dropped | Private material belongs outside the vault, not as an excluded folder inside it. |

### 1.2 The KNOWLEDGE convention

Every writing domain may have a `KNOWLEDGE/` subfolder. **Same name, same schema,
everywhere.** This keeps a vault-wide knowledge query to a single glob
(`*/KNOWLEDGE/**`) and keeps consolidation possible later if domains ever overlap
enough to want it.

Accepted cost: two domains researching the same subject produce two notes. At current
scale this is acceptable and arguably correct — different domains want different
things from the same source. Revisit if domain count grows past ~4 with heavy overlap.

### 1.3 ISSUES is per-tree, not global

Every tree carries its own `ISSUES/` folder. The `issue` *kind* is **not** in the
global `kind` list — it is declared locally in each `*/ISSUES/.vault/config.yaml`,
so `issue` is a **vault-specific** value scoped to issue channels, never a general
note kind. (This matches the principle that vocabulary is per-tree; an "issue" is a
report *about* a tree, not a content type that competes with `note`/`essay`/`poem`.)

Routing by scope, not by author:

| Scope | Goes to | Owned by |
|---|---|---|
| Domain-local (a malformed note, broken link, drift inside a tree) | `<TREE>/ISSUES/` | vault_manager |
| Systemic (tool broken, plugin bug, config wrong, cross-domain) | `SYSTEM/ISSUES/` | system profile |

Every agent holds `append: ["**/issues/**"]` — it may raise an issue anywhere, and may
not edit or delete any issue, including its own. This is the department-to-system
reporting channel, and it is deliberately the *only* write an agent has outside its
own tree.

Each `ISSUES/` config declares `kind: [issue]`, the `open/in-progress/resolved`
status override, and an optional `severity`. The `issue` status override lives in
those configs (not the root), keeping the root vocabulary free of issue terminology.

---

## 2. Roles & grants

### 2.1 Grant model

Permissions are a per-agent list of path grants, not a role enum. Four grant kinds:

| Grant | Means |
|---|---|
| `read` | may read notes and query context |
| `write` | may create, edit, delete notes |
| `append` | may create new notes only; may not edit or delete existing ones |
| `meta` | may modify frontmatter, links, tags — **never body content**; the engine splices the frontmatter block and leaves the body bytes unchanged, so a metadata edit cannot alter prose even by accident (enforced by test, not trust) |
| `config` | may modify `.vault/*.yaml` vocabulary sections — **never** grants or field definitions (§3.7) |

Path patterns are globs relative to vault root. Deny by default: no matching grant
means the operation is refused by the plugin, not discouraged by a skill.

### 2.2 The agents

```yaml
# .vault/roles.yaml — starter preset (D8/D9). The full standard set, all ACTIVE (P3.7e).
agents:
  default:
    write:  ["system/**"]
    read:   ["**"]
    append: ["**/issues/**"]

  vault-manager:
    meta:   ["**"]              # frontmatter, links, tags — everywhere
    config: ["**"]              # vocabulary promotion/retirement — §3.7
    read:   ["**"]

  creative:
    write:  ["work/creative/**"]
    read:   ["work/creative/**", "work/*/knowledge/**"]
    append: ["**/issues/**"]

  dev:
    write:  ["work/coding/**"]
    read:   ["work/coding/**", "work/*/knowledge/**"]
    append: ["**/issues/**"]

  researcher:
    write:  ["work/*/knowledge/**"]
    read:   ["work/*/knowledge/**", "system/**"]
    append: ["**/issues/**"]
```

Three things this encodes deliberately:

- **The universal escape hatch.** Every agent gets `append: ["**/issues/**"]`. This is
  the entire "any department can report a problem" feature — one line. `append` not
  `write`, so an agent can raise an issue but cannot edit or delete issues (including
  its own). Routing by scope is §1.3.
- **`default` reads everything, writes only `system/`.** It needs to understand the
  structure to fix it. It does not need to author in other domains.
- **`vault_manager` cannot damage writing.** `meta` is a hard constraint enforced in
  code: it may rewrite frontmatter, repair a wikilink, normalise a tag, move a file.
  It may not alter a single word of body prose. An automated maintenance agent that
  is *structurally incapable* of destroying content.
- **`vault_manager` owns the vocabulary.** The `config` grant lets it promote, merge,
  and retire `type`/`kind` values without escalating to the system profile. The vault
  is its duty; vocabulary hygiene is part of that duty. See §3.7.
- **Read is wider than write.** `creative` writes only `work/creative/**` but reads
  `work/*/knowledge/**` across every domain (D9). Curated reference material is shared — it was
  vetted on the way in and is useful wherever a question arises. SYSTEM's logs, specs,
  and records stay out. Write boundaries protect ownership; read boundaries protect
  scope.
- **Read is deny-by-default enforcement, uniform across every surface** (D2,
  `03-design-decisions.md` — supersedes the earlier "read boundaries only need to
  filter noise" framing). An agent sees exactly what its `read` grants say,
  everywhere: search, graph traversal, the audit trail, and context. Same grant
  intersection, every surface. Shared reference is expressed by glob
  (`work/*/knowledge/**`, D9), never by global access.

### 2.2.1 Write scope and query scope are different

Write context is deliberately narrow — one folder's schema and vocabulary (§5). That
narrowness is where the token saving comes from, and it must not leak into search.

Query scope is independent and may span anything the agent can read: a subtree, a
union of unrelated folders, or the whole vault. A topic discussed in
`CREATIVE/PHILOSOPHY/` and referenced in `SYSTEM/KNOWLEDGE/` should surface in one
query with both origins shown.

Scope is derived from the folder tree — no `domain:` frontmatter field. Such a field
would restate the path, could go stale on a move, and could not express non-hierarchical
unions. Effective scope is always `requested_scope ∩ read_grants`: an agent may query
`**` and simply receives nothing from where it cannot read. No error, no leak.

The same intersection applies to **every read surface**, not only search: graph
traversal (`obsidian_graph`) and the audit trail (`obsidian_audit`) filter through the
caller's `read` grants identically, and `obsidian_index` (a write of derived files) is
gated on the caller holding any grant over the target folder (D2).

Full query design — scope syntax, named scopes, provenance grouping — belongs to the
tool surface (`02-tool-surface.md`), not to the data model.

### 2.3 The researcher — superseded by D9

> **Superseded (D9, `03-design-decisions.md`):** the researcher is now a vault agent
> with its own profile and grants — `write: [work/*/knowledge/**]`,
> `read: [work/*/knowledge/**", "system/**"]` — it owns the shared knowledge folders
> rather than being a stateless web-only subagent. The *intent* survives: the vault
> stays curated, not accumulated; knowledge enters through the owning domain. The
> delivery mechanism (dedicated profile vs. stateless function) is what changed.

### 2.4 Cross-domain links

Wikilinks across domains are **allowed and unrestricted**. Links are read-only and
cheap; gating them starves the graph. Writes are gated; links are free.

(This reverses `00-original-plugin-idea.md` §6, which required Manager permission to
traverse cross-domain edges. With per-domain KNOWLEDGE the case for it largely
disappears anyway.)

---

## 3. Schema & configuration

### 3.1 The five fields

Carried forward from v1 unchanged — the factoring is sound. Each field answers exactly
one question; none may take on another's job.

| Field | Answers | Format |
|---|---|---|
| `type` | What class of note, within its tree? | one enum value |
| `kind` | What is its nature / genre / form? | one or more controlled values |
| `status` | Where is it in its lifecycle? | one lifecycle value |
| `tags` | What is it about? | list, topic vocabulary |
| `created` | When was it conceived? | `YYYY-MM-DD` |

### 3.2 Uniformity contract (load-bearing)

**The five fields are identical everywhere in the vault.** Child configs may constrain
or extend the *allowed values* of a field. A child may **never** rename a field,
remove a field, or change its meaning or format.

This is what makes `status:active` mean one thing vault-wide, and it is the difference
between a queryable vault and a pile of folders. It is a hard validation rule.

Children *may* add extra fields beyond the five (see §3.4).

### 3.3 Inheritance

Config lives in `.vault/config.yaml` at any depth. Resolution merges root → leaf, CSS-like:

```
.vault/config.yaml                      base
CREATIVE/.vault/config.yaml             + creative types
CREATIVE/KNOWLEDGE/.vault/config.yaml   + source, retrieved, confidence
```

Merge semantics:

| Key | Merge behaviour |
|---|---|
| `fields.*.allowed` | union (child extends parent's vocabulary) |
| `fields.*.allowed_only` | replace (child restricts — explicit opt-in) |
| `defaults` | child overrides key-by-key |
| `required` | union — a child may add requirements, never drop inherited ones |
| `tags.mode` | child overrides wholly |

One root config plus a small override where a domain genuinely differs. Adding a domain
is one small file, not a global edit.

### 3.4 Vocabulary is declared per tree

`type` and `kind` vocabularies are **domain-specific**. The root declares only what is
genuinely universal; each tree declares its own. Inheritance (§3.3) unions them, so an
agent is only ever offered the vocabulary of the domain it is writing in — CREATIVE's
list may grow to fifty genres without costing SYSTEM a single token.

Which fields *carry* a vocabulary (and so get the declared/observed lifecycle of §3.7)
is a per-field flag — `vocabulary: true` — not a name the engine knows. `type` and
`kind` have it; `status` does not. A vault may mark any field it likes. This is
principle 7: the engine knows *there is a vocabulary field*, never *which field is
named `kind`*.

```yaml
# .vault/config.yaml — universals ONLY
fields:
  type:
    required: true
    allowed: [index, note]
  kind:
    required: true
    multi: true
    allowed: [note, index, reference]            # P3.5: 'issue' is NOT global — declared only in */issues/ configs (§1.3)
  status:
    required: true
    allowed: [draft, active, paused, completed, reference]
  tags:
    required: true
    multi: true
  created:
    required: true
    format: date

defaults:
  status: draft
  created: "@today"

tags:
  mode: suggest

validation:
  fields: blocking       # missing/invalid required field → refuse write
  tags: advisory         # near-duplicate → warn, allow
```

```yaml
# SYSTEM/.vault/config.yaml
fields:
  type: { allowed: [spec, record, howto, knowledge] }
  kind: { allowed: [spec, log, decision, howto, api-reference] }
```

```yaml
# CREATIVE/.vault/config.yaml
fields:
  type: { allowed: [work, idea, project, knowledge] }
  kind: { allowed: [concept, essay, poem, script, character, scene, fragment] }
```

A note in `CREATIVE/` validly accepts `kind` from the union
`[note, index, reference, issue, concept, essay, poem, ...]` and never sees `spec` or
`api-reference`. Root stays small; domains stay expressive; neither pays for the other.

### 3.5 Per-class status overrides

Carried from v1 — genuine modelling, keep it.

```yaml
status_overrides:
  issue:      [open, in-progress, resolved]
  decision:   [proposed, adopted, rejected]
```

**Implementation note (supersedes the literal key):** in the engine this is
shorthand for a general mechanism — `value_overrides: { field, by, map }` — so
per-class overrides work on *any* vocabulary field, not only one named
`status` (principle 7: no field name is hardcoded in the engine). A vault that
prefers the general form writes:

```yaml
value_overrides:
  field: status          # which field's allowed values change per class
  by: kind               # which field selects the override
  map:
    issue:    [open, in-progress, resolved]
    decision: [proposed, adopted, rejected]
```

`status_overrides` is accepted and expanded automatically.

### 3.6 KNOWLEDGE schema (first inheritance test)

```yaml
# */KNOWLEDGE/.vault/config.yaml   — identical in every domain
fields:
  type:
    allowed_only: [knowledge]
  source:
    required: true                 # URL or origin
  retrieved:
    required: true
    format: date
  confidence:
    allowed: [high, medium, low]
defaults:
  status: reference
  kind: [reference]
```

This is the proving case for §3.3: same subfolder name, same schema, inheriting a
different parent in each domain.

### 3.7 Vocabulary lifecycle — self-extending registry

A controlled vocabulary must be able to grow, or agents will either fight it or drift
around it. But if it grows automatically it stops controlling anything. Resolution: a
**third state** between allowed and refused.

| State | Meaning | On write |
|---|---|---|
| **declared** | present in some config's `allowed` | accept silently |
| **observed** | in use in notes, not in any config | accept, flag as unregistered |
| **unknown** | neither | refuse; offer declared + observed, or explicit registration |

Both states are returned by the context call (§5), distinguished:

```yaml
kind:
  declared: [concept, essay, poem]
  observed: [{name: aphorism, count: 3, since: 2026-08-01}]
```

Showing the live vocabulary *at the moment of writing* is what produces reuse. An agent
that can see `essay` will not invent `essai`. This is what v1's "go read TAXONOMY.md"
was attempting and failing to achieve — same goal, delivered at the point of decision
instead of as a prerequisite read.

#### Introducing a value

Deliberate but cheap — one extra argument, never automatic:

```
obsidian_write(..., register: {"kind": "aphorism"})
```

The agent must *choose* to introduce a vocabulary term. That single token of friction is
the whole difference between a controlled vocabulary and a pile of strings. Auto-
registration would turn `allowed` into a log of everything ever typed. (The registration
requires the `config` grant; the value is written to the nearest config declaring that
field, so a tree's term lands in that tree — never at the vault root unless root is the
nearest.)

A registered value enters **observed**, not declared. Promotion is a separate act.

#### Curation — vault_manager's duty

Promotion, merge, and retirement are handled by `vault_manager` under its `config`
grant (§2.2). It **decides and acts**; it does not escalate to the system profile.
Vocabulary hygiene is vault business.

| Signal | Action |
|---|---|
| observed, ≥N uses, ≥D days stable | promote to `declared` in the narrowest config that covers its usage |
| observed, near-duplicate of a declared value | merge — rewrite affected frontmatter (`meta` grant), do not declare |
| observed, single use, aged out | flag in `<TREE>/ISSUES/` for the owning agent to reconsider |
| declared, zero uses over a long window | propose retirement; remove only after confirmation |

Thresholds live in `.vault/config.yaml` under `vocabulary:`. Every promotion, merge,
and retirement is written to `.state/audit-log.jsonl`, and a human-readable
summary lands in the generated registry (§6).

The manager escalates to `SYSTEM/ISSUES/` **only** when something is structurally
broken — a config that will not parse, a merge that would collide with a declared
value, a field-definition conflict between configs. Judgement calls about vocabulary
are its own.

Constraint: the `config` grant covers **vocabulary sections only**. `vault_manager`
may not touch `roles.yaml`, field definitions, `required`, or `validation` mode. It
curates values, never structure.

#### Why the asymmetry with tags

Tags are derived with no gate; `type`/`kind` are derived *and* declared with a
promotion gate. Justified: tags are descriptive and cheap to be wrong about, while
`type`/`kind` are structural — queries, templates, and validation depend on them. A
stray tag is noise; a stray `type` breaks retrieval.

---

## 4. Tags

Tags are **never declared in a file**. The tag vocabulary for a folder is computed
from the frontmatter of notes in scope. It cannot drift because it *is* reality.

Per-folder mode:

| Mode | Behaviour |
|---|---|
| `open` | any tag accepted; list derived from usage |
| `suggest` | derived + fuzzy near-duplicate warning at write time (`#Project` → "did you mean `project`?") |
| `closed` | only tags in `allowed:` accepted; anything else refused |

Default `suggest`. Use `open` where vocabulary should grow freely, `closed` where
consistency is load-bearing.

Near-duplicate detection is deterministic — case-fold, singular/plural, trigram
similarity. **No embeddings.** This is what makes §7.2 tag consolidation in the
original spec largely unnecessary: prevented at write, not repaired after.

---

## 5. The context call

The interface that replaces "read the skill, then the reference, then TAXONOMY":

```yaml
obsidian_context("CREATIVE/PHILOSOPHY")
→ {
    schema: {
      fields: { ...merged, resolved... },
      type:    { declared: [work (2), idea], observed: [] },
      kind:    { declared: [concept (3), essay (1)],
                 observed: [aphorism (3)] },
      status:  { allowed: [draft, active, ...] }
    },
    tags:     [ "ontology (1)", "nietzsche (2)", ... ],   # derived, this scope
    siblings: [ ...note titles for linking... ],
    template: "---\ntype: <type>\nkind: [<kind>]\n...\ndescription: \"one-line summary\"",
    grants:   { write: true, register: true },            # for the calling agent
    engine_options: { config_options: [...], grant_kinds: [...] }  # self-describing
  }
```

One call. Everything needed to write a conforming note in this folder, and nothing
about any other folder. ~300 tokens against ~3,000 for the v1 read-the-docs path.

The `grants` row is the caller's effective rights in this folder — five booleans
(`read`/`write`/`append`/`meta`/`config`), **shipped in P3.6**. An agent learns
whether it may act *before* being refused; a zero-grant agent gets an all-false row
and no siblings (D2). Writing rules live in the role's skill (D7) — the engine
never embeds convention content in the payload.

Note the vocabulary arrives **scoped and split** (§3.7): only this domain's values,
with `declared` and `observed` distinguished so the agent can prefer settled terms.
Vocabulary is rendered compactly (`"essay (1)"`) rather than as verbose objects — the
payoff is ~8x fewer tokens for the same information.

`engine_options` (added 2026-08-02) is the engine's own configuration reference, so a
from-zero user or a setup-assistant AI can discover capabilities like `summary_field`
or the `vocabulary: true` flag without reading source. Also exposed directly via
`obsidian_reference`. It is generated from `vault/reference.py`, so it cannot drift
from the code (principle 1).

Write path: `obsidian_write(path, frontmatter, body, register={"kind": "?"})`
validates against resolved config and refuses on blocking violations.

---

## 6. Generated vs authored

Unambiguous, because ambiguity here is how the v1 model decayed.

| Artifact | Authored by | Notes |
|---|---|---|
| Note bodies | agents / human | the actual content |
| `.vault/*.yaml` | human (system profile) | the only hand-written config |
| `SYSTEM/HANDBOOK/**` | system profile | prose: why, not what |
| `INDEX.md` (all) | **generated** | on write or cron; never hand-edited |
| `SYSTEM/HANDBOOK/registry.md` | **generated** | human-readable view of merged configs |
| `.state/audit-log.jsonl` | **plugin** (always on) | append-only JSONL at **vault root** (dot-prefixed, reads as machinery) — the engine's ledger, not a content tree. Auto-created on first write; the manager (P4) depends on it. Relocatable via `paths.state` but never absent. |
| `.state/change-log.json` | **plugin** (P4) | file events — *not yet built* |
| `.state/graph/{nodes,edges}.json` | *not persisted* | the graph is **derived on demand** from note bodies (P3), not stored |
| `.state/search-index/` | **plugin** | if built at all — see §9 (A4: deferred) |

**Implementation notes (drift between this table and the built code):**

- The audit log is **JSONL** (`audit-log.jsonl`), not a JSON array. Append-only so a
  crash cannot corrupt earlier entries and concurrent appends interleave safely.
- `change-log.json` is a **P4** deliverable, not yet built.
- **The graph is not stored.** `obsidian_graph` computes the wikilink graph from
  note bodies on every call — no `nodes.json`/`edges.json` on disk. This is a
  deliberate strengthening of "incremental": a derived-on-demand graph cannot drift
  from reality, and at vault scale a full recompute is sub-second. The `.state/
  graph/` row is retained only to record that we explicitly chose *not* to persist it.
- `search-index/` is deferred (A4): grep-class search is sufficient; revisit only
  if measurement shows otherwise.
- **`.state/` is a vault-root engine folder, always present.** The audit trail
  (and later the manager) depend on it, so the engine *defaults* `state` to a
  root `.state/` and auto-creates it on first write — a vault using this plugin
  always has a ledger. `paths.state` may relocate it, but it cannot be disabled
  by omission. It is engine-reserved machinery (like `.vault`), not a content tree,
  so it does not appear in the portability policy-name guard.
- Machine state lives wherever `paths.state` says; the default is root `.state/`.

**`summary_field` (added 2026-08-02):** a config key naming the frontmatter field used
as each note's one-line summary, rendered in INDEX so notes are triageable without
opening them. The *field name* is policy (`description` for Davide, `blurb` for a PARA
vault); only the `summary_field` key is engine. Advisory, never required.

**Rule:** a generated file carries a `<!-- generated: do not edit -->` marker and is
overwritten without warning. If you want to change a generated file, change its source.

Generated files stay *inside* the vault (not a hidden `.obsidian-vault/`): visible,
backed up, owned by `vault_manager`, and readable in Obsidian.

---

## 7. Skill shape after this

The `obsidian-vault` skill collapses from ~500 lines to a short protocol:

1. Call `obsidian_context(target_folder)`.
2. Write conforming to what it returns.
3. Call `obsidian_write` — it validates.
4. Record loose threads to `SYSTEM/ISSUES/`.

Everything else moved into data or code. Judgement stays in the skill; rules do not.

**One rule stays prose deliberately:** *never commit the vault without explicit
direction.* That is a judgement boundary about consequences, not a validation rule.
Enforce it in code as a hard denial **and** state it in the skill.

---

## 8. Build order

| Phase | Deliverable | Proves |
|---|---|---|
| 0 | config loader + inheritance resolver + `obsidian_context` | the model |
| 0b | maintainability + portability pass: `paths.py`/`constants.py` extraction, pytest suite, Principle 7 enforcement | open-sourceable by construction |
| 1 | `obsidian_write` with blocking validation + grant enforcement | the boundary |
| 2 | generated INDEX + registry | derive-don't-declare |
| 2b | `obsidian_scaffold` (§10); P2 addendum: `summary_field` + `obsidian_reference` self-documenting config | growth without redesign; discovery |
| 3 | graph + search: `obsidian_graph` (derived on demand), `obsidian_search` (deterministic) | navigation |
| 4 | change-log + vault_manager pass: sanitization **+ vocabulary curation (§3.7)** | the second layer |
| 5 | MCP adapter for UI verbs (`open_file`, `active_file_get_path`) — optional transport, not a second implementation | the façade |

Nothing after phase 1 is committed to. Several sections of
`00-original-plugin-idea.md` may dissolve once 0–2 exist.

---

## 9. Open questions

1. **BM25 index (`00-…` §4)** — duplicates Obsidian's own index *and* ripgrep. Defer
   until measurement shows `search_files` is insufficient.
2. **Similarity matching (`00-…` §2, §7.3)** — original spec wants semantic similarity
   but forbids local embeddings. Proposal: deterministic only (tag overlap + title
   trigram), and drop the word "semantic" from the spec.

### Resolved

- **`.private/`** — dropped. v2 has no private tree. If private material is ever
  needed it lives outside the vault entirely, not as an excluded folder inside it.
- **CREATIVE internal structure** — deliberately not designed. Superseded by §10:
  the deliverable is the mechanism for growing structure, not the structure.
- **Migration** — none. Knowledge from `hermes_workspace/` is re-entered
  selectively and by hand, one item at a time, by whichever agent owns the domain —
  so it enters through `obsidian_write` and conforms by construction. No migration
  tooling, no compatibility layer, no import path.
- **Open-sourcing / customisability for other users** — resolved into Principle 7.
  The engine hardcodes no tree, folder, or field name; every vault-specific choice
  lives in `.vault/config.yaml`. A PARA or Zettelkasten user reuses the engine with
  their own layout and fields, zero code change. Verified by running the whole engine
  against a foreign vault in `tests/test_portability.py`. The plugin ships as a
  *general engine* plus Davide's config as one example preset.

---

## 10. Growing the vault

The vault must not be designed ahead of use. Folders, schemas, and conventions are
added **when a real need appears**, never in anticipation of one. This section
specifies the mechanism that makes that cheap; §1's tree shape is the seed, not the
plan.

### 10.1 Principle

> A new folder should cost one conversation and one command — never a redesign.

If adding structure is expensive, structure gets added prematurely (to avoid paying
later) or not at all (to avoid paying now). Both are failure modes. The mechanism
below aims to make the cost low enough that the honest answer — *"add it when we need
it"* — is also the easy one.

### 10.2 The scaffold call

```
obsidian_scaffold(path, intent="...", proposed={...}, confirm=false)
```

Given a target path and a plain-language intent, the plugin:

1. **Resolves inherited config** for the parent — what this folder already gets for
   free (§3.3).
2. **Proposes a delta only** — the fields, vocabulary, and defaults this folder needs
   *beyond* inheritance. Most new folders need none; that is the correct outcome and
   should be stated plainly rather than padded.
3. **Returns the proposal for discussion** — nothing is written while `confirm=false`.
4. On `confirm=true`: creates the folder, writes `.vault/config.yaml` **only if a
   non-empty delta was agreed**, regenerates the parent INDEX, logs to the audit trail.

Empty deltas write no config file. A folder with no special needs is just a folder —
absence of config is the default state, not an omission.

### 10.3 Who may scaffold

| Agent | May scaffold |
|---|---|
| domain owner (e.g. `tww` in `CREATIVE/**`) | yes, within its own tree |
| `system` | yes, within `SYSTEM/**` |
| `vault_manager` | no — it curates existing structure, never creates it |

Scaffolding is a `write` operation and follows the same grants as any other (§2.1).

### 10.4 Confirmation policy

| Change | Requires |
|---|---|
| new folder, no config delta | agent may proceed |
| new folder with config delta | **user confirmation** |
| new field on an existing folder | **user confirmation** |
| new `type`/`kind` value | `register_*`, then curation (§3.7) — no user gate |

The line: **values flow freely and get curated; structure requires assent.** Adding
`aphorism` as a kind is reversible and low-stakes. Adding a required field to a folder
changes what validates for every note written there afterwards.

### 10.5 Convention capture

When a folder acquires a convention that *cannot* be encoded — a way of working, a
reason, a caution — it goes to `SYSTEM/HANDBOOK/`, linked from the folder's generated
INDEX. It never becomes prose the agent must read before writing.

> **Superseded by D7 (`03-design-decisions.md`):** conventions live in the skill's
> mutable files (per-profile), not in HANDBOOK. HANDBOOK remains an *optional user
> convention*, independent of plugin mechanics — a user who wants a handbook keeps
> one; the plugin neither creates nor requires it.

Test for where something belongs:

- Can validation check it? → config (§3)
- Is it a judgement the agent must exercise? → HANDBOOK, and only loaded when relevant
- Neither? → it probably isn't a convention yet

### 10.6 What this replaces

v1 grew structure by editing the skill: new folder meant new `references/<tree>.md`
prose, a new INDEX entry by hand, and vocabulary added to a global registry file. Three
edits across two systems, none enforced, all liable to drift.

v2: one call, a short conversation, and the structure exists with its config, its
generated index, and its audit entry. The skill is untouched.
