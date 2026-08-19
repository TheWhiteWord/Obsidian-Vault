# Tool reference

The plugin registers **18 tools** under the `obsidian_vault` toolset.
They all share two optional standard arguments: `agent` (who is acting,
as named in `roles.yaml`; defaults to `$OBSIDIAN_VAULT_AGENT`) and
`vault` (vault-root override; defaults to `$OBSIDIAN_VAULT_PATH`).

Gates are grant-based, deny-by-default. The operation→grant mapping:
`read`/`context`/`search` → `read`; `create` → `write` (also
satisfiable by `append`); `edit`/`delete` → `write`; `edit_meta` →
`meta`; `edit_config` → `config`.

## Writing

| Tool | Purpose | Key parameters | Gate |
|---|---|---|---|
| `obsidian_context` | Everything needed to write a conforming note in one folder: merged schema, declared vs observed vocabulary, tag cloud, siblings, a ready-to-fill template, and your grants. Call this **before** writing. | `folder` (required; `.` = root) | `read` |
| `obsidian_write` | Create or update a note. Frontmatter is validated against the folder's schema before anything is written; a non-conforming note is refused with the specific problems listed. | `path`, `frontmatter` (required); `body`, `register`, `overwrite` | `write` — or `append` for a **new** note |
| `obsidian_edit_metadata` | Change frontmatter without touching the body (byte-identical prose). Use for status changes, tag fixes, link repair. `null` as a value removes a field. | `path`, `changes` (required) | `meta` |
| `obsidian_delete` | Delete a note. An `append` grant is not sufficient. | `path` (required) | `write` |

## Structure

| Tool | Purpose | Key parameters | Gate |
|---|---|---|---|
| `obsidian_scaffold` | Create a folder cheaply: returns a proposal of only what the folder needs **beyond inheritance**, writes nothing unless `confirm=true`. Structural config (new required fields, or `allowed_only` narrowing) needs `proposed.user_confirmed=true` *and* `confirm=true` — `confirm=true` alone is refused; vocabulary values need neither. Empty deltas write no config. | `path` (required); `intent`, `proposed`, `confirm` | `write` / `append` (create operation) |
| `obsidian_edit_config` | Edit an existing `.vault/config.yaml` — the config-gated sibling of scaffold. Same delta semantics; structural changes need `proposed.user_confirmed: true`. Never edits `roles.yaml`; refuses uniformity violations (redefining `format`/`multi`). | `path`, `proposed` (required); `confirm` | `config` |
| `obsidian_conventions` | Read or edit the in-tree scope directives. Read mode (`folder`): the resolved conventions chain — nearest file plus fallbacks. Edit mode (`path` ending in `.vault/conventions.md` + `content`): only the derived owner of the scope may write; the manager never writes conventions. | `folder` — or `path` + `content` | read: any agent; edit: `write` over the scope |

## Derived

| Tool | Purpose | Key parameters | Gate |
|---|---|---|---|
| `obsidian_index` | Regenerate derived artifacts: a folder's INDEX and/or the registry. Use after bulk changes, or to produce a human-readable view of the effective schema. | `folder` (`.` = whole vault); `registry_to` | any grant over the target |

## Read

| Tool | Purpose | Key parameters | Gate |
|---|---|---|---|
| `obsidian_search` | Deterministic term search across titles, tags, bodies, links, frontmatter. `scope` accepts a glob or list (`!`-prefixed entries exclude). Results are silently intersected with your read grants — searching `**` returns nothing from where you cannot read. | `query`; `scope` / `folder`, `fields`, `group_by`, `limit` | `read` |
| `obsidian_graph` | Navigate the wikilink graph: neighbors (in/out/both) or N hops from a note; `dangling: true` lists links to missing notes. Derived on demand, never cached. | `path` (required); `hops`, `direction`, `dangling` | `read` |
| `obsidian_audit` | Read the append-only audit trail: every vault mutation with agent, action, path, timestamp. Entries are filtered to what you can read. | `limit` (default 100); `agent`, `action` | `read` |
| `obsidian_reference` | Discover what the engine supports: every config option and the five grant kinds, self-described. Use when setting up a vault or unsure a capability exists. | — | none |

## Issues

> **IMPORTANT — conclude formally.** Deciding an issue in chat does not close it.
> When you decide an issue is done, wrong, or not yours to act on, call
> `obsidian_issue_resolve` to set its state — the ledger is the system of record,
> not the conversation. An issue left `open` after you've moved on just clutters
> the next sweep.

| Tool | Purpose | Key parameters | Gate |
|---|---|---|---|
| `obsidian_issue` | Raise one or more issues on the ledger (the manager's batch). Records are invisible to search/graph by construction. Duplicate keys are skipped; a **resolved** issue with the same key is re-opened (a genuine regression) — a **declined** one stays closed (permanent owner rejection, recorded so it never re-raises). | `items` (required): `subject`, `detail`, `target` each; `priority`, `tags`, `key`, `assignee` (who should resolve — a SHOULD signal, never a grant override) optional | any registered agent |
| `obsidian_issue_resolve` | Move an issue: route it (`assignee` — sets who should resolve, state untouched), claim it (`in_progress` — records you as the holder) or close it (`resolved` fixed / `declined` won't fix). Optionally record why. | `key` (required); `assignee`, `state` (`in_progress` \| `resolved` \| `declined`), `reason` | `write` **or** `meta` over the target |
| `obsidian_issue_list` | List issues, filtered and grant-intersected: you see only issues whose target you can read. "My issues" is a query, not a folder. | `state`, `priority`, `tags`, `target`, `raised_by`, `assigned_to` (`me` = calling agent), `limit` | `read` intersection |

## Protocols

| Tool | Purpose | Key parameters | Gate |
|---|---|---|---|
| `obsidian_protocol_list` | List the handoffs where you are a party (requester or responder); `peer=<profile>` narrows to one pair. | `peer` | registered agent (grant-free) |
| `obsidian_protocol` | Read, register, or update one handoff. Read mode (`name`): the full record. Register (`register`): create — you must be one of the sides. Update (`name` + `update`): replace — you must be a party. `confirm: true` applies the write; without it the call validates and gates. | `name`; `register`; `update`; `confirm` | read: registered agent; write: parties only |

## Maintenance

| Tool | Purpose | Key parameters | Gate |
|---|---|---|---|
| `obsidian_maintain` | Run the maintenance sweep. Three depths — cron drives the mode: `delta` (only what changed since the last sweep), `maintain` (full correctness census), `optimize` (adds quality suggestions). Regenerates INDEXes, promotes vocabulary, distributes findings as ledger issues (dedupe by key). `dry_run` rehearses with zero writes. Findings are for the owning domain agent — the manager never edits content. | `mode`, `distribute` (default true), `dry_run` | registered agent (designed for the manager role) |
