# 05 — Vault maintenance & the ISSUE layer (P4 design)

**Status: FINAL design (2026-08-04).** v4 adopts the **issue ledger**: issues
are *structured records*, not notes — JSON files under `.state/issues/`,
invisible to the vault by construction, accessed only through tools.
Universal engine mechanism (like the audit trail), zero config, zero grant
changes. Replaces the v3 board-with-trays + `channels:` table design, which
was rejected because issues-as-notes pollutes domain search/graph/INDEX.

**Related:** `01-vault-v2-model.md` (§3.7 vocabulary, §6 state), `TASKS.md` P4,
`03-design-decisions.md` (D1, D2, D7, D8, D9), `04-installation.md`.

---

## 0. The constraint that shapes everything

The vault-manager is a **census + report + escalation engine**: it detects,
reports, and raises issues; it never edits content. Its grants are **unchanged
by P4** — no new grants needed:

| Grant | Scope | Why |
|---|---|---|
| `read` | `**` | see everything |
| `meta` | `**` | vocabulary promotion, resolve its own issues |
| `config` | `**` | vocabulary promotion |

The ledger lives under `.state/` — engine machinery, written by the engine
exactly like `audit.record`. No grant governs machinery; grants govern
*content*, and the ledger is not content. **Zero roles.yaml changes.**

---

## 1. The ISSUE ledger — records, not notes

**An issue is a structured record with a lifecycle, not a note.** A note is
content: frontmatter, body, links, INDEX entry, graph node, vocabulary member.
Every note-like feature (INDEX, graph, registry, validation) actively fights
being applied to tickets. Issues are *meta* — about the vault, not part of it.

### Location & format

- One small JSON file per issue: **`.state/issues/<filename>.json`** —
  `<filename>` is a deterministic slug of the issue **key** (`type|path`,
  e.g. `dangling|work/creative/projects/a.md`) with a short hash suffix.
- **Current state only.** Full history lives in the audit log: every issue
  mutation is recorded (`issue_create`, `issue_resolve`, `issue_prune`) with
  `path` = the issue's target — provenance without extra bookkeeping.
- Record shape (engine-fixed, layout-independent):

```json
{
  "key": "dangling|work/creative/projects/a.md",
  "state": "open",                 // open | in_progress | resolved | declined
  "kind": "finding",               // finding (B1) | suggestion (B2)
  "priority": "medium",            // low | medium | high | critical
  "subject": "[dangling] work/creative/projects/a.md",
  "detail": "Links to [[Missing Note]]",
  "target": "work/creative/projects/a.md",   // path or scope glob (e.g. "system/**")
  "tags": ["maintenance"],
  "raised_by": "vault-manager",
  "created_at": "2026-08-04T10:00:00Z",
  "updated_at": "2026-08-04T10:00:00Z",
  "resolved_by": null,
  "resolved_at": null,
  "reason": null                    // closure reason (resolution/decline)
}
```

### Why not notes

- **Pollution.** `obsidian_search("api")` in `work/coding` must return
  knowledge, not tickets. A note-based issue layer lands in every INDEX, the
  graph, the registry, and the census's own checks — the manager would
  eventually flag its own issue notes (self-flagging loop). The ledger is
  under `.state/` (in `SKIP_DIRS`), so `iter_notes` / `build_graph` /
  `generate` / `search` never see it. **Zero pollution, by construction, with
  no special-casing.**
- **Invisibility is the feature.** "A layer invisible unless it is looked
  for" — looked for = the tools. This was the design decision that flipped
  v3: issue visibility in the domain is pollution, not navigation.

### Why universal

The manager/contributor structure exists wherever the plugin runs, so the
escalation channel is always useful — it is *derivative* of the grant model.
Therefore it is **engine machinery, like the audit trail**: `ISSUES_DIRNAME`
joins `STATE_DIRNAME` in `constants.py`, `ISSUES` joins `STATE`/`VAULT` in the
portability test's reserved names. No starter config enables it; it works on
any vault (including a PARA vault with `category`/`format`/`owner` fields —
the record schema is engine-fixed and layout-independent).

---

## 2. Access — at call time, derived from grants

**No folders, no trays, no routing table.** The issue carries `target` (the
affected path, or a scope glob for tool-level issues). Everything derives from
grants at call time:

| Op | Gate | Who |
|---|---|---|
| **raise** | any registered agent (audited: `raised_by`) — the escalation valve | any agent |
| **list** | caller's `read` grants match the issue's `target` | "my issues" = "issues whose target I can read" |
| **resolve** | caller holds `write` **or** `meta` over `target` | domain owner fixes its domain; manager (`meta **`) closes its own |

