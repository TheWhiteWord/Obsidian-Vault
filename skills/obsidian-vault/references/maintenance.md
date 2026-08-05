# Maintenance — immutable reference (manager)

The vault-manager's sweep: what `obsidian_maintain` checks, what it does
with findings, and what a manager does with the results. Load before running
or interpreting a maintenance pass.

## Who runs it

The **manager profile** (vault-manager). Contributors raise issues; they do
not run the sweep. The manager holds `meta` + `config` + `read` on `**` and
no content `write` — which is exactly why every maintenance task splits into
AUTO (the manager applies it) vs FLAG (needs content judgment → escalate to
the owner).

## Modes

| Mode | What it does | Distribution |
|---|---|---|
| `delta` | Checkpoint over the audit log since the last run (watermark = last processed line; the log stays append-only) | findings → issues |
| `maintain` | Full correctness census: broken links, orphans, stale edges, empty notes, malformed frontmatter, INDEX freshness | findings → issues |
| `optimize` | Suggestions only: duplicates, missed connections, tag normalization, coverage gaps | `nature: suggestion` |

`dry_run: true` reports without distributing. `distribute: false` reports
without touching the ledger.

## What the checks flag

- Broken links and dangling wikilinks (from the graph).
- Orphan notes and stale edges.
- Empty notes and malformed frontmatter.
- INDEX/registry freshness.
- Observed vocabulary past `promote_after_uses` (auto-promoted with the
  `config` grant — a manager action, applied by the sweep).
- Optimization candidates — suggestions only, never auto-applied.

## Lifecycle of a finding

1. Sweep finds it → `obsidian_issue` record with `key = <check>|<path>`,
   `target = path`, `tags: [maintenance]`.
2. Condition clears (sweep re-run) → auto-resolve.
3. Suggestion unanswered for 14 days → auto-decline; resolved records pruned
   after 30 days.

## Manager duties around the sweep

- Read the census (`obsidian_issue_list`) and the audit trail
  (`obsidian_audit`) for anomalies.
- Refresh stale INDEX/registry (`obsidian_index`) — AUTO.
- Curate vocabulary per the reference's promotion rules — AUTO.
- Keep `roles.yaml` and per-tree `.vault/config.yaml` coherent with actual
  growth (`obsidian_scaffold` / `obsidian_edit_config`) — structural
  changes need explicit user confirmation.
- Escalate content-judgement calls to the domain owner — the manager
  maintains, the owner decides.

## Schedule

Installed by the installer on the vault-manager profile: daily 05:00
`maintain`, Monday 06:00 `optimize`. Jobs fire only while the Hermes gateway
is running (`hermes gateway install`).
