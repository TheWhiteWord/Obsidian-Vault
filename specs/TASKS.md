# Obsidian Vault Plugin — Trajectory & Tasks

**Purpose:** single overview of where this is going and what state each phase is in.
Living document — updated as phases complete and as design decisions land.

**Related:**
- `00-original-plugin-idea.md` — original feature ambitions (reference, partly superseded)
- `01-vault-v2-model.md` — the data model (settled, minor gaps below)
- `02-tool-surface.md` — the tool surface (not yet written)
- `03-design-decisions.md` — settled decisions ledger (D1–D9; read enforcement, engine/preset/config split, bootstrap, skill architecture, system ownership, shared knowledge)

**Legend:** ☐ todo · ◐ in progress · ☑ done · ✂ dropped

---

## Trajectory in one line

Model → loader → boundary → derived artifacts → growth → navigation → maintenance → UI.
Each phase is usable on its own; nothing after P1 is committed to.

---

## Stage A — Design

### A1. Vault data model ☑
`01-vault-v2-model.md`. Trees & ownership, grant model, five-field schema,
per-folder config inheritance, tag modes, vocabulary lifecycle, generated-vs-authored,
growth mechanism.

### A2. Model gaps to close ☑

- ☑ **`read` grants** — TWW set to `["CREATIVE/**", "*/KNOWLEDGE/**"]`. Curated
  reference shared across domains; SYSTEM logs/specs excluded. (`01` §2.2)
- ☑ **Query vs write scope** — distinction stated in `01` §2.2.1 with the no-`domain`-
  field rationale and grant intersection. Full design deferred to `02`.
- ☐ **Named scopes** — `scopes:` block in root config. Deferred to `02`; it is a
  query-surface convenience, not a model concern.

### A3. Tool surface ☑ (in code) · ☐ (design doc)
The surface itself is built and live: 8 tools in `vault/schemas.py` with
signatures, return shapes, refusal semantics, and per-tool grant requirements.
What remains is the standalone `02-tool-surface.md` write-up (signatures +
query design + composition). The code is the source of truth; the doc is
optional and can be generated from it.

- ☑ 8 tools: `obsidian_context`, `obsidian_write`, `obsidian_edit_metadata`,
  `obsidian_delete`, `obsidian_scaffold`, `obsidian_index`, `obsidian_audit`,
  `obsidian_reference`
- ☑ Each tool declares its required grant (write/edit need `write`/`meta`;
  scaffold is a `write`; audit/index/reference are read)
- ☐ `02-tool-surface.md` — optional write-up; query design (`scope`, named
  scopes, `group_by`, grant intersection) lands with P3

### A4. Deferred design decisions ☐
Revisit only when evidence demands it.

- ☐ BM25 index — defer until `search_files` measurably insufficient
- ☐ Similarity matching — deterministic only (tag overlap + title trigram), no
  embeddings; drop "semantic" from `00`

---

## Stage B — Implementation

### P0 — Config loader & context ☑
*Proves: the model.* **Complete 2026-08-02.** Plugin at `~/.hermes/plugins/obsidian-vault/`.

- ☑ Plugin skeleton (`plugin.yaml`, `register(ctx)`), discovered + enabled
- ☑ YAML config loader, `.vault/config.yaml` at any depth
- ☑ Inheritance resolver — merge semantics per `01` §3.3
- ☑ **§3.6 falsification test PASSED** — identical `KNOWLEDGE/.vault/config.yaml`
  under two parents resolves correctly: `allowed_only` replaced `type`
  (`[knowledge]`, restricted), `allowed` unioned `kind` against each parent's
  own vocabulary, `required` accumulated `source`+`retrieved`. **Inheritance model holds.**
- ☑ Uniformity contract enforced at load (`ConfigError` on redefining
  `format`/`multi`, or dropping an inherited `required`)
- ☑ Frontmatter parser via `python-frontmatter` (principle 6, not hand-rolled);
  `Note` shape mirrors Obsidian's `NoteJson` so a P5 MCP adapter needs no
  second data model
- ☑ Malformed frontmatter never raises — `Note.error` set, surfaces as
  `malformed_notes` for the vault manager
- ☑ Vocabulary derivation: declared / observed / unused (§3.7)
- ☑ `obsidian_context(folder)` — schema, vocabulary, tags, siblings, template
- ☑ **E2E verified through Hermes' real plugin loader and tool registry**
- ☑ **Token cost measured: ~300–340 tokens** vs ~3,000 for the v1
  read-skill-then-references path. ~9x reduction, target met.

