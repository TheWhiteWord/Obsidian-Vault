# Maintenance

The manager's sweep: what `obsidian_maintain` checks, what it does with
findings, and how to triage the results. Load before running or interpreting
a maintenance pass.

## Who runs it

The manager profile. Its grants — `meta`, `config`, `read` everywhere, no
content `write` — are exactly why every maintenance task splits into **AUTO**
(the sweep applies it) vs **FLAG** (needs content judgment → escalate to the
domain owner).

## Modes

`delta` runs on every pass; the mode picks what is added on top.

| Mode | What it adds |
|---|---|
| `delta` (always) | Check what changed since the last run's checkpoint (a watermark over the audit log): regenerate INDEX for changed folders, promote observed vocabulary past `promote_after_uses`, flag findings from the change set |
| `maintain` | Full correctness census: broken links, orphans, stale edges, empty notes, malformed frontmatter, INDEX freshness |
| `optimize` | Suggestions only: duplicates, missed connections, tag normalization, coverage gaps — `nature: suggestion`, never auto-applied |

`dry_run: true` reports everything with zero writes (findings plus
would-create / would-suggest counts). `distribute: false` runs the checks but
leaves the ledger alone.

## What a run produces

- **Findings file** — `.state/maintain/findings/<run_id>.jsonl`, the machine
  interface; every finding with its nature and location.
- **Ledger distribution** — findings become issues (`key = <check>|<path>`,
  `target = path`, `tags: [maintenance]`), deduped by key.
- **Lifecycle pass** — auto-resolves findings whose condition cleared,
  auto-declines suggestions unanswered for 14 days, prunes records closed
  more than 30 days.
- **Checkpoint** — advanced only after a full successful run (the watermark
  for the next `delta`).

## The audit trail

Every mutation is appended to `.state/audit-log.jsonl` (JSONL: `ts`, `agent`,
`action`, `path`, plus per-action details) — note mutations (`create`,
`edit`, `edit_meta`, `delete`, `scaffold`) and ledger mutations (`issue_*`).
`obsidian_audit` reads it newest-first, filtered by `agent`, `action`, or
`limit` (default 100). Triage means looking for anomalies: unexpected
actions, wrong paths, agents acting outside their expected scope.

## Manager duties

- **Read the results:** findings file, ledger issues, audit trail.
- **AUTO actions (the sweep applies them):** INDEX regeneration, vocabulary
  promotion — verify, don't redo.
- **Fix within remit:** `obsidian_index` for a folder or the whole vault;
  `obsidian_edit_config` to keep per-tree configs coherent with actual
  growth; `obsidian_edit_metadata` for frontmatter-level fixes (never body).
  Regenerate the registry (`obsidian_index` with `registry_to`) after config
  changes, for a human-readable view of the effective schema.
- **Escalate:** content-judgment findings stay with the domain owner — the
  sweep distributes them; make sure they land as ledger issues.
- **Structural changes** (new contributors, domains, config files) run
  through the growth subcommands — never by hand. Scaffold is not available
  to you: your grants hold no content `write`.

## Schedule

Installed by the installer on the manager profile: daily 05:00 `maintain`,
Monday 06:00 `optimize`. Jobs fire only while the Hermes gateway is running.
