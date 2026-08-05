# Tool protocol — immutable reference

How the `obsidian_*` tools behave. Load when planning a multi-tool operation
or debugging a refusal.

## The surface

| Tool | Needs | Purpose |
|---|---|---|
| `obsidian_context` | read (folder) | Schema, vocabulary, tags, grants, `conventions_ref` |
| `obsidian_write` | write / append | Create or edit a note (validated) |
| `obsidian_edit_metadata` | meta | Splice frontmatter only — body bytes untouched |
| `obsidian_delete` | write | Remove a note |
| `obsidian_scaffold` | write | Create a folder / propose structural change |
| `obsidian_edit_config` | config | Edit an existing `.vault/config.yaml` — scaffold's delta, applied to files that exist |
| `obsidian_index` | any grant | Regenerate INDEX.md / registry for a folder |
| `obsidian_audit` | read (paths) | The append-only mutation trail, filtered by grants |
| `obsidian_search` | read (paths) | Term search over title/body/tags/links/frontmatter |
| `obsidian_graph` | read (paths) | Wikilink neighbors, N-hop traversal, dangling links |
| `obsidian_reference` | — | Self-describing config options + grant kinds |
| `obsidian_issue` | registered agent | Raise one/many ledger issues (escalation valve) |
| `obsidian_issue_resolve` | write/meta over target | Close an issue: resolved / declined |
| `obsidian_issue_list` | read (targets) | List ledger issues, grant-intersected |
| `obsidian_maintain` | manager grants | The sweep: delta / maintain / optimize |

## Grants (deny-by-default)

| Kind | Allows |
|---|---|
| `read` | read notes, query context |
| `write` | create, edit, delete |
| `append` | create only — no edit, no delete |
| `meta` | frontmatter / links / tags — never body prose |
| `config` | vocabulary sections of `.vault/*.yaml` — never grants/field defs |

- Every read surface filters by the caller's `read` grants (D2). Querying
  `**` returns nothing from where you cannot read — silently, not as an error.
- `obsidian_audit` / `obsidian_graph` / `obsidian_search` all apply this.
- `obsidian_index` is gated on *any* grant over the target folder.

## Refusal semantics

- `permission_denied` — you lack the grant for the operation. Fix the request
  or the grants (config grant only).
- `validation_failed` — the note violates the effective schema; the response
  carries field errors and `did_you_mean` suggestions.
- Errors are structured JSON; an actionable object, never a stack trace.

## Enforcement order (writes)

`safe_join` (path confinement) → grant check → schema validation → write.
No bypass path; generated files carry `<!-- generated -->` and are never
hand-edited.

## Scope globs

- `**` crosses separators (`work/creative/**`), `*` does not (`*/issues/**` =
  one folder per tree).
- `scope` filters results; `folder` bounds the scan.
- Grant intersection is applied *after* the query — you never see what you
  cannot read.

## Agent resolution

Handlers accept `agent`; falling back to `$OBSIDIAN_VAULT_AGENT`, then a
default. The installer sets the profile's agent name so each profile acts as
its own identity in `roles.yaml`.

## conventions_ref

`obsidian_context` returns `conventions_ref` — a **pointer** to the skill
owning the vault's writing conventions (default: `obsidian-vault`; per-vault
override via `conventions: {skill: ...}` in root config). It never returns the
content; the agent loads that skill itself.
