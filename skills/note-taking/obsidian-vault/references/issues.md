# Issues

The vault's issue layer: ledger records, not notes. Load before raising,
listing, or resolving an issue.

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

## Raising

`obsidian_issue` with `items: [{subject, detail, target, ...}]` — one or many
at once. Any registered agent may raise; no grant over the target is needed.

- `subject`, `detail`, `target` are required. `target` is the vault-relative
  path of the affected note, or a scope glob like `system/**`.
- Optional: `priority` (default medium), `tags`, and `key` — a custom dedupe
  key. Omit `key` and one is derived from subject + target. Optional
  `assignee` — who should resolve it (see the directive below).
- **The assignee directive — key on grant kind + scope, not domain.** The
  resolution capability is `write` **or** `meta` over the target: a domain
  contributor with scoped `meta` is the natural addressee for its own
  domain; the manager's global `meta` covers anything unowned or
  cross-domain. A read-only observer is never a valid addressee. When the
  target's owner is unambiguous, assign explicitly; when unclear or
  multi-owner, leave unassigned — the manager's triage routes it. The
  fast lookup is your peer/role memory note (it carries each peer's
  domain + grants, verified at session start); roles.yaml is the
  authority when exact grant kind matters. `assignee` is a SHOULD signal,
  never a grant override — a mis-assigned issue simply cannot be acted on
  by the wrong agent.
- The response reports each item as `created`, `exists` (already open), or
  `reopened` (was closed, reopened).

## Listing

`obsidian_issue_list` — current state of every issue you can read, newest
first.

- Filters: `state`, `priority`, `tags`, `target`, `raised_by`,
  `assigned_to` (`me` = your own profile), `limit` (default 50).
- Visibility is grant-intersected at call time: you see only issues whose
  `target` you can read. Census findings from the sweep arrive tagged
  `[maintenance]` — filter on it to see what concerns your domain.

## Resolving

`obsidian_issue_resolve` with `key` — claim it or close it:

- `state: "in_progress"` claims it — you become the holder (`claimed_by`),
  visible to the manager and to anyone listing the ledger.
- `state: "resolved"` or `"declined"` closes it, with an optional `reason`.
- You may act on an issue only when you hold `write` or `meta` over its
  target — issues about your domain are yours to claim/close; anything
  else is refused.
- **`declined` is a permanent owner decision — it sticks.** When you decline a
  suggestion (esp. a `missed_connection`), the engine records the pair in
  `.state/maintenance/declined.yaml` and never re-proposes it; the issue does
  not re-open on the next sweep. So a decline is your standing call as the
  domain owner and needs no further action. Re-opening/re-resolving the issue
  (e.g. after you link the notes) clears that record. Decline only when the
  proposition is genuinely not a connection you want — your judgment of
  utility, not the engine's, decides.
- **A recurring finding correct *by design* for your scope is a
  scope-exemption, not a decline.** When the *check itself* is wrong for the
  whole scope (e.g. `orphan` on a folder-navigated unit), exempt it in your
  scope's config (`obsidian_edit_config`) — that makes the sweep stop raising
  it and auto-resolves the open issues (`scope-exempted`). See the manager's
  `config-authoring.md` §8 for the shape. Use `declined` for a single
  proposition you reject; use `exempt` for a whole class the engine should
  never raise in your scope.
- **Know the test before you exempt or decline.** Exempt/decline only when the
  finding is *structurally correct by design* — e.g. a folder-navigated unit
  whose notes are reached by opening the folder, not by `[[links]]`; or notes
  that are siblings by construction. **If the finding reveals a real gap you
  intend to fix**, do *not* exempt or leave it declined — claim it
  (`in_progress`) and fix the link/note, which closes it honestly. Hiding a
  fixable finding (via exempt or a decline you didn't mean) leaves the gap.
- **Worked example (already in place).** `work/creative/projects/short
  stories/**` and `work/creative/projects/TV Series/the writing is on the
  wall/**` are folder-structured story/project units; their `orphan` findings
  are false positives by design and are exempted at the scope config. A
  `missed_connection` you judge not worth linking is `declined` (recorded
  permanently). The real missed-link/orphan gaps (e.g. in `short film/prova/**`)
  are *not* exempted or declined and stay on the ledger to be fixed.

## Typical flow

1. Spot something wrong (broken link, stale INDEX, missing convention).
2. `obsidian_issue` with `items: [{subject, detail, target}]`.
3. `obsidian_issue_list` (optionally filtered) to track it.
4. When raising, set `assignee` per the directive if the owner is
   unambiguous — otherwise leave it unassigned for the manager's triage.
5. Resolution comes from whoever holds write/meta over the target — the
   sweep for census findings, the owning agent (subdomain owner, else
   domain contributor) for content judgment. Claim an issue you intend to
   handle (`in_progress`); close it yourself when you own the target and
   the call is yours to make.
