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
(a path or a scope glob), `tags`, `raised_by`, `assignee` (who should
resolve), `claimed_by` (who claimed it), timestamps, and resolution info.

## Rules of the layer

- **Raise ≠ fix.** Filing an issue is an escalation valve, not permission to
  act. Raising succeeds without grants over the target; acting on it is a
  separate, grant-checked step.
- **Access is derived at call time** from grants against the record's
  `target` — no folders, no routing table, no per-domain inboxes. "My
  issues" is a query, not a location.
- **Dedupe by key.** Raising an open key returns the existing record;
  re-raising a **resolved** one reopens it (a genuine regression, history
  kept, priority preserved); a **declined** one stays closed (permanent
  owner rejection).
- **Issues are not notes** — never write them with `obsidian_write`, never
  link them, never expect them in INDEX.

## Triage

`obsidian_issue_list` reaches the whole vault (your `read` covers every
target): current state of every issue, newest first.

- Filters: `state`, `priority`, `tags`, `target`, `raised_by`,
  `assigned_to` (`me` = your own profile), `limit` (default 50).
- The census backlog is the main inflow — sweep findings carry
  `key = <check>|<path>`, `target = path`, `tags: [maintenance]`. Filter on
  the tag to see the backlog; on `target` for one domain.
- **Issues are auto-assigned at distribution time.** The sweep computes the
  derived owner of each finding's `target` (most-specific write glob in
  `roles.yaml`, via `owner_of`) and sets `assignee` on creation — so a
  `system/**` finding lands on `default`, a `work/creative/**` finding on
  `creative`, and so on. Query your own with
  `obsidian_issue_list assigned_to=me`; you should no longer have to scan the
  whole ledger. **Only genuinely ownerless targets** (a path matching no
  ownership glob) stay `null` — that is the residual manager triage job: read
  the target's grants and assign to the capable owner via
  `obsidian_issue_resolve key=<key> assignee=<profile>`, or resolve/decline
  yourself when the call is yours (meta covers every target). An
  `in_progress` issue has a holder (`claimed_by`) — respect the claim; don't
  reassign work someone has taken.
- Pair with `obsidian_audit` for the mutation side (see
  `references/maintenance.md`).

## Raising

`obsidian_issue` with `items: [{subject, detail, target, ...}]` — you raise
structural breakage and triage anomalies instead of silently fixing them.
Target the affected path or a scope glob like `system/**`. The response
reports `created`, `exists`, or `reopened` per item.

## Resolving and declining

> **IMPORTANT — conclude formally.** Deciding an issue in chat is not closing it.
> When you route, claim, or close an issue, call `obsidian_issue_resolve` to set
> the state (`in_progress` / `resolved` / `declined`) — the ledger is the system
> of record, not the conversation. An issue left `open` after you've moved on just
> clutters the next sweep and hides what still needs a holder.

`obsidian_issue_resolve` with `key` — claim (`in_progress`) or close
(`resolved` / `declined`), with an optional `reason`. Your `meta` grant
covers every target, so any issue is actionable.

- `resolved` when the condition cleared. The sweep auto-resolves its own
  findings; manual resolution is for what it cannot see.
- `declined` is for a **single rejected *pair* proposition** — and only
  records to the suppression store when the proposition carries a `partner`
  (a `missed_connection`). For a partner-less suggestion (e.g. `duplicate`,
  `thin_note`), declining closes the issue but writes **nothing** to
  `.state/maintenance/declined.yaml`; the finding still recomputes on every
  sweep and is only held back by the `create_issue` declined-guard. That is
  a leak, not a record — do **not** treat decline as "the engine now
  knows." So: decline only a proposition you reject **and** that has a
  partner; for everything else, exempt (next bullet).
- **A whole-class / N-way / by-design-for-scope finding is a scope-`exempt`,
  never a `declined`.** When the *check itself* is wrong for the whole scope
  (e.g. `duplicate` of identical entry-point `00-overview` titles across
  subdomains, `orphan` on a folder-navigated unit, an intentional
  `tag_normalization` variant, a deliberately short `thin_note` stub), exempt
  it in the scope config (`obsidian_edit_config`) — the sweep stops raising
  it at generation and auto-resolves open issues (`scope-exempted`). See the
  manager's `config-authoring.md` §8 for the shape. **Rule of thumb: decline
  = one rejected *pair* (a `missed_connection`); exempt = any proposition
  with no `partner` (`duplicate`, `tag_normalization`, `thin_note`) or a
  whole class the engine should never raise in your scope. If declining it
  would write nothing to `.state/maintenance/declined.yaml`, it leaks —
  exempt instead.**
- `in_progress` claims the issue (sets `claimed_by`) — use it when you are
  actively handling one, so the ledger shows who holds it.
- Content judgment stays with the owning agent (the subdomain owner for
  `knowledge/` findings, else the domain contributor): when closing would
  mean deciding content for someone else's tree, escalate instead of
  deciding.

## The sweep in the ledger

The sweep files findings, auto-resolves cleared conditions, auto-declines
suggestions unanswered after 14 days, and prunes records closed after 30
days. Your cron runs it daily (`maintain`) and Monday (`optimize`) — full
mechanics in `references/maintenance.md`.
