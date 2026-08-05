# TASKS — skill split: obsidian-vault ↔ obsidian-vault-management

Goal: replace the single role-routed skill (with role directives `contributor.md` /
`manager.md`) with two role-owned skills. Kill the role-directive machinery; fold
role content into each SKILL.md; prune references of cross-contamination and
historical noise; simplify SOUL.md sections. Dev-facing docs (engineering skill)
cleaned of the obsolete machinery.

## Principles (apply to every file)

1. **One file at a time** — in the order below, never in batches, never copy-paste
   from the old files. Each file is reviewed before the next starts.
2. **Audience first** — every file is owned by contributor | manager | both.
   No cross-contamination.
3. **Tool-first** — if a tool exposes it, don't document it; say "use the tool".
4. **Upstream-once** — a concept expressed in SKILL.md is not repeated in a
   reference, and never in two references.
5. **No history** — state current truth. No "used to be X / replaced by Y / this is
   not X, it's Y". If it doesn't exist, it doesn't get a sentence.
6. **Tight** — expose the nuance, not the explanation.

## Per-file checklist (run for each file)

- [ ] Audience assigned (contributor / manager / both)
- [ ] Every statement verified against the real tool/engine (run it, read the code)
- [ ] No duplication with upstream or siblings
- [ ] No historical baggage
- [ ] No cross-contamination
- [ ] Indexed in its skill's References section (or deliberately excluded)
- [ ] Concise: nuances exposed, padding removed
- [ ] **No meta-commentary:** the skill states its own duties only — no install
      mechanics, no other-role routing, no developer-repo talk ("edit in the
      plugin repo"). Other roles are mentioned only when they affect the
      agent's own action (seldom).

## Phase 0 — decisions (LOCKED 2026-08-05)
- **D1 conventions_ref: REMOVE — confirmed.** Field, `_role_directives`,
  `conventions.skill` config key (+ its entry in `vault/reference.py`), and the
  `_CONVENTIONS_REMINDER` in `vault/schemas.py` (it names conventions_ref —
  reword, don't just delete the field).
- **D2 placement:** `skills/note-taking/obsidian-vault/` +
  `skills/note-taking/obsidian-vault-management/`. No collision (v1 legacy lives
  at `note-taking/obsidian`). Phase 1–2 edits happen in place; the git mv runs
  in Phase 3 with the setup.py path updates.
- **D3 shared references: SPLIT — confirmed, with the "less depth" rule.** Each
  file gets a per-role owner. When both roles need a topic, each gets its own
  slice at the depth its role requires — e.g. issues: contributor owns
  raise/list in depth; manager owns triage/resolve/sweep in depth, and a
  shallower raise slice only if it genuinely needs one. Duplication only for
  slices both roles use identically (tool-protocol refusal semantics).
- **D4 task file location:** `specs/` — confirmed.

## Phase 1 — contributor skill (`obsidian-vault`)

1. **SKILL.md — DONE (2026-08-05, amended after Davide review).** New structure:
   When to use (contributor duties only — no manager-skill mention) → The
   writing loop (context → manifest-registered conventions → write; no
   conventions_ref) → Tool routing (12 tools, no obsidian_maintain) → Knowledge
   layout (bare minimum: bundled files do-not-modify, no repo/copy-on-write
   talk) → Writing rules (from contributor.md, before/while/after, count-free
   required fields — schema comes from context) → Maintaining conventions (what
   goes in / what doesn't / propose-confirm-record) → References index (5 files;
   maintenance.md excluded, manager-owned) → Verification → Pitfalls. Frontmatter
   bumped to 2.0.0 + related_skills: [obsidian-vault-management].
   **Verified finding:** spec 06 has NO divergence semantics (zero "diverge"
   hits) — the split into per-folder convention files is an undocumented LLM
   step, no subcommand creates a second file. SKILL.md now states the intended
   model (default one `<vault>-conventions.md`; divergent folder gets its own
   file, deliberate, registered in the manifest). Possible Phase 3 addition:
   a `--add-conventions`-style mechanic — DECIDE.
   **References index wording is provisional** — final reconcile after tasks
   2–7 (Davide: the audits decide what belongs in the index).
2. `references/obsidian-formatting.md` — **DONE (2026-08-05).** 66 → 45 lines.
   Cut: "immutable reference" title (meta), "taxonomy" (v1 language → folder
   vocabulary), "drift the manager must clean" (role-mention), the dangling-
   link bullet (duplicated in SKILL.md after-writing), the "invent a tag —
   note it for canonization" overlap (SKILL.md owns it). Corrected: "description
   shown in INDEX" → only when the folder config names it `summary_field`
   (generate.py:112). Verified: body `#tags` not indexed (notes.py:119 — tags
   from frontmatter only); validation modes blocking/advisory (constants.py).
   Structure: Wikilinks / Embeds / Callouts / Tags / Frontmatter / INDEX.
3. `references/tool-protocol.md` — **DONE (2026-08-05).** 89 → 34 lines.
   Verified: refusal codes REAL (permission_denied / validation_failed +
   did_you_mean — `__init__.py:_dispatch`, NOT in vault/ — verification
   pitfall: grep the whole engine, not just vault/); enforcement order;
   any-grant index gate; silent grant filtering. Corrected: obsidian_context
   needs NO grant (reports your grants — "Needs: read" was wrong). Deleted:
   conventions_ref section (D1), grant-kind table (tool-first →
   obsidian_reference), Agent resolution (installer machinery), generated-
   marker line (duplicated in obsidian-formatting.md). Surface table →
   compact grouped tool-requirements list (12 contributor tools; purposes live
   in SKILL.md — upstream-once). Shared slices for the manager bundle
   (task 12): refusal semantics, enforcement order, scope globs.
   **Completeness verified (2026-08-05, Davide):** 15 registered tools, 1:1
   with schema constants; contributor reference lists 14 = all but
   obsidian_maintain (manager grants — no contributor value); no typos, no
   phantoms.
4. `references/config-authoring.md` — **DONE (2026-08-05).** 142 → 133 lines.
   Deleted: `conventions` top-level row (D1); the per-field `default` merge
   row (INVENTED — merge_configs has no per-field default; defaults are
   top-level only); "check obsidian_reference" on `scopes` (tool doesn't list
   it — fixed to "reserved — merged but unused"). Corrected: `vocabulary` row
   → `promote_after_uses` only (`promote_after_days` is DEAD in the starter —
   zero engine reads, flagged for starter cleanup); root anchor example →
   real starter (paths/summary_field/vocabulary, no conventions); roles.yaml
   rows reworded neutral (no manager mention, "changed by the growth
   protocol, never by hand"); search/graph implication row tightened (config
   never widens read access). Verified: KNOWLEDGE example exact match;
   promote_after_uses real (maintain.py:301); scopes merged-but-unused
   (config.py:162). SHARED file (both roles need identical DSL semantics —
   D3 exception; duplicate into manager bundle, task 12). Phase 3 gap: the
   intro claims obsidian_reference is the authoritative option list but
   CONFIG_OPTIONS covers only 5 keys — EXTEND reference.py CONFIG_OPTIONS
   to the full top-level DSL (task 14).
5. `references/issues.md` — **DONE (2026-08-05, contributor slice).** 53 → 48
   lines. Full engine understanding first (issues.py + tool layer + schemas +
   sweep) — shared system mapped before changes (Davide's care requirement).
   Corrected: `nature:` in the raise example (NOT a tool parameter — silently
   ignored; human issues are always findings, only the sweep sets suggestion);
   "reopens with a new priority" (reopen PRESERVES priority — create_issue
   keeps the record's); role-neutral phrasing; title. Structure: Ledger /
   Rules / Raising (payload + result codes created|exists|reopened) / Listing
   (filters + grant-intersected visibility + [maintenance] tag) / Resolving
   (write|meta over target, declined+reason) / Typical flow. SHARED CORE
   (Ledger + Rules) defined here — reused VERBATIM in the manager slice
   (task 10). Manager slice additions at task 10: full-scope triage, sweep
   keys `<check>|<path>` as triage handle, resolve/decline, TTLs, escalation
   principle, maintenance.md pointer.
6. `references/growth-protocol.md` — **DONE (2026-08-05): FOLDED + REMOVED.**
   Contributor slice was thin (§1 add-subdomain row, §2 subdomain flow, 3
   pitfall lines) — folded into SKILL.md as "Growing your domain"
   (propose→confirm→execute, scaffold proposal, --add-subdomain registration
   with refusal conditions + --dry-run, divergent-rules conventions file).
   Reference DELETED from the contributor bundle (git history preserves it).
   Stale content found: `DESK/specs/06` path, `contributor.md — role
   directive` in the manifest example, "combined skill role (both directive
   files)" — all died with the split. Manager version (task 11) rebuilds from
   git history: add-contributor, add-domain, setup questionnaire, role
   table, pitfalls — cleaned of the staleness.
7. `templates/vault-conventions.md` — **DONE (2026-08-05).** Deleted the
   `conventions: {skill: ...}` wiring sentence (D1 — file is registered via
   the SOUL manifest, created by ensure_conventions_file with <Vault name>
   substituted); merged "Conventions" + "Style" → "Style & structure" (the
   Rules/Conventions split was the terminology muddle Davide flagged);
   "five required frontmatter fields" example → count-free (schema comes from
   context). Intro trimmed to mutable/grows/keep-tight — no mechanism.
   No migration concern: template seeds new files only; live vault has none.

**PHASE 1 COMPLETE (2026-08-05).** Contributor bundle: SKILL.md (rewritten,
2 review amendments, "Growing your domain" added), 4 references (formatting,
tool-protocol, config-authoring, issues), template. Remaining Phase 1
reconcile: SKILL.md References index final wording — already matches the 4
files; recheck after Phase 2 in case issues/tool-protocol wording needs the
manager-slice view.

## Phase 2 — manager skill (`obsidian-vault-management`)

Created at FINAL location `skills/note-taking/obsidian-vault-management/`
(new dir — inert until Phase 3; only the contributor bundle gets git mv'd).
Manager grant shape verified from both presets: `meta/config/read` on `**`,
NO content write → manager CANNOT use obsidian_scaffold (create op → write
kind) — manager.md's and maintenance.md's "obsidian_scaffold for structural
changes" claims are WRONG (structural work = growth subcommands +
obsidian_edit_config); manager CAN use obsidian_edit_metadata (edit_meta op
→ meta kind, verified in write.py).

8. **SKILL.md — DONE (2026-08-05).** New file: When to use (management only —
   no other-skill mention) → The management loop (context → sweep → triage →
   act) → Tool routing (12 manager-usable tools: context, maintain, index,
   audit, edit_metadata, edit_config, search, graph, reference, issue*;
   excluded: write/delete/scaffold) → Remit (maintain don't author: AUTO vs
   escalate vs raise-don't-silently-fix vs never-by-hand) → References (5:
   maintenance, issues, growth-protocol, tool-protocol, config-authoring) →
   Verification → Pitfalls. No conventions section — manager doesn't maintain
   conventions.
9. `references/maintenance.md` — **DONE (2026-08-05).** Written at the manager
   bundle (final location); old copy removed from the contributor bundle.
   Engine-verified: delta ALWAYS runs (INDEX regen + vocabulary promotion +
   change-set findings — old file's modes table was thin); findings file
   `.state/maintain/findings/<run_id>.jsonl`; lifecycle pass (auto-resolve,
   14d decline, 30d prune); checkpoint advanced only after full success;
   dry_run/distribute semantics; audit schema (limit/agent/action). Fixed:
   scaffold claim (manager holds no write — structural work = growth
   subcommands). NEW: "The audit trail" section — the P4 audit was never
   documented (Davide's gap call); registry regen via `obsidian_index
   registry_to`.
10. `references/issues.md` — **DONE (2026-08-05, manager slice).** Shared core
    (Ledger + Rules) reused VERBATIM from the contributor file. Manager depth:
    Triage (full-vault list, census backlog via key=<check>|<path> +
    [maintenance] tag, audit pairing) / Raising (structural breakage pattern,
    scope-glob targets) / Resolving & declining (meta covers all targets;
    honest reason; content judgment stays with the owner — escalate) / The
    sweep in the ledger (one-line TTLs + pointer to maintenance.md — no
    duplication). No contributor-flow content.
11. `references/growth-protocol.md` — **DONE (2026-08-05).** Rebuilt at the
    manager bundle from the preserved original (git history). Manager content
    only: who-may-do-what table, --add-contributor, --add-domain (verified
    against setup.py:1075–1146), the stage-machine questionnaire (stages,
    create|default|existing:NAME, standard|blank, relay-only), pitfalls.
    Cleaned: DESK path, role-directive mentions, "combined skill role (both
    directive files)" → "both skills plus unioned grants", P5d dates. The
    subdomain flow stays contributor-side (SKILL.md "Growing your domain").
12. `references/tool-protocol.md` + `config-authoring.md` — **DONE (2026-08-05).**
    Manager tool-protocol: 12-tool surface + shared slices verbatim (refusal
    semantics, enforcement order, scope globs) + one boundary line (write-
    gated tools not in remit → growth subcommands). config-authoring copied
    verbatim (shared DSL).

**PHASE 2 COMPLETE (2026-08-05) — coverage gate PASSED.** Script-verified:
manager 12/12 tools covered (SKILL.md or references); manager index ↔ disk
exact match (5 files); contributor index ↔ disk exact match (4 files). Only
leftovers: conventions/contributor.md + manager.md (removed in Phase 3).

**PHASE 2 GATE — manager coverage matrix (Davide 2026-08-05):** before Phase 2
closes, every one of the manager's 12 tools must be covered (routing or a
reference), and every manager-relevant engine behavior accounted for — new
references are allowed if something implemented was never documented (audit
trail was the first catch; check remaining: registry rendering, maintain
schedule, issue TTLs, config coherence). Matrix: context ✓ (SKILL.md) ·
maintain ✓ (maintenance.md) · index ✓ (maintenance.md) · audit ✓
(maintenance.md §audit) · edit_metadata ✓ (maintenance.md) · edit_config ✓
(maintenance.md + config-authoring) · search/graph ✓ (routing) · reference ✓
(routing) · issue/issue_list/issue_resolve → issues.md (task 10).

## Phase 3 — engine/installer (code follows docs)

13. `scripts/setup.py` — **DONE (2026-08-05, split machinery).** ROLE_FRAGMENTS
    → ROLE_SKILLS + SKILL_BUNDLES; install_skill → install_skills (role owns
    the skills: contributor→obsidian-vault, manager→obsidian-vault-management,
    combined→both; conventions/ real dir on the contributor skill only;
    skill-level role alignment removes only symlinks — conventions/ and CoW
    content survive); callers (_finalize, add_contributor) updated;
    `_soul_block` rewritten with the three blocks (contributor / manager
    no-conventions-no-manifest / combined DEDICATED with the dual-role
    bullet); role directives deleted from the bundle (conventions/ dir
    removed). Tests rewritten (install/conventions/alignment/SOUL/growth/
    stages). **289 passed.** Live profiles cleaned of stale directive files.
14. `vault/context.py` + `schemas.py` + `reference.py` + `config.py` +
    `scaffold.py` — **DONE (2026-08-05, D1 removal).** conventions_ref +
    directives gone from context (functions deleted, payload field removed,
    imports trimmed); `_CONVENTIONS_REMINDER` reworded (no conventions_ref —
    points at the skill's writing loop); `conventions.skill` removed from
    reference.py + config.py merge + scaffold delta list + ResolvedConfig;
    **CONFIG_OPTIONS extended to the full top-level DSL** (12 entries:
    required, allowed/allowed_only, multi/format, defaults, tags.mode,
    validation, vocabulary.promote_after_uses, scopes — "obsidian_reference
    is authoritative" now true). **Bonus cleanup:** `engine_options` REMOVED
    from build_context — the extended reference would have bloated every
    context call (~3.5KB); the option list is a discovery call, not folder
    context (tool-first). 5 conventions_ref tests deleted, payload-ceiling
    and reference-discovery tests flipped. **284 passed.**
16b. Starter/blank preset configs — **DONE (2026-08-05).** `conventions:`
    block removed from both (D1); dead `promote_after_days` removed
    (promote_after_uses kept); stale `conventions_ref` comments gone.
15. `tests/` — **absorbed into tasks 13–14** (install/conventions/alignment/
    SOUL/growth/stages/permission/reference/ceiling tests all updated
    inline).
16. `plugin.yaml` — **DONE: nothing to change** (tools list only; no skill
    paths declared — registration lives in `__init__.py`).
17. Fresh-machine E2E probe (`verify-install-e2e.py`) — **DONE (2026-08-05):
    ALL PASS.** Probe updated for the split: default skill path →
    note-taking/obsidian-vault; new checks — default has NO manager skill;
    one-agent gets BOTH skills, conventions/ on the contributor one only,
    combined SOUL carries the dual-role line. Standard + blank + one-agent
    all green, zero enable WARNINGs, functional grant probes pass.

**PHASE 3 COMPLETE (2026-08-05).** The docs' spec is now the code's reality:
role-owned skills, no role directives, no conventions_ref, extended
obsidian_reference, cleaned presets. 284 suite tests + E2E ALL PASS.

## Phase 4 — SOUL.md sections (per profile role; implemented in setup.py
`ensure_soul_sections`, task 13 — **DONE 2026-08-05, verified live**)

**Live migration ran through the installer's own functions** (`_role_skill`
→ `install_skills` + `ensure_soul_sections` per profile — state produced by
installation, not hand-edited): default/creative/dev/researcher →
contributor block + `note-taking/obsidian-vault` + conventions/; vault-manager
→ manager block + `note-taking/obsidian-vault-management`, no conventions
sections. All five old-layout `skills/obsidian-vault` shells verified
(symlinks + empty conventions only) then removed. 18/18 checks PASS: skill
dirs symlinked, manager has no contributor skill, zero role-directive terms
in any live SOUL, manifest add-markers present.

18. Contributor section — Vault operations + Issues + Convention maintenance
    (2 lines) + manifest. DRAFTED (2026-08-05, see task 13).
19. Manager section — no conventions section; Vault operations + Issues
    (triage + maintain). DRAFTED.
20. Combined section — **DEDICATED text, not concatenation (Davide 2026-08-05).**
    Reasons: concatenation contradicts (manager "no conventions" vs
    contributor maintains), duplicates Issues, and cannot express the dual-role
    operational nuance. Draft carries one dual-role bullet: "sweep findings
    about your own domains are yours to fix; about other domains, raise them."
    Implemented in `_soul_block("combined")`; E2E probe asserts it.

## Phase 5 — dev-side cleanup — **DONE (2026-08-05)**

21. `obsidian-vault-plugin-engineering` — **DONE.** SKILL.md fully rewritten
    as the current-state doc (role-owned skills, split overlay, D1, 284
    tests, 54-check E2E; archaeology gone). `skill-composition-architecture.md`
    + `skill-split-audit.md` deleted (verified facts folded into
    gotchas.md §15); stale `smoke_register.py` / `verify_install.py`
    deleted; gotchas §12 compose bullet superseded; probe updated
    (note-taking paths, two-skill one-agent assertions).
22. Grep hygiene — **DONE.** Zero hits for `conventions_ref` /
    `contributor.md` / `manager.md` / `skills/obsidian-vault` in live
    guidance (skills, memory, README, engine comments, both bundles).
    The ONLY remaining mentions are past-tense deletion records in the
    change log (TASKS-skill-split.md + TASKS.md ⚠ markers + 03 ledger +
    06 note) — they name what was removed, which is the tracker's job.
    All specs/README/setup.py/starter-config mentions updated to the
    split model (D7 entries, overlay tables, role→skill mappings,
    conventions-file docstrings).
23. **Suite green (284) + fresh-machine E2E ALL PASS (54 checks) — DONE.**
    Commit prep: see `git status`; Davide pushes via VS Code.

**SPLIT COMPLETE (2026-08-05).** Two role-owned skills, no role directives,
no conventions_ref, context folder-scoped, obsidian_reference authoritative,
live machine migrated through the installer's own functions.
