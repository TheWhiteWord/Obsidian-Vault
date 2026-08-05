# Issues — immutable reference

The vault's issue layer: ledger records, not notes. Load before raising,
listing, or resolving an issue.

## The ledger

Issues are **JSON records** under `.state/issues/<slug>.json` — engine
machinery, invisible to search/graph/INDEX by construction (`.state` is
skipped). They are *about* the vault, not part of it; bugs don't live in
production data, they live in a tracker.

Every record carries engine-fixed fields: `key` (`<check>|<path>` or
`<slug>`), `state` (open / in_progress / resolved / declined), `nature`
(finding / suggestion), `priority`, `subject`, `detail`, `target`,
`tags`, `raised_by`, timestamps, and resolution info.

## Lifecycle

| Action | Tool | Who |
|---|---|---|
| Raise one or many | `obsidian_issue` (`items:`) | any registered agent |
| List | `obsidian_issue_list` | anyone with read over the targets |
| Resolve / decline | `obsidian_issue_resolve` | write or meta over the target |
| Auto-resolve | `obsidian_maintain` | the sweep, when the condition clears |
| Auto-decline | TTL | suggestions, 14 days unanswered |
| Prune | TTL | resolved records, 30 days after close |

## Rules of the layer

- **Raise ≠ fix.** Filing an issue is an escalation valve, not permission to
  act. The raise succeeds without grants; acting on it is a separate,
  grant-checked step.
- **Access is derived at call time** from grants against the record's
  `target` — there are no folders, no routing table, no per-domain inboxes.
  "My issues" is a query, not a location.
- **Dedupe by key.** Raising the same `key` again returns the existing
  record instead of duplicating it. Re-escalation after resolution reopens
  with a new priority.
- **The sweep is the distributor.** `obsidian_maintain` turns findings into
  ledger records (`tags: [maintenance]`); a human or manager never has to
  file the census by hand.
- **Issues are not notes** — never write them with `obsidian_write`, never
  link them, never expect them in INDEX.

## Typical contributor flow

1. Spot something wrong (broken link, stale INDEX, missing convention).
2. `obsidian_issue` with `items: [{subject, detail, target, nature}]`.
3. `obsidian_issue_list` (optionally filtered) to track it.
4. Let the manager's sweep or a grant-holder resolve it — or resolve it
   yourself if you hold write/meta over the target and the resolution is
   yours to make.
