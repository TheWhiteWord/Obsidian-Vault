# Issues

The vault's shared issue ledger, from the manager's seat. Load before
triaging, resolving, or raising.

## The ledger

Issues are **JSON records** under `.state/issues/<slug>.json` — engine
machinery, invisible to search/graph/INDEX by construction (`.state` is
skipped). They are *about* the vault, not part of it.

Every record carries engine-fixed fields: `key`, `state` (open /
in_progress / resolved / declined), `nature` (finding / suggestion),
`priority` (low / medium / high / critical), `subject`, `detail`, `target`
(a path or a scope glob), `tags`, `raised_by`, timestamps, and resolution
info.

## Rules of the layer

- **Raise ≠ fix.** Filing an issue is an escalation valve, not permission to
  act. Raising succeeds without grants over the target; acting on it is a
  separate, grant-checked step.
- **Access is derived at call time** from grants against the record's
  `target` — no folders, no routing table, no per-domain inboxes. "My
  issues" is a query, not a location.
- **Dedupe by key.** Raising an open key returns the existing record;
  re-raising a closed one reopens it (history kept, priority preserved).
- **Issues are not notes** — never write them with `obsidian_write`, never
  link them, never expect them in INDEX.

## Triage

`obsidian_issue_list` reaches the whole vault (your `read` covers every
target): current state of every issue, newest first.

- Filters: `state`, `priority`, `tags`, `target`, `raised_by`, `limit`
  (default 50).
- The census backlog is the main inflow — sweep findings carry
  `key = <check>|<path>`, `target = path`, `tags: [maintenance]`. Filter on
  the tag to see the backlog; on `target` for one domain.
- Pair with `obsidian_audit` for the mutation side (see
  `references/maintenance.md`).

## Raising

`obsidian_issue` with `items: [{subject, detail, target, ...}]` — you raise
structural breakage and triage anomalies instead of silently fixing them.
Target the affected path or a scope glob like `system/**`. The response
reports `created`, `exists`, or `reopened` per item.

## Resolving and declining

`obsidian_issue_resolve` with `key` — close `resolved` or `declined`, with an
optional `reason`. Your `meta` grant covers every target, so any issue is
closable.

- `resolved` when the condition cleared. The sweep auto-resolves its own
  findings; manual resolution is for what it cannot see.
- `declined` with an honest `reason` when an issue is not actionable — the
  reason is what the raiser sees.
- Content judgment stays with the domain owner: when closing would mean
  deciding content for someone else's domain, escalate instead of deciding.

## The sweep in the ledger

The sweep files findings, auto-resolves cleared conditions, auto-declines
suggestions unanswered after 14 days, and prunes records closed after 30
days. Your cron runs it daily (`maintain`) and Monday (`optimize`) — full
mechanics in `references/maintenance.md`.