Consequences:

- `work/creative/knowledge/z.md` issue → visible to `creative` (reads
  `work/creative/**`) *and* `researcher` (reads `work/*/knowledge/**`) — the
  knowledge ambiguity dissolves: whoever can read it can see it, whoever can
  fix it (`write`/`meta`) can resolve it.
- The manager's distribution needs **no routing config**: the finding's path
  *is* the target. The `channels:` table of v3 is gone.
- A custom vault names nothing — there are no names to configure.

---

## 3. A. The delta pass — change-driven checking

**Design: a checkpoint over the audit log — never mutate the log.**

- The audit log (`.state/audit-log.jsonl`) **stays append-only**: crash-safe
  by construction, and the provenance record the ISSUE layer wants. Truncating
  it once entries are "checked" destroys that.
- The manager keeps **one small state file** in `.state/maintain/`: the
  **last-processed line number** of the log (JSONL is append-only, so line N
  is a stable sequence — better than a timestamp watermark).
- Each run: entries after the watermark → change set (path + action:
  `create`/`edit`/`edit_meta`/`delete`/`scaffold`) → **expand to
  link-neighborhoods** (a created note may resolve a previously-dangling link;
  a deleted note's former linkers now dangle) → check only that set. Issue
  actions (`issue_*`) are excluded — they mutate the ledger, not notes.
- **Advance the watermark only after a full successful run.** A failed pass
  reprocesses the same delta — safe, because every check is idempotent.
- The "ever-growing list" is solved by derivation: the work set is *computed*
  from the log each run. Nothing accumulates.
- **External-edit gap, accepted:** the log sees only plugin-originated
  changes; a human editing in Obsidian directly is invisible to the delta.
  Accepted for now (agents are the writers); the checkpoint design leaves
  room for a future mtime/hash supplement.

---

## 4. B. Maintenance & optimization

### B1. Maintenance (correctness — things not as intended)

| Check | Source | Action |
|---|---|---|
| Dangling wikilinks | `graph.dangling` | finding + issue; fix is content judgment → domain agent |
| Orphans (zero in/out, excl. generated) | graph | finding (may be intentional: seeds, archive) |
| Stale edges to deleted notes | graph | finding — graph is derived, nothing to prune |
| Malformed frontmatter | note errors / INDEX "Needs attention" | finding + issue |
| Empty notes | note body empty | finding + issue (delete is content judgment) |
| INDEX freshness | folders in the change set | **AUTO**: regenerate |
| Vocabulary: promote observed | `derive_vocabulary` + `promote_after_uses: 3` / `promote_after_days: 14` | **AUTO**: `config` grant |

### B2. Optimization (quality — suggestions for the domain agent)

**All FLAG-only. The manager proposes; the domain agent disposes.** Every
suggestion is `kind: suggestion` — the auto-close policy treats it
differently (see §5.2).

- Duplicate notes — title/tag overlap + mutual links → merge candidates.
- Missed connections — same-domain notes sharing tags/terms with no wikilink.
- Tag normalization — `philosophy` vs `Philosophy` → merge suggestion.
- Coverage gaps — e.g. a knowledge note missing `source`/`retrieved`.
- Wording / coherence — explicitly out of manager scope; flag.

A4 stands: deterministic signals only. No embeddings, no BM25, until
measurement says the cheap signals are insufficient.

---

## 5. C. Distribution & the issue lifecycle

### 5.1 Findings artifact (machine interface)

One file per run: `.state/maintain/findings/<run-id>.jsonl` — one JSON object
per FLAG item:

```json
{"type": "dangling", "path": "work/creative/projects/a.md", "severity": "medium",
 "detail": "Links to [[Missing Note]]", "suggestion": "Create the target or remove the link"}
```

The manager session reads this (it is the agent); the distributed issues are
the *agent-facing* surface. `.state/` is in `SKIP_DIRS` — no INDEX, no graph,
no other profile ever touches the raw findings.

### 5.2 Distribution & lifecycle (engine helpers in `vault/issues.py`)

- **Create** — each finding becomes an issue record via `create_issue`:
  `key = type|path`, `target = path`, `tags: [maintenance]`, `kind` from B1/B2.
  Batch: `obsidian_maintain mode=optimize distribute=true` raises N issues in
  one call.
- **Dedupe** — the key is the filename: if a record exists with state
  `open`/`in_progress`, skip (deterministic, O(1), no fuzzy search).
- **Re-escalation** — if the same key exists with state `resolved`/`declined`
  and the condition recurs, **re-open the same key** (state → `open`, history
  stays attached to one ticket). Dedupe and re-escalation are the same
  mechanism.
- **Closure** — two paths: a domain agent fixes the note and resolves
  (`obsidian_issue_resolve`, gated on `write`/`meta` over target); or the
  manager's next sweep re-checks its open findings and finds the condition
  cleared → auto-resolve with reason `"condition cleared"`.
- **Auto-close of suggestions** — `kind: suggestion` open past a TTL
  (engine constant, 14 days) → auto-decline (`"non-action = implicit
  decline"`). Suggestions must not accumulate forever.
- **Pruning** — resolved/declined issues older than a TTL (engine constant,
  30 days) are deleted by the sweep. The audit log keeps the full history;
  deleting the current-state file loses nothing.
- The manager resolves/declines/prunes **only its own** issues
  (`raised_by` = itself, `tags: [maintenance]`). It never touches
  agent-raised issues.

---

## 6. D. Agent-raised issues (the tools ARE the layer)

Because issues are no longer notes, there is no fallback surface — the tools
are the layer, so they ship now:

- **`obsidian_issue`** — raise one or many issues (`items:` array — the
  manager's batch). Fields: `subject`, `detail`, `target`, `priority`,
  `tags`, `key` (optional; derived from `subject`+`target` when omitted).
  Gate: any registered agent; audited.
- **`obsidian_issue_resolve`** — close (`resolved`/`declined`) with `reason`.
  Gate: `write` or `meta` over `target`.
- **`obsidian_issue_list`** — filter by `state`/`priority`/`tags`/`target`;
  returns only issues the caller can read (grant intersection on `target`).
- **`obsidian_maintain`** — the sweep: `mode: delta | maintain | optimize`
  (cron drives the mode — one tool, not three), `distribute: bool`,
  `dry_run: bool`.

What remains for later (recorded, never designed from zero):

- *convention* — what a good issue contains (subject, detail, reproduction,
  owner); lives in the skill + soul.md per profile;
- *exposure* — a `soul.md` directive per profile: "vault or tool issue you
  cannot fix → raise it; plugin/system issue → target `system/**`";
- *routing* — domain issue → domain agent; plugin/tool issue → `default`;
  vault-hygiene issue → vault-manager (which consumes raised issues as its
  next run's change set — the loop closes);
- the "plugin as vault knowledge" idea closes the dev loop: `work/coding/
  knowledge/` holds plugin-architecture notes so `dev` resolves plugin issues
  without new tooling.

Cron cadence: **daily `maintain`** (delta always first), **weekly
`optimize`** — confirmed with Davide. The vault-manager profile invokes it on
schedule; its skill (`obsidian-vault-management`) holds judgment + escalation rules.

---

## 7. Human visibility (DEFERRED — not built now)

The ledger is invisible unless looked for; the tools + manager report are the
look-for mechanism. **Agents need nothing more.** For the human (Davide), a
future task: generate a **derived issue board note** (e.g. `system/ISSUES.md`
or a `.state`-adjacent generated file — placement TBD) regenerated each sweep,
listing open issues grouped by domain/priority. Marked generated, excluded
from the manager's own checks. This is purely cosmetic-for-human; design and
build when the ledger is stable. Recorded in TASKS.md.

---

## 8. Standard-state changes (ship in the starter, reach the live vault via installation)

1. **Starter tree** — remove the three `*/issues/` folders and the
   `issues-channel` config copies (vestigial once issues leave the notes
   world).
2. **Roles** — remove every agent's `append: ["**/issues/**"]` line (dead:
   the ledger is machinery, not content). The `append` grant *kind* stays in
   the engine (universal), just unused by the standard install.
3. **Portability test** — add `ISSUES` to reserved names (alongside
   `STATE`/`VAULT`); the engine's `ISSUES_DIRNAME` constant is now
   legitimate machinery. Engine stays free of policy names; the record schema
   fields (`state`, `priority`, `target`, …) are generic.
4. **Tests** — fixtures lose the note-issue folders; issue tests use a
   synthetic ledger under the fixture's `.state/`.

The live vault reaches this by a **clean re-install from zero** (the standard
pattern; it is still nearly empty — README + one generated INDEX — so the
wipe is cheap). `maintenance_status` annotation is **dropped** — the issue
record IS the flag.

---

## 9. Open items after build

1. Human-visible board (deferred — see §7).
2. Pruning/suggestion TTLs as config vs constants (currently engine
   constants; promote to config when a vault asks).
3. External-edit supplement to the delta pass (mtime/hash) — only if
   human edits in Obsidian become common.