⚠ **2026-08-03 review correction (D6):** the "E2E verified" claim above was stale
relative to the final tree — `register()` raised `NameError: _handle_delete`
(the handler was wired in the dict but never defined), so the plugin was loading
**zero tools**. Fixed (D6 #1) with a new `tests/test_entrypoint.py` smoke test
that calls `register(FakeCtx())` and asserts all 10 tools register; that test is
now part of the standing suite. The E2E claim holds again as of the fix.

Fixed during verification: verbose `{name,count}` vocabulary objects → compact
`"essay (1)"` strings (−31% payload); template was sampling a sibling note's
real tags, inviting wholesale copying — now placeholders only.

### P0b — Maintainability & portability pass ☑
*Complete 2026-08-02.* Prompted by two standing asks: keep the code
maintainable, and don't foreclose open-sourcing the plugin.

- ☑ Extracted `vault/paths.py` — vault-root resolution + `safe_join` traversal
  guard. Needed by P1 write, P3 search, P4 cron; was buried in the entrypoint.
- ☑ Extracted `vault/constants.py` — shared values, one edit not three.
- ☑ Replaced throwaway `verify_*.py` print-scripts with a real pytest suite
  (`tmp_path` fixtures, never touches the live vault).
- ☑ **Bug found by the new tests:** `safe_join("/etc/passwd")` silently
  reinterpreted an absolute path as vault-relative instead of refusing it.
  A chokepoint that quietly rewrites input is a latent hole — now raises.
- ☑ **Principle 7 (mechanism vs policy)** adopted and enforced:
  - `VOCAB_FIELDS` hardcoding `type`/`kind` → per-field `vocabulary: true` flag
  - `STATE_DIR = "SYSTEM/STATE"` → `paths: { state: ... }` in root config
  - `CORE_FIELDS` constant deleted — the five fields are policy, not mechanism
  - `tests/test_portability.py`: greps engine sources for leaked folder/field
    names, **and** runs the full engine against a PARA-layout vault with
    entirely different field names (`category`/`format`/`owner`)
- ☑ 37 tests passing. Engine contains zero vault-specific names.

**Result:** the plugin is a general schema-driven vault engine; this vault is
one configuration of it. Open-sourceable by construction rather than by later
extraction.

### P1 — Write & enforcement ☑
*Proves: the boundary.* **Complete 2026-08-02.** Part of the cumulative 95-test suite.

- ☑ `roles.yaml` loader; five grant kinds (`read`/`write`/`append`/`meta`/`config`)
- ☑ Path-glob matcher, deny-by-default. `**` crosses separators, `*` does not,
  so `*/ISSUES/**` means one folder per tree — not anything anywhere by that name.
- ☑ `obsidian_write` — blocking field validation, advisory tag warnings,
  `did_you_mean` suggestions on refusal
- ☑ `register` argument → explicit vocabulary extension (§3.7), requires `config`,
  writes to the *nearest declaring config* so a tree's value lands in that tree
- ☑ `append` semantics — create only; edit and delete both refused
- ☑ `meta` enforcement — `obsidian_edit_metadata` splices frontmatter and leaves
  body bytes untouched
- ☑ Adversarial suite: 20 tests, every agent × every forbidden operation
- ☑ Verified end-to-end against the live vault through the tool handlers

**Order enforced on every mutation, no bypass path:**
`safe_join` → grant check → validation → write.

Found and fixed during the phase:
- `_dump_note` re-serialised the body on metadata edits, adding a blank line —
  the `meta` grant promises byte-identical prose, so it now splices instead.
  Caught by asserting bytes rather than trusting the claim.
- `.vault/` write check ran *after* the `.md` suffix check, so config writes got
  a misleading error.
- **Portability guard fired three times** — `"status"` hardcoded in
  `validate.py`, and vault-specific folder names in a docstring and two tool
  descriptions. `status_overrides` is now the shorthand for a general
  `value_overrides: {field, by, map}`, so per-class validation works on any
  schema.

### P2 — Derived artifacts ☑
*Proves: derive-don't-declare.* **Complete 2026-08-02.** Part of the cumulative 95-test suite.

- ☑ INDEX.md generation, on write + on demand; `<!-- generated -->` marker;
  hand-authored files sharing the name are never overwritten (`FileExistsError`)
- ☑ INDEX excludes itself and other generated files — no regeneration feedback loop
- ☑ INDEX shows derived tag cloud and flags malformed notes
- ☑ `SYSTEM/HANDBOOK/registry.md` — effective schema for every config folder,
  with declared/unused/observed vocabulary; replaces v1's hand-written SCHEMA.md
- ☑ `.state/audit-log.jsonl` — append-only, JSONL (crash-safe, concurrent-safe)
- ☑ Writes/deletes refresh the containing folder's INDEX automatically

### P2b — Scaffold ☑
*Proves: growth without redesign.* Done together with P2.

- ☑ `obsidian_scaffold(path, intent, proposed, confirm=false)` — delta-only proposal
- ☑ Empty delta writes **no** config file; states "inherits everything" plainly
- ☑ Delta strips values already inherited — only the real difference is proposed
- ☑ Structural config (new required fields) refuses without explicit
  `user_confirmed`; vocabulary values flow freely (§10.4)
- ☑ Scaffold is a `write` op — `vault_manager` is structurally unable to create
  structure (§10.3), and owners cannot scaffold outside their own tree
- ☑ Scaffold action is audited

Found and fixed during the phase:
- The index summary privileged a hard-coded `status` field — now shows every
  vocabulary field's value, config-driven. The portability guard caught it.
- Audit log used to be a JSON array; switched to JSONL so a crash can't corrupt
  the trail, and concurrent appends interleave safely.
- Generated files were being counted as notes by `iter_notes`, so each regen
  fed on the last. `include_generated=False` default breaks the loop (§6).

### P2 addendum — summary_field (discovery-safe) ☑
*Proves: the open-source concern is real and cheaply solved.*

- ☑ `summary_field` is an *engine concept* (config key), not a hardcoded name.
  The vault names the field (`description` for Davide); INDEX renders it; the
  engine stays name-agnostic. A PARA vault uses `blurb` with no code change.
- ☑ `description` added to Davide's root config as **advisory** (not required)
  — prompted in `obsidian_context`'s template, never blocking. Avoids v1's
  friction-driven decay.
- ☑ Discovery problem solved by `vault/reference.py`: the engine emits its own
  config reference (every option + the five grant kinds). `obsidian_reference`
  tool and `engine_options` in `obsidian_context` expose it. A from-zero user or
  a setup-assistant AI reads the reference instead of the source — docs cannot
  drift from code.
- ☑ `obsidian_reference` tool added (8 tools total).

Founds/fixes: portability guard fired false positives on JSON-schema
`"description":` keys and ROLES help text; corrected the guard to ignore
string-value lines. Payload size ceiling raised to 3200 to accommodate the
intentional self-documenting reference (constant, not bloat).

### P3 — Graph & query ☑
*Proves: navigation.* **Complete 2026-08-02.** Part of the cumulative 107-test suite.

- ☑ `obsidian_search` — deterministic term match over title/body/tags/links/
  frontmatter. `scope` glob, `group_by` (folder/any-field/tag), `limit`.
- ☑ **Grant intersection (§2.2.1):** results filtered by the agent's `read`
  grants, not the query. Searching `**` silently returns nothing from where the
  agent cannot read. The vault_manager (no agent / system) searches unfiltered.
- ☑ `obsidian_graph` — wikilink graph: neighbors (in/out/both), N-hop BFS
  traversal, dangling-link report.
- ☑ Graph is **derived from note bodies on demand**, never cached — it cannot
  drift (stronger than the spec's "incremental" idea; at vault scale a full
  recompute is sub-second). `.state/graph/` is no longer written.
- ☑ Cross-domain navigation works: a SYSTEM/KNOWLEDGE note linking a CREATIVE
  note is traversable by an agent with read grants on both.

**Deviation from spec, deliberate:** no BM25 index, no embeddings (A4). Grep-
class matching is sufficient at vault scale; search earns its keep without a
second index that duplicates Obsidian's own. Revisit only if measurement shows
`search` is insufficient.

### P3.5 — STATE + ISSUES restructuring ☑
*Design correction from review (post-P3).*

- ☑ **STATE → vault root `.state/`, always on.** Moved from `SYSTEM/STATE` to
  root `.state/` (dot-prefixed, reads as machinery). The engine now *defaults*
  `state` to `.state/` and auto-creates it on first write — the manager (P4)
  needs the audit trail, so it can't be opt-in. `paths.state` still relocates it;
  a new `STATE_DIRNAME` constant marks it engine-reserved (exempt from the
  portability policy-name guard, like `.vault`).
- ☑ **`issue` is no longer a global kind.** Removed from the root `kind` allowed
  list. Each `*/ISSUES/.vault/config.yaml` declares `kind: [issue]`, the
  `open/in-progress/resolved` status override, and optional `severity`. An `issue`
  written outside an ISSUES folder is observed (advisory warning), not declared —
  so the global vocabulary stays clean of issue terminology.
- ☑ Live vault migrated: audit log moved `SYSTEM/STATE/audit-log.jsonl` →
  `.state/audit-log.jsonl`; `SYSTEM/STATE` removed; `SYSTEM/ISSUES` + `CREATIVE/
  ISSUES` folders created with their local configs.
- ☑ Tests updated: the portability guard now distinguishes policy names
  (SYSTEM/CREATIVE/KNOWLEDGE/ISSUES…) from engine-reserved names (STATE/VAULT,
  where STATE = the `.state/` folder constant); obsolete "no state path" test
  replaced with "default STATE trail always written".

### P3.6 — Permission coherence (D2) ☑
*Proves: read grants are real.* **Complete 2026-08-03.** The review decision D2 (`03`) made
`read` deny-by-default enforcement across every surface; the code and the spec now agree.

- ☑ ISSUES `allowed_only` — `*/ISSUES/.vault/config.yaml` restricts `kind`/`status`
  to issue values (`allowed_only`), so the `allowed` union no longer defeats the channel
- ☑ `obsidian_graph` read enforcement — center, neighbors, hops, and dangling all filter
  through the caller's `read` grants
- ☑ `obsidian_audit` read enforcement — entries filtered by the caller's `read` grants
- ☑ `obsidian_index` grant gating — gated on **any** grant over the target folder
  (a `meta`-only maintainer must be able to refresh INDEXes)
- ☑ `obsidian_context` grants — `agent` wired through; payload carries the
  caller's five grant booleans. ⚠ The `conventions_ref` pointer shipped here
  was REMOVED 2026-08-05 (D1, skill split — see TASKS-skill-split.md): context
  is folder-scoped; the writing rules live in the role's skill.
- ☑ Regression tests per surface — `tests/test_permission_coherence.py` (16 tests:
  ISSUES restriction, graph/audit/index enforcement, context grants; the pointer
  tests were deleted with D1)

Found and fixed during the phase:
- `any_grant` was added to `Grants` but handlers hold a `RoleRegistry` — moved
  (the registry owns agent-scoped methods)
- Payload ceiling test had drifted: `engine_options` reference is a documented
  ~2000-char constant (one entry per real option), not the "~400 chars" the old
  comment claimed — ceiling corrected to 3400. ⚠ `engine_options` itself was
  removed 2026-08-05 (D1) — the option list is a discovery call, never context

### P3.7 — Skill phase (D7/D8/D9) ☑
*Proves: the missing content layer.* Conventions live in the skill, not the vault (`03` D7).
**Complete 2026-08-03.** Design locked with Davide first: plugin holds immutable
fragments; the installer composes a profile-tailored copy into each profile's skills/;
`default` owns `system/**` (D8), `vault-manager` is maintenance-only, per-domain
`knowledge/` shared with `researcher` (D9).

- ☑ Archived v1 `note-taking/obsidian-vault` → `~/.hermes/skills-archive/obsidian-vault-v1-legacy`
  (no namespace collision with the new skill)
- ☑ Bundled skill at `skills/obsidian-vault/` (plugin dir): SKILL.md (cascade +
  tool routing + immutable/mutable split), `references/` (obsidian-formatting,
  tool-protocol), `templates/vault-conventions.md`. ⚠ Superseded 2026-08-05 by
  the skill split (TASKS-skill-split.md): two role-owned skills at
  `skills/note-taking/`; role-directive fragments abolished.
- ☑ `ctx.register_skill("obsidian-vault", …)` in `register()` — pre-install
  fallback + immutable source; smoke test asserts the bundle ships
- ☑ `scripts/setup.py` — compose_skill (base+contributor, +manager for manager
  profiles), install_skill (profile copy, never touches bundled),
  ensure_soul_directive (append-only, idempotent), scaffold_vault
  (default|blank preset); pure functions testable against scratch HERMES_HOME
- ☑ Installer installs into `default` (system owner, contributor-only) + manager
  + per-domain contributors; SOUL.md directive appended to each touched profile
- ☑ Starter preset `examples/starter-vault/` — neutral tree (`system/`, `work/<domain>/`
  with per-domain `knowledge/`), roles per D8/D9, issues-channel config
- ☑ Live vault reset to the starter preset (user-approved wipe; the four `.vault`
  configs captured to `DESK/specs/reference-configs/` first)
- ☑ Reminder line on mutating tool schemas (Decision B — pointer, never
  verification; the cascade is assumed at skill level)
- ☑ `DEFAULT_AGENT` renamed `system` → `default` (matches starter roles; an
  agent-less call must not fall through to a name that denies everything)
- ☑ Starter globs fixed for two-level-deep paths — `*/knowledge/**` never
  matched `work/<domain>/knowledge/` (single-segment `*` doesn't cross
  separators); now `work/*/knowledge/**` and `**/issues/**`, regression-tested
- ☑ Tests: `test_setup.py` (10: compose/install/SOUL/scaffold/glob regression),
  `test_entrypoint.py` skill-bundle test — **144 tests green**
- ☑ E2E through real handlers on a scratch starter vault: context → write →
  refusal → search → graph dangling → audit, 9/9 checks passed
- ☑ SOUL.md directive appended to the default profile (this one)

Found and fixed during the phase:
- `roles.allows()`/`check()` take **operations** (create/edit/delete/read/…),
  not grant kinds — `allows(agent, "write", path)` is `RolesError` (swallowed
  to False). Append semantics are tested via `create` (allowed) vs `edit` (denied).
- The uncomment-in-test helper twice corrupted YAML by uncommenting prose —
  only agent/grant lines are uncommented, re-indented.
- Installer crashed on every real run: the `default` profile lives at the
  HERMES_HOME **root** (`~/.hermes/SOUL.md`), not `profiles/default/`. Fixed
  with a `profile_home()` helper (+parent mkdir in ensure_soul_directive),
  caught by a scratch-HERMES_HOME E2E of the full installer; 2 regression
  tests added. Scratch E2E also proved `hermes profile create` delegation +
  contributor loop (vault-manager + creative created via the real CLI).
- Re-scaffold was clobbering vault policy: `scaffold_vault` re-copied
  `.vault/config.yaml` + `roles.yaml` on every run, wiping activated
  contributor grants. Fixed with `_copy_if_missing` (configs written only on
  first scaffold; tree re-ensured), regression-tested. Proven live: installer
  re-run preserved the 3 active contributors (grant matrix 7/7 after).

### P3.7b — Installer v2: per-profile plugin enablement + domain configs ☑
*Fixes two gaps Davide hit after the first real install (2026-08-03).*

- ☑ **Per-profile plugin enablement (issue 1).** A named profile does NOT see
  globally-installed plugins — discovery scans only the profile's own
  `plugins/` (probed: `hermes --profile creative plugins list` empty before
  symlink). Installer now: symlinks the bundle into `<profile>/plugins/`,
  runs `hermes --profile <name> plugins enable obsidian-vault
  --no-allow-tool-override` (writes `plugins.enabled`), and writes
  `OBSIDIAN_VAULT_PATH` + `OBSIDIAN_VAULT_AGENT` into the profile `.env`
  (without the agent var every session acts as `default`). `default` gets
  env-only (plugin already lives at the HERMES_HOME root).
- ☑ **Per-domain `.vault` configs (issue 2).** Spec §3.3/3.4/3.6 designed them
  (`CREATIVE/.vault/config.yaml`, `*/KNOWLEDGE/.vault/config.yaml` "identical
  in every domain") but the starter never shipped them. Now 5 configs:
  `system/`, `work/creative/`, `work/coding/`, + both `knowledge/` (the §3.6
  schema: `allowed_only: [knowledge]`, source/retrieved/confidence). All
  copy-if-missing.
- ☑ Verified live: symlinks present in all 4 named profiles, `plugins.enabled`
  set in each config, per-profile env wired, 5 domain configs in the vault;
  context probe shows the merge (creative type = root+domain union via
  `declared_unused`; KNOWLEDGE restricted + source/retrieved/confidence).
- ☑ Tests: 152 green (added link_plugin, ensure_profile_env upsert/idempotence,
  domain-config copy + preserve-on-rerun regressions).

**Supersedes:** `00` §1's "Manager has default access to all tools and domains"
— D8 makes `default` the system owner and `vault-manager` maintenance-only.

### P3.7c — Profile configs seeded from default (2026-08-03) ☑
*Fixes: new profiles were bare stubs (no memory / most settings) because
`hermes profile create` seeds minimal configs.*

- ☑ **Config seeding.** `seed_profile_config()` copies the system default
  `config.yaml` into each named profile, copy-if-missing, before plugin
  enable. Discriminator is `memory:` — the stubs already contain `model:`,
  so a `model:` check would leave every stub untouched. Default config has
  no identity keys (name/profile/alias) → verbatim copy is safe.
- ☑ **Normal behaviour for installation:** new profiles start from default's
  config as a working baseline; the installer prints "review
  model/memory/plugins" and the setup docstring documents it. `--clone-from`
  rejected: mutually exclusive with `--no-skills`, drags .env/SOUL/skills,
  and cannot fix already-created stubs.
- ☑ Verified live: all 4 profiles now 9148 bytes with memory/moa/plugins;
  `hermes --profile dev config get model.default` works; per-profile
  OBSIDIAN_VAULT_AGENT intact after seed.
- ☑ Tests: 157 green (+5 seed tests: fills stub, creates missing config,
  preserves customised, skips default, warns when no default exists).

### P3.7d — Clean-slate E2E verification ☑
*The installer from a true zero state (2026-08-03).* User stripped all
profiles, every plugin config/env entry from `default`, and the whole vault —
the installer then had to create everything, including the vault tree.

- ☑ From zero: 4 profiles via CLI, configs seeded (9148 B, `memory:` present,
  no identity keys leaked), plugin enabled per profile, symlinks + `.env`
  wired, vault scaffolded from scratch (11 dirs; 10 `.vault` configs incl.
  `roles.yaml`, now also README)
- ☑ **Default enablement gap fixed:** `enable_plugin_for_profile` skipped
  `default` (env-only) — post-strip default would have had `.env` but no
  enabled plugin. Now bare `hermes plugins enable` for default too; failures
  surfaced as warnings, not silent success. (+3 tests)
- ☑ **README scaffold gap fixed:** `scaffold_vault` never copied the starter
  README into a new vault — now copy-if-missing. (+1 test)
- ☑ **`_create_profile` silent failure fixed:** `hermes profile create` exits
  1 on existing profiles; the installer swallowed the error and printed
  success. Now warns visibly — re-run is a normal scenario. (+2 tests)
- ☑ Functional probe on the fresh vault (deny-by-default proven, not just
  file presence): write as `default` ok; search as `default` finds it;
  search as `creative` (zero grants — fresh roles.yaml has contributors
  commented) returns nothing; context grants row all-false + siblings
  hidden for zero-grant agents; delete ok; vault left clean.
- ☑ SOUL.md directive idempotent across runs (1 occurrence per profile);
  suite **163 green**.

### P3.7e — Standard install ships the full agent set active (2026-08-03)
*Decision (Davide): the starter roles.yaml carries all five agents —
`default`, `vault-manager`, `creative`, `dev`, `researcher` — **granted by
default**. The vault is built for exactly these profiles, so nothing ships
commented; deny-by-default still protects *unlisted* agents. Custom profile
sets are a future design consideration (spec `04` C1), not the default.*

- ☑ Starter `roles.yaml` uncommented: contributors ship active, comment
  rewritten to state the standard set + defer custom installs
- ☑ Starter README updated (no more "uncomment per domain" instructions)
- ☑ Tests: dead `_uncomment_starter_contributors` helper removed;
  `test_starter_roles_ship_full_agent_set_active` pins the five-active
  invariant; rerun-preserve test now edits a real grant instead of
  simulating an uncomment; glob test runs directly on scaffolded roles
- ☑ Suite green (**164**), live vault re-scaffolded through a clean
  installer run — the state comes from installation, not a manual fix

### P3.8 — Search scope exclusions (`!pattern`) ☑
*Proves: shared-folder searches (D9).* **Complete 2026-08-04.** Part of the cumulative 175-test suite.

- ☑ `scope` accepts a glob **or a list** — a `!`-prefixed entry is an
  exclusion: `["work/creative/**", "!work/creative/knowledge/**"]` searches a
  domain tree minus the shared folder
- ☑ Negation lives in the glob language, not a new parameter (D3's "`!pattern`
  negation in the glob language"; one coherent surface — no `exclude_scope`)
- ☑ `vault/grants.py` gains `scope_matches(patterns, path)` — include-any AND
  exclude-none; `path_matches` stays the positive-only grant primitive, and a
  `!` inside a grant pattern is a literal that matches nothing
- ☑ Deny-by-default untouched: scope negation applies after the read-grant
  intersection, so exclusions can only remove results, never reveal them
- ☑ Edge semantics: an exclusion-only scope matches nothing (absence of an
  inclusion never widens a query); the trailing `/**` folder-self convenience
  applies to exclusions too; `*` vs `**` separator rules shared with grants
- ☑ Schema: `OBSIDIAN_SEARCH.scope` typed `string | array`, documented
- ☑ Tests: +11 (5 search-level negation incl. never-widens-grants, 6
  glob-language unit tests) — **175 green**

Found and fixed during the phase:
- The first unit test encoded a wrong expectation about the bare-`*` glob
  (which the engine treats as match-anything, like `**`): `!*` excludes
  everything, not just root-level files. Negation must mean exactly what
  inclusion means — the separator test now uses `!*/design.md` vs
  `!**/design.md` to pin real semantics.

### P4 — Vault manager ☑
*Proves: the second layer.* First non-interactive agent.

Design: `05-maintenance-design.md` (v4 — the **issue ledger**).
**Complete 2026-08-04.** Part of the cumulative 213-test suite.

- ☑ Issue ledger (`vault/issues.py`): record CRUD + lifecycle — create /
  resolve / list / dedupe-by-key / re-escalation / prune. JSON records under
  `.state/issues/`, engine machinery (no grants, no config, no notes)
- ☑ Delta pass: checkpoint over `.state/audit-log.jsonl` (watermark = last
  processed line, advance only after a full successful run; log stays
  append-only)
- ☑ Maintenance pass: broken links, orphans, stale edges, empty notes,
  malformed frontmatter (`graph.dangling` + note errors + INDEX freshness)
- ☑ Optimization (B2): duplicates, missed connections, tag normalization,
  coverage gaps — suggestions only, `nature: suggestion`
- ☑ Vocabulary curation per `01` §3.7 — promote observed past
  `promote_after_uses` (config grant, AUTO)
- ☑ Distribution + lifecycle: findings → issues (key = `check|path`, target =
  path, tags `[maintenance]`); auto-resolve when condition clears; suggestions
  auto-decline after TTL (14d); prune resolved after TTL (30d)
- ☑ Tools: `obsidian_issue` (batch `items:`), `obsidian_issue_resolve`,
  `obsidian_issue_list`, `obsidian_maintain` (`mode: delta|maintain|optimize`,
  `distribute`, `dry_run`)
- ☑ Cron schedule: daily `maintain` (05:00), weekly `optimize` (Mon 06:00) —
  installed on the `vault-manager` profile (`hermes --profile vault-manager
  cron`). **SUPERSEDED 2026-08-06** — setup now installs them
  role-dependently (see the Scheduled maintenance cron phase below). NOTE:
  the gateway is not running as a daemon, so jobs fire only when it is up
  (`hermes gateway install`).
- ☐ DEFERRED — human-visible issue board (derived note, regenerated each
  sweep): purely for the human, not agents. Design + build when the ledger is
  stable.

Live-vault proof (2026-08-04): from-zero re-scaffold (backup kept at
`VAULT.backup-20260804-124534`), live sweep found the README orphan, issued
`orphan|README.md`, dedupe confirmed on re-run, agent raise → grant-filtered
list → owner resolve exercised end-to-end. Starter README gained conforming
frontmatter (the sweep caught its absence).

Build against the current state — `.state/audit-log.jsonl` + on-write INDEX regen —
**not** a `change-log.json` event log (`03` Open). The vault-manager profile +
skill already exist (P3.7); this phase is the maintenance logic and schedule.
Standard-state changes: starter loses the three `*/issues/` folders + the
`append: ["**/issues/**"]` grant lines (vestigial once issues are records);
`ISSUES` joins `STATE`/`VAULT` in the portability test's reserved names.

### P5 — Installation & growth system ☑
*Proves: growth — the trajectory's fifth step.* The installer goes from
one-shot to a system that grows the vault. **Design discussion 2026-08-04**
(Davide's `MARKDOWN-plugin-skil.md` overview + four settled questions). The
old P5 (MCP) is demoted to P7: the next tasks on the old list weren't the
interesting work; the tool exists and the open question is how it installs
and grows cleanly.

**Locked decisions (2026-08-04):**
- **No role-split tool registration** — all 14 tools register for every
  profile; differentiation lives in the convention layer (SOUL/skill), grants
  are the hard backstop. One coherent surface: portability guard, entrypoint
  test, and the one-profile setup all stay simple. (Davide accepted on the
  argued recommendation.)
- **Two-tier growth, engine-native (verified).** Manager owns root config /
  roles / new full domains (config grant on `**`). Domain owner self-serves
  subdirectories + local `.vault/config.yaml` fragments inside its tree:
  `obsidian_scaffold` gates on the `create` operation (write kind), not
  `config`, so a contributor can scaffold a subfolder with a config delta
  today — no manager round-trip. Nuance: scaffold's config write rides the
  *write* gate; the `config` grant governs editing existing configs /
  vocabulary registration (`_register_value`) — manager-only.
- **Skill overlay (probe-proven 2026-08-04):** symlink SKILL.md +
  references/ + templates/ to the bundle; `conventions/` real files per
  profile. Conventions survive re-runs — today `install_skill` rmtree's the
  whole profile skill dir (the survival bug). Probe: `skill_view` resolves
  symlinked SKILL.md + symlinked references/ dirs.
- **Blank preset ships a neutral roles.yaml** — deny-by-default, no
  five-agent defaults. Today `--preset blank` reuses the starter roles
  (confirmed gap).
- **Coder-plugin interaction is P6** — its own research + design, tackled
  last (Davide 2026-08-04).

#### P5a — Skill overlay ☑
*Proves: conventions survive.* **Complete 2026-08-04.** Part of the cumulative 217-test suite.

- ☑ `install_skill` rewritten: SKILL.md, references/, templates/ → **symlinks**
  to the bundle (update-propagating, base intact); `conventions/` → real
  per-profile dir, seeded copy-if-missing, **never rmtree'd on re-run**
- ☑ `_ensure_symlink` COW guard: a *modified* real references/templates dir
  is a deliberate copy-on-write escape hatch (06 §2.3) and is left alone;
  only content-identical stale copies from pre-P5a installs are replaced by
  symlinks. SKILL.md is engine-owned — any real file there is a stale
  composed variant, always replaced
- ☑ Role alignment: ⚠ now skill-level (2026-08-05 split) — re-installing a
  profile with a different role removes the other role's skill symlinks; the
  maintained conventions file is never touched
- ☑ Base SKILL.md updated: routing table gains the 4 P4 tools
  (`obsidian_issue`/`_resolve`/`_list`, `obsidian_maintain`); "immutable vs
  mutable" rewritten for the overlay; new **role → skill** mapping
  (contributor → obsidian-vault, manager → obsidian-vault-management, one-profile
  → both, 2026-08-05); stale "appended here by the installer" text removed
- ☑ `compose_skill` deleted — composition is replaced by routing; the
  composed-profile-copy model is gone
- ☑ Tests: +9 overlay tests (symlink base, seed conventions, survival
  regression, seed-if-missing, stale-copy → symlink, COW preserved,
  other-skill symlink removal), −5 dead compose tests — **217 green**
- ☑ Live migration (installer re-run = source of truth, P3.7e): all 5
  profiles (`default`, `vault-manager`, `creative`, `dev`, `researcher`)
  re-installed as overlays. Live `references/` were stale Aug-3 copies
  (tool-protocol.md predated the P4 rows) — verified zero custom files, so
  replaced by symlinks (lost nothing). Final state per profile:
  SKILL.md/references/templates symlinks ✓, conventions/ real dir ✓,
  conv files: contributors `[<vault>-conventions.md]` (split: the only
  maintained file), vault-manager none. `skill_view('obsidian-vault')` resolves
  the live symlinked skill end-to-end
- ⚠ Migration note: `_identical_dir` (COW guard) cannot distinguish a stale
  pre-P5a copy from a deliberate edit — both are non-identical. The
  one-time migration used "no files outside the bundle" as the stale
  discriminator. Future installer runs only ever see symlinks or true COW
  edits, so this ambiguity is migration-only

#### P5b — SOUL + references + presets + edit tool ☑
*Proves: the config surface is authorable, not just readable.* **Complete 2026-08-04.** Part of the cumulative 237-test suite.

- ☑ SOUL.md → role-aware anchored template (`ensure_soul_sections`): one
  `## Vault` umbrella with `###` subsections (Vault operations / Issues /
  Convention maintenance / Convention manifest), every bullet a tool or
  reference pointer. Role variants contributor | manager | combined
  (one-profile). Anchored block (`SOUL_ANCHOR`) replaced in place on
  re-run; the pre-P5b single paragraph is **upgraded in place** (removed,
  not duplicated) — verified live on all 5 profiles, idempotent re-run
  (**2026-08-04 correction:** sections nested under `## Vault`, not flat)
- ☑ Manifest starts empty-but-directed (`<!-- add: path — description -->`);
  the growth protocol (P5c) appends entries. Role directives listed as
  immutable; manager's manifest carries no per-vault add-line (it does not
  maintain conventions)
- ☑ New bundle references: `issues.md` (ledger lifecycle, raise≠fix,
  grant-derived access), `maintenance.md` (modes, AUTO/FLAG, findings →
  ledger, schedule), `config-authoring.md` — **the full config DSL**
  (Davide's clarification): location + upward inheritance, top-level keys,
  per-field keys with verified merge rules (`allowed` union, `allowed_only`
  replace, `required` accumulate, `format`/`multi` immutable), the
  **implications map** (what each statement does to write/search/context/
  INDEX/promotion), may/must-not, and anchor examples
- ☑ Neutral blank preset (`examples/blank-vault/`): deny-by-default
  roles.yaml (only `default` active, manager as commented stub) + minimal
  config (five core fields, conventions pointer). `scaffold_vault` now picks
  the source per preset — the old blank preset wrongly reused the starter's
  five-agent roles (fixed)
- ☑ **Starter roles D-5:** contributors gain `config` on their own tree
  (`default: system/**`, `creative: work/creative/**`, `dev:
  work/coding/**`, `researcher: work/*/knowledge/**`) — write over a tree
  ⇒ config over that tree; root `.vault/` and roles.yaml stay manager-only
- ☑ **`obsidian_edit_config` tool** (15th tool): config-gated (`edit_config`
  op → `config` kind), scaffold's delta machinery reused (cannot drift),
  structural fields/validation need `user_confirmed` (mirroring scaffold's
  real semantics — any `fields` delta, not just required-keys; the schema's
  old "vocabulary flows freely" promise did not match scaffold's code),
  defaults/tags flow freely. Refusals: roles.yaml, non-config targets,
  missing files, and uniformity violations — the merged chain is re-resolved
  through the real loader in memory (`_validate_merged_chain`) so dropping
  an *inherited* required or redefining an inherited `format`/`multi` is
  refused before any write. Audited (`edit_config`)
- ☑ Tests: +16 `test_config_edit.py` (propose/apply, confirmation
  semantics, grants, refusals, inherited-required + format immutability via
  a child-of-KNOWLEDGE config, allowed vs allowed_only semantics, audit),
  +6 SOUL tests (−2 old directive tests) — **237 green**;
  **2026-08-04 corrections → 238 green** (role-based install_skill tests:
  manager gets manager.md ONLY, contributor.md removed on promotion,
  maintained-conventions survival + directive refresh)
- ⚠ **Conventions model — SUPERSEDED 2026-08-05 by the skill split**
  (TASKS-skill-split.md): role directives (`contributor.md` / `manager.md`)
  are abolished; each role owns its skill (`obsidian-vault` /
  `obsidian-vault-management`); the maintained file is
  `conventions/<vault>-conventions.md`, created from the template by the
  growth protocol, never touched by the installer. "Manager is not a
  contributor" still holds — a manager gets the management skill only and
  does not maintain conventions
- ☑ Live: SOUL sections written for all 5 profiles (manager variant on
  vault-manager only), bundle references symlink-propagate to every profile
  copy automatically (P5a overlay); 2026-08-04 re-run: all SOULs upgraded to
  the `## Vault` form (2026-08-05: refreshed again for the split)

#### P5c — Growth protocol ☑
*Proves: the vault grows through mechanical, tested commands — the agent
is aided through the process, it never improvises filesystem surgery.*
**Complete 2026-08-04.** 259-test suite (238 + 21 growth).

- ☑ **Interactive reference** — `references/growth-protocol.md` (bundle,
  registered in SKILL.md References): the three canonical flows (Eg1
  subdomain / Eg3 full domain / Eg2 custom install) with the LLM-step vs
  mechanical-step split, per-stage questions, role-constraint table,
  expected outputs, the SOUL manifest mechanics, the copy-on-write escape
  hatch (§2.3 — documented once here, closing that §6 open item), and
  pitfalls
### P5c growth protocol — SUPERSEDED 2026-08-05

The `--add-contributor` / `--add-domain` / `--add-subdomain` flags below were
replaced by the `--role` verb family (bind/unbind/transfer/list) — see
`TASKS-role-mutation.md` + 06-growth-design §4.5. Kept as the phase record.

- ☑ **`--add-contributor NAME`** (manager): profile (if missing) + skill
  overlay (contributor role) + SOUL sections + config seed + plugin enable
  + env binding. Extracted from the installer's contributor loop — one
  code path, thin entry points
- ☑ **`--add-domain DOMAIN --owner PROFILE [--config FILE]`** (manager):
  `work/<domain>/` + `.vault/config.yaml` (prepared file or minimal stub,
  both YAML-validated) + roles.yaml grant block (write/config on the tree,
  read + shared knowledge glob) + maintained conventions file
  `<vault>-conventions.md` (copy-if-missing from template) + SOUL manifest
  entry. Refuses: unscaffolded vault, missing owner profile (order!),
  owner with existing grants (hand policy edit), broken `--config`
- ☑ **`--add-subdomain REL_PATH --owner PROFILE`** (domain owner): rides
  `obsidian_scaffold` — verifies the dir exists (scaffold ran) and the
  owner holds `write` (engine `create`/`edit` operations, re-checked),
  then records the subdomain in the owner's SOUL manifest + conventions
  file. Refuses non-owners and missing dirs
- ☑ **Manifest mechanics**: entries accumulate above the `<!-- add:`
  marker, idempotent (never duplicated), manager SOULs refuse appends
  (no add-marker — the conventions-are-contributor-owned guard)
- ☑ **roles.yaml surgery is comment-preserving text append** (never a
  round-trip — POLICY comments survive), re-parsed with `yaml.safe_load`
  before write, refuses top-level keys after `agents:`
- ☑ **Dry-run everywhere**: `--dry-run` prints actions, touches nothing
  (asserted per subcommand)
- ☑ **Grant correctness through the real engine**: tests assert via
  `load_roles` + `OPERATION_GRANTS` — owner can `create`/`edit`/
  `edit_config` inside its tree, cannot reach root `.vault/` or
  `roles.yaml`
- ☑ Live verification (dry-run against the real vault): the three guards
  fire (existing-grant owner refused, missing profile refused, missing
  subdomain dir refused), nothing written

#### P5d — Install/setup redesign: deterministic questionnaire ☑
*Proves: install and setup are separable, script-owned, and never
LLM-improvised. **Complete 2026-08-05.** 287-test suite (286 + P5d).*

- ☑ **Install = Hermes-native** (`hermes plugins install <git-url>`):
  repo clone + auto-install of runtime deps via `plugin.yaml`
  `pip_dependencies` (python-frontmatter, PyYAML — both lazy imports,
  declared 2026-08-05). No manual git clone, no TWW paths in shipped
  artifacts
- ☑ **Setup = deterministic stage machine** (`scripts/setup.py --setup`):
  script owns sequence, validation, and every fs decision; the agent only
  relays `SETUP:question` JSON and feeds answers via `--answer`. Stages:
  location → name → preset (standard|blank) → per-role profile assignment
  → finalize recap. Invalid answers loop back with `SETUP:alert`
- ☑ **Role accumulation (one-agent setups allowed):** mapping several
  roles onto one profile yields the combined skill role (both directive
  files) and unioned grants — the old `_append_agent_grant` "refuse
  existing owner" path is deleted; one shared core `_ensure_agent_block`
  (extend-or-append, comment-preserving, idempotent) serves setup +
  growth
- ⚠ **`conventions_ref` role-awareness — REMOVED 2026-08-05 (D1, skill
  split)**: the pointer and its directives list are gone; context is
  folder-scoped (grants, schema, tags), the option list is a discovery
  call (`obsidian_reference`)
- ☑ **Naming unified:** preset is `standard|blank` everywhere — the
  legacy `default` preset name, the `--preset/--manager/--yes` flags, and
  the interactive flow are gone; scaffold rejects unknown presets
- ☑ **plugin.yaml coherence test** — `provides_tools` (15) must match the
  entrypoint's registered tools (drift guard)
- ☑ README rewritten for the install/setup split (stale TWW-era copy
  replaced; one-line install prompt for the agent)

### Scheduled maintenance cron — setup-embedded (2026-08-06) ☑
*Proves: the maintenance schedule ships with the vault.* The two jobs were
hand-created in dev (P4); a fresh install got zero. Setup now installs them
at finalize.

**Design decision (Davide, 2026-08-06):** maintenance cron is installer-owned;
user-requested *content* cron is decoupled from the plugin — a manager-skill
procedure (`references/recurring-tasks.md`), not engine machinery.

- ☑ `install_cron_jobs(profile)` in `vault_ops.py` — shells `hermes cron
  create` per job; idempotent by job NAME (existing jobs left untouched);
  `--dry-run` shells nothing.
- ☑ Setup finalize derives the target profile from the manager ROLE
  (role-dependent — one-agent installs land on `default`; `existing:NAME`
  lands on NAME); never a hardcoded name.
- ☑ Jobs pin the manager skill (`obsidian-vault-management`) and carry the
  full management loop (sweep + README drift + grant-anchor + triage), not
  a bare tool call.
- ☑ Manager skill: `references/recurring-tasks.md` (profile-by-grants,
  chained jobs via `context_from` for cross-owner workflows, first-run
  verification).
- ☑ Tests: 5 unit tests (command shape, bare-vs-profile, idempotency,
  dry-run, failure warning) + E2E probe asserts jobs land on the manager
  profile in standard/blank AND on `default` in one-agent installs.
- ☑ Live vault: stale dev-time jobs recreated with the new prompts
  (2026-08-06, ids rotated; verified via `cron list` + jobs.json).

### P8.1 — Full role SOULs ☑ (2026-08-06)
*Proves: role profiles ship real identities, not just a vault block.*
Design: `specs/08-soul-design.md`; research: `reference/soul-md-research.md`
(source-verified against `hermes_cli/default_soul.py` — the "safe to
overwrite" precedent the replace rule mirrors).

- ☑ Five identity templates in `souls/` (repo root — moved out of
  `examples/` 2026-08-06: profile templates shared across presets, not
  vault content) — `manager`, `system-owner`, `creative`, `researcher`,
  `dev` (prose-only files; the engine composes the `## Vault` block so
  it cannot drift).
- ☑ Templates enriched to the four-section house style (2026-08-06, per
  the CrewAI craft guide in `reference/Crafting_Effective_Agents_-_CrewAI.md`):
  `# Identity` → `# Goal` → `# Perspective` → `# Style`, each 2–4 lines.
  Perspective's FORM follows the role's psychology (scars / external
  judge / duty / stewardship) — never a fixed skeleton. **`manager`
  still pre-enrichment** (Identity+Style only) — enrichment pending.
- ☑ Identities are **decoupled personas** (review, 2026-08-06): the agent
  IS the persona; the vault is a tool/memory layer expressed by the
  anchored block. The manager is the deliberate exception (its identity
  is vault-connected).
- ☑ Replace-vs-append rule: pristine (`DEFAULT_SOUL_MD` / legacy
  template) → replace wholesale with the full role SOUL; anything else →
  append/replace only the anchored block. `default` is always block-only
  (S-3). Manager gets a full soul only on a profile CREATED for the role
  (S-4, review override).
- ☑ `_is_pristine_soul`, `_full_soul`, `_soul_identity`, `_soul_has_identity`,
  `_apply_soul_prose`; `--soul FILE` on `bind` (generation + update path);
  domain-add review notice (S-8).
- ☑ Tests: 21 new (381 green) — pristine→replace, customized→append,
  legacy→replace, default carve-out, manager full soul, combined
  block-only, upgrade paths, idempotence, unbind restore (incl. manager),
  `--soul` semantics, review notice.
- ☑ E2E probe updated (90 checks): standard + blank manager assert full
  manager souls; contributors assert decoupled full souls; `default`
  block-only.
- ☑ Live vault: `vault-manager` + contributors migrated to full souls via
  the installer's own functions; `default` untouched byte-for-byte
  (probe 10/10).

### P6 — Coder-plugin interaction ☐
*Deferred (2026-08-04): a specific feature needing its own research and
design, and a lot of background work (Davide).* Prerequisites to resolve
when picked up: git init decision (the plugin dir and `~/.hermes` are not
under version control today), update/install path interplay with the P5a
overlay, scope of a profile acting on the plugin bundle, wiring the `dev`
profile to the `obsidian-vault-plugin-engineering` skill.

### P7 — Transport adapter (MCP optional) ☐
*Proves: the façade, if ever wanted.* Last, smallest, entirely optional.

Settled early in the design (see `01` §7): **skills-first, plugin-later, MCP
optional**. The Python plugin is the primary surface — no running Obsidian
required. An MCP adapter is only worth building if a non-Hermes client needs
the same verbs; it would be a thin transport over the existing `vault/` module,
not a second implementation.

- ☐ If built: internal MCP server wrapping `obsidian_*` tools
- ☐ `obsidian_open`, `obsidian_active_file` (UI verbs only, need a live Obsidian)
- ☐ Graceful degradation when Obsidian is not running
- ☐ Raw `mcp__obsidian__*` tools hidden from agents

---

## Accomplished but not on the original list

Work that landed during P0–P2 but was not in the original trajectory:

- ☑ **Principle 7 codified** — mechanism-in-code / policy-in-config. Not an
  original task; became the governing rule after the open-source question.
  Enforced by `tests/test_portability.py`, which greps engine sources for
  leaked vault/folder/field names AND runs the whole engine against a PARA
  vault (`category`/`format`/`owner` fields) with a different layout.
- ☑ **`summary_field` (engine concept) + `description` advisory field** —
  user-requested note summaries in INDEX. Concept (not hardcoded name), so
  portable. Davide's vault uses `description`; a PARA vault would use `blurb`.
- ☑ **`obsidian_reference` tool + `engine_options` in `obsidian_context`** —
  the engine self-documents its config options and grant kinds. Solves the
  "a from-zero user / setup AI can't discover capabilities" problem without
  drift-prone docs.
- ☑ **`value_overrides` generalisation** — `status_overrides` is now shorthand
  for `{field, by, map}`, so per-class validation works on any schema, not just
  one with a field named `status`. Caught by the portability guard.
- ☑ **Audit trail as JSONL** (`.state/audit-log.jsonl`) — append-only,
  crash-safe, concurrent-safe. Originally spec'd as a JSON array.
- ☑ **Live vault seeded and exercised** — the developer's live vault has
  real notes, a working `.vault/roles.yaml`, generated INDEX/registry
  files, and an audit log written by the plugin itself.
- ☑ **Plugin is enabled in Hermes** and its tools are registered through the
  real plugin loader + tool registry (verified end-to-end). Tools appear after
  a Hermes restart, since tools load at startup.
- ☑ **Blank preset stops pre-claiming the system tree (2026-08-06).** The
  blank preset shipped a standing `system/**` write grant for `default`
  with NO tree — an invisible permission that silently made `default` the
  derived owner of any user-created root `system/` in a "you bring your
  own tree" vault. Fix: blank ships NO system grant (its "No `system/`,
  no `work/`" claim is now true), and the reserved tree became a growth
  action — `--role bind <NAME> --system` creates `system/` + config + the
  write/config grant (the standard preset's `default` block as a verb,
  mutually exclusive with `--domain` and `--manager`). The standard
  preset and the live vault are UNCHANGED — `system/` stays real and
  granted there; the flaw was blank-only. Consequence: the
  standing-grant carve-out in the manager's grant-anchor check is
  retired — a bind always creates the tree, so a missing `system/**`
  base is a rename symptom, flagged.

---

## Resume state (for a fresh session)

**What exists:** a complete, tested, enabled vault engine + installer. Plugin
at `~/.hermes/plugins/obsidian-vault/`. **213 pytest tests**, all green
(P4 added the issue ledger + maintenance sweep, 204 → 213 after tool wiring).
Clean-slate
E2E verified 2026-08-03: full install from zero profiles/vault; the standard
install ships the full five-agent set active (P3.7e); deny-by-default protects
unlisted agents. P4 verified 2026-08-04: from-zero re-scaffold + live sweep
+ ledger issue lifecycle end-to-end.

**To pick up:** **Stage C** (adoption — content migration), then P5 (MCP,
optional). P4 done: the vault-manager sweep (`obsidian_maintain`, daily 05:00
+ weekly Mon 06:00 cron on the vault-manager profile) + the issue ledger
(`obsidian_issue*` tools). Human-visible issue board deferred.

**Key files:**
- `vault/config.py` — inheritance resolver + uniformity contract
- `vault/grants.py` — five grant kinds, deny-by-default, glob matcher
- `vault/write.py` — validated, permissioned writes; `safe_join → grant → validate → write`
- `vault/generate.py` — INDEX + registry
- `vault/scaffold.py` — growth without redesign
- `vault/reference.py` — self-describing config reference
- `vault/paths.py` — `safe_join` traversal guard (the security chokepoint)
- `vault/audit.py` — append-only JSONL trail
- `tests/` — the regression + adversarial + portability suites

**Standing constraints:** never hardcode a tree/folder/field name in `vault/`;
the portability test enforces it. Every mutation goes through `write.py`'s
enforcement order. Generated files carry `<!-- generated -->` and are never
hand-edited. No credentials anywhere — redact as `[REDACTED]`.
`tests/test_entrypoint.py` must keep passing — it is the guard that the plugin
loads at all (a handler wired in `register()` but never defined took the whole
plugin down once; the smoke test catches that class).

**Next design decision (P3):** graph/query earns its complexity only if
`search` (grep-based) proves insufficient. Per A4, defer BM25/embeddings until
evidence demands it.

## Stage C — Adoption

- ☑ Retire v1 skill + `vault_navigator.py` — archived at
  `~/.hermes/skills-archive/obsidian-vault-v1-legacy` (P3.7 / D7)
- ☑ Agent profiles — `default`, `vault-manager`, `creative`, `dev`, `researcher`
  created, plugin-enabled, env-wired (P3.7b–P3.7e)
- ☑ `$OBSIDIAN_VAULT_PATH` on the starter vault — set per-profile by the installer
- ☐ Hand-migrate selected knowledge, one item at a time, via the owning agent
- ☐ Archive `hermes_workspace/`

---

## Checkpoints

Points where we stop and reassess rather than continuing on momentum.

| After | Ask |
|---|---|
| P0 | Did inheritance hold under the KNOWLEDGE test? Is the token saving real? |
| P1 | Do the grants feel right in use, or are they fighting the work? |
| P2b | Is the vault growing naturally, or is scaffold friction pushing toward premature structure? |
| P3 | Is graph/query earning its complexity, or would ripgrep have done? |

**Standing rule:** nothing after P1 is committed to. Several `00` §7 features are
expected to dissolve once write-time validation exists — do not build them out of
loyalty to the original document.
