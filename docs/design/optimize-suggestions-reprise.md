# Design note — optimize suggestions and the reprise problem

Date: 2026-08-15
Raised by: user (system owner) · status: open decision, not yet engine-changed

## The observation

`optimize` suggestions (`duplicate`, `missed_connection`, `tag_normalization`,
`thin_note`) are generated fresh every weekly run over the *whole* vault. The
ledger dedupe by `key` means each suggestion keeps ONE record, but that record
re-opens / recurs forever unless resolved. The resolution paths are:

- **fix** — the content changes; auto-resolve closes it (`condition cleared`).
- **decline** — `reason` recorded, auto-declines after the 14-day TTL.
- **exempt** — the scope declares it by-design; auto-resolves immediately
  (`scope-exempted`).

With a small vault and a high-yield heuristic (the current `missed_connection`
shares-≥2-tags rule produces ~52 suggestions in one run across two
subtrees), the ledger fills fast and, because a `declined` suggestion does not
prevent the *same* heuristic from re-firing next week, the same propositions
keep returning. The user's concern: the system "keeps presenting the same
propositions unless it learns a generalized rule," and a generalized rule
risks going stale as the vault grows and wrongly suppressing real
optimization.

## Diagnosis

The concern is correct *in part*. Two separate things are conflated:

1. **Noise that recurs because it is by-design.** Genuinely by-design
   suggestions (e.g. project siblings sharing structural tags) SHOULD become
   an `exempt`, not be declined repeatedly. That is already the durable
   mechanism; the gap was that the heuristic itself was too loose (see
   `missed_connection` fix, separate note). An `exempt` is a *scoped,
   human-authored* rule — it does not "learn" and does not go stale silently
   because it is visible config, not an emergent model.

2. **Noise that recurs because the heuristic is weak.** This is a *heuristic
   defect*, not a ledger defect. Fixing the heuristic (drop non-discriminating
   shared tags within a top-level scope) removes the class of noise at the
   source. It does not need a "learning" layer.

The user's worry about "learning a generalized rule that becomes wrong" is a
real risk **if** we tried to auto-derive standing rules from declines. We
should NOT. The engine has exactly two durable memory mechanisms and both are
human-authored and visible: `maintenance.exempt` (suppress a check for a
scope) and `vocabulary` promotion (observed tag → declared). Neither is an
auto-learned optimization rule. Keeping it that way is the right call: a
growth-vault's notion of "a good connection" is too unstable to bake into a
standing rule automatically.

## Recommendation (proposed, not yet applied)

- Treat optimize suggestions as **advisory signal, not recurring obligations**.
  The 14-day auto-decline already encodes "non-action = implicit decline";
  the fix is to make that *legible and final* in the contributor guidance so a
  decline is understood as "no, and don't keep asking" rather than a temporary
  dismiss.
- Prefer **fixing weak heuristics over exempting per scope**. Exempt only when
  the structure is genuinely by-design (folder-navigated units), never to
  blanket-hide a heuristic that is merely noisy on one subtree.
- Do NOT build an auto-rule-learner from declines. If a pattern recurs across
  many scopes, that is evidence the heuristic should be widened — a one-line
  engine change + test — not a per-decline memory.
- Keep `missed_connection` strictly as a *link* prompt. Content-level
  "should these two notes be connected" is out of scope for a mechanical
  sweep and belongs to the human/agent editor; the engine should not presume
  to know it.

## Resolution (2026-08-15) — IMPLEMENTED

The fix shipped as a deterministic, visible rule in `vault/maintain.py`
(`_project_unit` + `_pervasive_tags`, used by the `missed_connection` branch of
`run_suggestions`):

- **Comparison universe:** notes within the same top-level tree (original
  behaviour) — so genuine resonance ACROSS projects (e.g. a theme tag shared by
  two different stories) still surfaces. This directly answers the owner's
  "is finding new connections an overreach" concern: cross-note resonance is
  preserved, only the boilerplate is dropped.
- **Noise filter:** a shared tag is dropped only when it is pervasive *within
  both notes' own project unit* — i.e. a project/section label every note in
  that project wears (e.g. `tv-series` on 24/24 TV-Series notes). Deterministic
  thresholds (`MISSING_CONNECTION_PERVASIVE_RATIO = 0.20`,
  `MISSING_CONNECTION_PERVASIVE_MIN = 2`), **not learned** — a fixed, testable
  rule, so it cannot go stale and silently suppress real optimization the way
  an auto-learned standing rule would.
- **Result on the live vault:** `missed_connection` suggestions fell from ~52
  across the two subtrees to **6** total — TV Series 22→0, short stories
  30→3, prova 24→0. The 6 survivors are specific content resonances (a `comfyui`
  handbook cluster; `01-territory` record notes sharing specific tags with
  sibling stories), none are project/section boilerplate. Regressed-guarded by
  `tests/test_missed_connection.py` (500 tests pass suite-wide).

## Declined propositions are permanently recorded (2026-08-15) — IMPLEMENTED

The second half of the reprise problem: a *rejected* suggestion must not
re-raise and force re-assessment on every sweep. Implemented in
`vault/issues.py` + `vault/maintain.py`:

- A `declined` suggestion records the pair in a single vault-wide store,
  `.state/maintenance/declined.yaml` (dict `note -> [partners]`), both ways.
  The engine loads it **once per sweep** and does O(1) per-note lookups, so
  vault growth adds no per-proposition scan cost (owner's scale concern).
- `run_suggestions` skips any `missed_connection` pair present in the store —
  the proposition is never emitted, so no agent re-assesses it.
- `declined` is permanent: `create_issue` no longer re-opens a declined record
  (only a `resolved` one re-opens on a genuine regression). `auto_resolve`
  flips an aged, un-actioned suggestion to `declined` (implicit permanent
  rejection), and an owner's explicit `declined` writes the store. Re-opening
  or resolving the issue clears the store entry (e.g. after the owner links
  the notes), so the record self-heals when the condition changes.
- The decision is the **domain owner's** (not the human's): he declines via
  `obsidian_issue_resolve`, grant-checked over the target. No soft/hard split —
  a decline is just a durable rejection. Documented in the contributor
  `issues.md` protocol.

This is consistent with the earlier "no auto-learned rules" stance: a decline
is an **explicit, owner-authored, per-pair, visible** record — not the engine
inferring a general rule from behaviour.

## What was deliberately NOT done

- **No auto-rule-learner from declines.** (As above.)
- **No per-scope `exempt` for `missed_connection`.** The heuristic fix removes
  the class of noise at the source; per-scope exemptions would just whack-a-mole
  each new project folder.
- **No soft ("not now") rejection state.** Owner's call: a rejection is durable
  by nature; there is no temporary-decline mode.
- **`optimize` cadence (weekly vs on-request) left as a separate decision** —
  the suggestion itself is now low-noise enough that the cadence is a question
  of preference, not necessity.

