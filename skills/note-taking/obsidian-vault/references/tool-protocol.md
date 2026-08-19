# Tool protocol

How the `obsidian_*` tools behave.

## Tool requirements

- `obsidian_context` — none: it reports the grants you hold in the folder.
- Writes — `obsidian_write`, `obsidian_delete`, `obsidian_scaffold` need
  `write`; `obsidian_edit_metadata` needs `meta`; `obsidian_edit_config` needs
  `config`.
- Reads — `obsidian_search`, `obsidian_graph`, `obsidian_audit` need `read`;
  `obsidian_index` needs any grant over the folder.
- Issues — `obsidian_issue` needs a registered agent identity;
  `obsidian_issue_list` needs `read` over the target; `obsidian_issue_resolve`
  needs `write`/`meta` over the target.
- `obsidian_reference` — none (it is the self-documentation).
- `obsidian_conventions` — reading needs none (any registered agent); the
  edit mode (`path` + `content`) needs `write` over the containing scope.

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

## Structural-change confirmation

Some config changes alter what validates for future notes — adding a required
field, or narrowing a vocabulary to `allowed_only`. The engine will not apply
these on the agent's own authority, even with `confirm=true`: `confirm` means
"I am executing", not "the human approved a schema change".

Two separate flags, by design (scaffold.py / edit_config.py `_user_confirmed`):

- `confirm=true` — the agent authorizes the write to proceed.
- `proposed.user_confirmed=true` — the agent asserts the *human* explicitly
  approved this structural change (e.g. via the `clarify` tool).

A structural delta is refused (`ScaffoldRefused`) unless **both** are true. Set
`user_confirmed: true` *inside the `proposed` dict* — not as a top-level
argument — and only after the user has actually confirmed. Vocabulary *values*
(broadening `allowed`) are not structural and need neither flag.

## Enforcement order (writes)

`safe_join` (path confinement) → grant check → schema validation → write.
No bypass path.

## Scope globs

- `**` crosses separators (`work/creative/**`); `*` does not (`*/issues/**` is
  one folder per tree).
- `scope` filters results; `folder` bounds the scan. Grant intersection is
  applied after the query.
