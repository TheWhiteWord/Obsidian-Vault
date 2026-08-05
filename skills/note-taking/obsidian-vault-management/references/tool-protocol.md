# Tool protocol

How the `obsidian_*` tools behave.

## Tool requirements

- `obsidian_context` — none: it reports the grants you hold in the folder.
- `obsidian_maintain` — the sweep (delta / maintain / optimize). Your core
  duty; see `references/maintenance.md`.
- `obsidian_index` — any grant over the folder.
- Reads — `obsidian_search`, `obsidian_graph`, `obsidian_audit` need `read`.
- `obsidian_edit_metadata` — needs `meta` (frontmatter only, never body).
- `obsidian_edit_config` — needs `config`.
- Issues — `obsidian_issue` needs a registered agent identity;
  `obsidian_issue_list` needs `read` over the target; `obsidian_issue_resolve`
  needs `write`/`meta` over the target.
- `obsidian_reference` — none (it is the self-documentation).

Write-gated tools (`obsidian_write`, `obsidian_delete`, `obsidian_scaffold`)
are not in your remit — your grants hold no content `write`; structural work
runs through the growth subcommands.

## Grants — deny by default

What each grant kind allows is returned by `obsidian_reference`. Behavior: an
unlisted agent holds nothing; every read surface filters by your `read`
grants — a `**` query returns nothing from where you cannot read, silently,
never as an error.

## Refusal semantics

- `permission_denied` — you lack the grant for the operation.
- `validation_failed` — the note violates the effective schema; the response
  carries per-field errors with `did_you_mean` suggestions.
- Responses are structured JSON — an actionable object, never a stack trace.

## Enforcement order (writes)

`safe_join` (path confinement) → grant check → schema validation → write.
No bypass path.

## Scope globs

- `**` crosses separators (`work/creative/**`); `*` does not (`*/issues/**` is
  one folder per tree).
- `scope` filters results; `folder` bounds the scan. Grant intersection is
  applied after the query.
