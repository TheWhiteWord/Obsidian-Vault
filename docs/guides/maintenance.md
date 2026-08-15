# Maintenance & the issue ledger

The plugin keeps the vault healthy through two mechanisms: an **issue
ledger** — structured records that surface problems — and a
**maintenance sweep** that detects decay, distributes findings as
issues, and promotes vocabulary. Both are engine machinery: they work
on any vault, need no configuration, and are invisible to the vault's
content surfaces by construction.

## Issues are records, not notes

An issue is a **structured record with a lifecycle**, stored as one
JSON file under `.state/issues/<slug>.json`. It is not a note: it has
no frontmatter, no body, no INDEX entry, no graph node. Because the
ledger lives under `.state/` (in `SKIP_DIRS`), search, the graph, and
INDEX generation never see it — an issue cannot pollute a domain's
results, and the manager never flags its own tickets.

Record fields are engine-fixed:

| Field | Meaning |
|---|---|
| `key` | deterministic dedupe key (`subject|target` slug + hash) |
| `state` | `open` / `in_progress` / `resolved` / `declined` |
| `nature` | `finding` (from the sweep) / `suggestion` (advisory) |
| `priority` | `low` / `medium` / `high` / `critical` |
| `subject`, `detail` | what is wrong |
| `target` | the affected path, or a scope glob like `system/**` |
| `tags` | e.g. `["maintenance"]` |
| `assignee` | who SHOULD resolve (profile name, optional; a SHOULD signal, never a grant override) |
| `claimed_by` | who moved the issue `open → in_progress` (the holder) |
| `raised_by`, `created_at`, `updated_at`, `resolved_by`, `resolved_at`, `reason` | provenance + closure |

Every mutation is recorded in the audit trail
(`issue_create`, `issue_claim`, `issue_assign`, `issue_resolve`,
`issue_prune`), so full history lives there; the ledger file holds current
state only.

## Access — derived from grants at call time

| Operation | Gate |
|---|---|
| **raise** | any registered agent (present in `roles.yaml`) — the escalation valve, audited |
| **list** | the caller's `read` grants intersect the issue's `target` — "my issues" is a query, not a folder |
| **assign / claim / resolve** | `write` **or** `meta` over the `target` — you act on issues about notes you own |

There is no routing table: the issue's `target` *is* the addressee, and
the optional `assignee` is a SHOULD hint on top of it. The domain owner
fixes its domain; the manager (`meta` on `**`) can resolve maintenance
findings; whoever can read a target can see its issues. The assignee
never overrides grants — a mis-assigned issue simply cannot be acted on
by the wrong agent.

## The tools

- **`obsidian_issue`** — raise one or many issues (`items:` array).
  Optional per item: `priority`, `tags`, `key`, `assignee` (who should
  resolve). Duplicate keys are skipped; a closed issue with the same key
  is re-opened.
- **`obsidian_issue_resolve`** — move an issue's lifecycle: route it with
  `assignee=<profile>` (sets who should resolve, state untouched — the
  owner then claims/closes), claim with `state: in_progress`, or close
  with `state: resolved | declined` and an optional `reason`. Assign,
  claim, and resolve share the same grant gate (`write`/`meta` over the
  target).
- **`obsidian_issue_list`** — filter by `state` / `priority` / `tags` /
  `target` / `raised_by` / `assigned_to` (`me` = the calling agent);
  results are grant-intersected.

## The maintenance sweep

`obsidian_maintain` runs the sweep at three depths — the cron schedule
drives the mode:

| Mode | Checks |
|---|---|
| `delta` | checkpoint over the audit log: check only what changed since the last run (and its link-neighbourhood), regenerate INDEXes for changed folders, promote observed vocabulary. Fast; runs every tick. |
| `maintain` | delta + the full correctness census: dangling wikilinks, orphan notes, malformed frontmatter, empty notes, missing required fields, case collisions |
| `optimize` | maintain + quality suggestions: duplicate notes, missed connections, tag normalisation, thin notes. **Suggestions only** — never auto-applied |

The delta checkpoint is a **watermark over the audit log** — the
last-processed line number (JSONL is append-only, so line N is a stable
sequence). The log itself is never truncated: provenance survives, and
a failed run simply reprocesses the same delta (every check is
idempotent). Findings are written to `.state/maintain/findings/<run-id>.jsonl`
and distributed as ledger issues (`distribute: true` by default;
`dry_run: true` rehearses with zero writes).

Lifecycle rules:

- **Dedupe** — the key is the filename: an existing `open`/
  `in_progress` record is skipped, deterministically.
- **Re-escalation** — a condition that clears and recurs re-opens the
  same key; history stays attached to one ticket.
- **Auto-resolve** — when the sweep re-checks its own open findings and
  the condition has cleared, it resolves them with reason
  "condition cleared".
- **Suggestion TTL** — `kind: suggestion` open past 14 days is
  auto-declined ("non-action = implicit decline").
- **Pruning** — resolved/declined issues older than 30 days are
  deleted; the audit log keeps the history.

The manager resolves/declines/prunes **only its own** issues
(`raised_by` = itself); agent-raised issues are the raiser's to close.

## Cron

The setup questionnaire installs the maintenance schedule on whichever
profile the **manager role** is bound to (role-derived, never a
profile name; one-agent installs land on `default`):

- **daily 05:00** — `maintain` mode
- **Monday 06:00** — `optimize` mode

User-requested *content* cron ("every day, note X") is a
manager-skill procedure, not engine machinery — the plugin never learns
about specific workflows.

## Health

The ledger is invisible unless looked for; the tools and the manager's
report are the look-for mechanism. A health report is available on
request from the manager — the issue list grouped by domain and
priority is the human-readable surface of vault health.
