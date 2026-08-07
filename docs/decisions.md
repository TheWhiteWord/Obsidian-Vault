# Design decisions (D1–D9)

The plugin's settled-decisions ledger, archived from `specs/` on
2026-08-07 when the design history was folded into this documentation
tree. Design decisions with consequences land here once agreed;
append-only — a decision is amended by a new entry, never rewritten in
place.

The current state these decisions shaped lives in this folder's
`concepts/` and `guides/`; this ledger records *why* they are the way
they are.

---

## D1. The plugin is a general engine; TWW's vault is one configuration

**The question.** The plugin must ship so that *anyone* can use and customize it.
At what stage does the plugin impose a design on the base state — a bare vault, or
a structure with features (domains, issues, maintenance)? Which is the product?

**The answer — neither, and both.** The engine already imposes nothing: the
portability test (`tests/test_portability.py`) greps every engine file for
tree/folder/field names *and* runs the whole engine against a foreign PARA vault
(`category`/`format`/`owner` fields, different layout). It passes. `SYSTEM`,
`CREATIVE`, `KNOWLEDGE`, `ISSUES`, `tww`, `vault_manager` exist nowhere in
`vault/*.py` — they are data in `.vault/config.yaml` and `roles.yaml`.

What actually exists is three layers, and keeping them distinct is the whole design:

| Layer | What it is | Lives where | Imposed? |
|---|---|---|---|
| **Mechanism** | validation, grants, derive-don't-declare, audit trail, scaffold | engine code | **imposed** — invisible, universal |
| **Convention** | a coherent named pattern: write-domains, per-domain knowledge, issues channels, role agents | starter preset (to be written, `examples/`) | **offered** — copied at init, never checked |
| **Configuration** | TWW's actual vault | your live vault + fixtures | **private** — yours |

The issue process, maintenance, and vocabulary lifecycle are already *mechanism* —
a stranger using the engine gets them for free without ever seeing `ISSUES/` in a
config. They are not features you'd impose on them; they are capabilities they'd
have to *opt out of*.

**Consequences**
- The engine hardcodes no tree/folder/field/agent name — enforced by the portability guard.
- The starter preset is a *suggestion*, shipped in `examples/`, never a default.
- TWW's `CREATIVE`/`SYSTEM`/`tww` stay private configuration, untouched by shipping.

---

## D2. Read grants are deny-by-default enforcement — uniform across every read surface

**The question.** Spec `01` §2.2 framed read as a "noise filter": "Read boundaries
only need to filter noise." Is that the right stance for a shipped plugin?

**The answer — no, not for the product.** The noise-filter stance was written for
a two-agent trust model where every actor was known. A stranger's vault has
unknown actors; the only stance that doesn't require trusting them is: an agent
sees exactly what its grants say, everywhere, or nothing.

**The rule.** `read` is deny-by-default enforcement, applied **uniformly** to every
read surface: `obsidian_search`, `obsidian_graph`, `obsidian_audit`,
`obsidian_context`. An agent queries `**` and receives nothing from where it
cannot read — in search *and* in graph traversal, *and* in the audit trail.

**The cost, stated.** A few explicit lines per agent in `roles.yaml`. This is
exactly how the scoping requirement ("contributor scope relevant to its domain,
but domains interlink") gets expressed: shared reference is shared **by glob, not
by global access** — `tww` reads `*/KNOWLEDGE/**`, and that one pattern is the
entire "knowledge is per-domain but shared selectively" feature. It generalizes:
a stranger's researcher agent grants `read: ["*/references/**"]` and the same
design works, no code change.

**Consequences**
- `obsidian_graph` and `obsidian_audit` currently bypass the read boundary (they
  are `needs_roles=False` in the entrypoint). They get the same filter as search.
- `obsidian_index` regenerates INDEX files with no grant check — it is the one
  write op with zero enforcement. Gate it on the agent holding any grant over the
  target folder.
- **Explicitly not built:** a full `obsidian_read` tool. Read grants are an
  enforcement filter over *plugin* surfaces; generic `read_file` access is
  out of scope by design. If the plugin ever ships to vaults with untrusted
  agents, `obsidian_read` is the first thing to add — this is recorded, not built.
- `obsidian_context` returns the caller's grants for the folder (§5 of `01`) —
  an agent learns whether it may write/register *before* being refused.

---

## D3. The starter preset uses neutral names — the relationships are the design

**The question.** If the plugin ships a named pattern at all, should it ship the
TWW names (`CREATIVE`/`SYSTEM`/`KNOWLEDGE`/`ISSUES`)?

**The answer — the preset ships role-neutral; TWW's vault keeps its names.**
The *relationships* are the design and the names are the cargo. The pattern that
generalizes:

- `work/` (or `personal/`) — the owner's write-domain
- `system/` — structural content (specs, decisions, logs)
- per-domain `references/` — curated knowledge, shared by glob
- `issues/` — append-only reporting channel
- agents: `owner`, `maintainer`, `contributor` — not `tww`, `vault_manager`

This works for a solo vault, a family wiki, or a team. `CREATIVE` stays in TWW's
live vault — it is configuration, and renaming configuration is not a product
decision.

**Consequence.** `examples/starter-vault/` (init target) carries neutral names,
clearly labeled *example*, never default.

---

## D4. Bootstrap: the plugin's first run creates only the minimal root

**The question.** What is the plugin's "base state" on first run?

**The answer.** Two files, as a proposal: root `.vault/config.yaml` (the
five-field schema + defaults + `summary_field`) and `.vault/roles.yaml`
(minimally `maintainer`, or empty = everything denied). `obsidian_scaffold`
already does propose-then-confirm; an init verb is ~50 lines on top of it. The
starter convention ships *beside* it in `examples/starter-vault/` — copyable,
never default.

From that moment on, everything is custom.

**Cost of the decision.** ~half a day of packaging work (init verb + example vault
+ README rewrite separating "the engine" from "a configuration"). Not a redesign
— the engine already is the engine.

---

## D5. Fix the existing code — no rebuild

**The question.** The review surfaced several defects. Work on the existing tree
or rebuild?

**The answer — fix.** Evidence: 108 tests green (115 after this session's
additions), the portability guard works exactly as designed, and every defect
found is a thin-layer gap — a missing 6-line handler, a broken glob, a stale
docstring — none architectural. A rebuild would discard a tested foundation and
re-introduce the drift the v2 model exists to kill.

**Consequence.** No rewrite of `vault/`. Bugs are fixed with regression tests.

---

## D6. Bug log — this session

| # | Bug | Fix | Regression guard |
|---|---|---|---|
| 1 | `register()` raised `NameError: _handle_delete` — the plugin loaded **zero tools** | added `_handle_delete` in `__init__.py` (6 lines, mirrors `_handle_write`) | `tests/test_entrypoint.py` — calls `register(FakeCtx())`, asserts all 10 tools register |
| 2 | `obsidian_search` `scope` glob treated as literal path — `scope="CREATIVE/**"` returned 0 results | `scope` now a glob filter via the shared `path_matches` glob language (`vault/grants.py`); grant intersection still applied after | `test_scope_glob_limits_the_scan` (+ cross-tree, no-widen variants) |
| 3 | word-boundary `\b` never matched non-word terms (`C#`, `C++`) | lookaround boundary `(?<!\w)…(?!\w)` | `test_non_word_terms_match` |
| 4 | snippet returned body head, not the match | match-window excerpt (±80 chars around first term) | `test_snippet_windows_around_match` |
| 5 | results in path order, not relevance | deterministic score: title hits ×2, body occurrences (capped), tag/link/frontmatter | `test_relevance_ranks_title_hits_first` |
| 6 | `folder` in code but absent from schema; `scope` in schema but broken | `folder` documented; `scope` fixed | schema updated |
| 7 | tools would light up against v1 vault (`$OBSIDIAN_VAULT_PATH` → `hermes_workspace/`, no root `.vault/config.yaml`) | `_available()` refuses a root without `.vault/config.yaml` | — (deployment guard) |

---

## D7. Conventions live in the skill, not the vault

**The question.** Where do "how to write well" rules live — the vault's
`SYSTEM/HANDBOOK/` (§10.5 of `01`), or the skill?

**The answer — the skill.** The vault holds *content*; the skill holds
*procedure*. §10.5's convention capture was dead design anyway — conventions got
written to HANDBOOK and nothing ever read them back. And a guide-on-how-to-write
is operating procedure, not vault content: writing it into the vault pollutes it
with plugin mechanics. HANDBOOK remains an **optional user convention** (Davide's
vault keeps one), independent of plugin mechanics.

**The split.**

| Tier | What | Lives where | Editable? |
|---|---|---|---|
| **Immutable references** | Obsidian formatting standards, the v2 model summary, the tool-surface protocol | bundled with the plugin via `ctx.register_skill` (namespaced `plugin:obsidian-vault`) | no — versioned with code, same for every vault |
| **Mutable conventions** | per-profile writing rules grown through interaction | the maintained file `<vault>-conventions.md` in the contributor skill's `conventions/` (per profile), created from the template | yes — created by the growth protocol, iterated through interaction |

The mutable tier **cannot** live in the plugin directory (overwritten on plugin
update) and **cannot** live in the vault (pollution). It lives beside the skill,
per profile. The skill names these files as *the place*; it does not own their
content.

**Skills own the procedure (D7, 2026-08-05).** Each role has its own skill —
`note-taking/obsidian-vault` for contributors (writing loop, formatting,
maintained conventions), `note-taking/obsidian-vault-management` for managers
(sweep, triage, growth). Tools stay content-free: `obsidian_context` is
folder-scoped (schema, grants, tags, siblings); `obsidian_reference` is the
option-discovery tool. The setup process writes a small, stable section into
the profile's `SOUL.md` naming the role's skill, so the agent always knows
the skill exists.

**Manager + setup.** Setup is the deterministic stage machine
(`scripts/setup.py --setup`); the manager skill holds maintenance judgment
and escalation rules.

**Old skill.** `note-taking/obsidian` is v1-legacy (three-tree layout,
`RESEARCH`, `TAXONOMY.md`, `vault_navigator.py`, `hermes_workspace`) —
unrelated to the plugin; the split (2026-08-05) gave the plugin its own
contributor skill at `note-taking/obsidian-vault`, next to it.

**Consequences**
- P3.6 dropped HANDBOOK-conventions wiring; D1 (2026-08-05) removed the
  `conventions_ref` pointer — context is folder-scoped, the reference is a
  discovery call.
- Stage C's "rewrite the skill as a 40-line protocol" is superseded by this
  architecture (bundled skill + references + conventions).
- The skill build is the **skill phase**, after P3.6.

---

## D8. `default` owns `system/`; `vault-manager` is maintenance-only

**The question.** Which profile is in charge of the system domain — a manager
profile, or the default profile?

**The answer — `default`, and `vault-manager` is deliberately not a system
owner.** Two reasons, both privilege boundaries:

1. The manager profile should only be given duties of *managing and
   maintaining the vault* — not authoring system content.
2. The system vault is a system-wide knowledge base and maintenance area whose
   functionality goes beyond the plugin. Only `default` has access to the whole
   `.hermes` application and can make changes system-wide, even beyond the app
   (this profile). It uses the plugin as one tool among many.

So `default` is the system owner (a contributor in vault terms), and
`vault-manager` is a lean maintenance agent: `meta`/`config`/`read` everywhere,
no prose write, no `.hermes` authority.

**Consequences**
- Starter `roles.yaml`: `default` → `write: [system/**]`, `read: [**]`;
  `vault-manager` → `meta: [**]`, `config: [**]`, `read: [**]` (no `write`
  over system prose).
- Skill composition: `default` gets base + contributor conventions (system
  owner); `vault-manager` gets base + contributor + manager (the maintenance
  agent carries the manager section). No profile gets both system-ownership
  and the `.hermes` reach unless the user makes it so.

---

## D9. Per-domain `knowledge/` shared with `researcher` — no top-level research vault

**The question.** Should research be a top-level vault (`research/`), or
per-domain `knowledge/` folders?

**The answer — per-domain `knowledge/`, `researcher` as shared domain.**
Each vault gets a `knowledge/` folder which is itself a vault; all knowledge
folders are domain of the researcher profile and shared with the profile that
holds them:

- `work/creative/knowledge/` → domain of `creative` **and** `researcher`
- `work/coding/knowledge/` → domain of `dev` **and** `researcher`

The researcher provides research for each profile; access follows domain.
Sharing is expressed purely in `roles.yaml` (`researcher` →
`write: [work/*/knowledge/**]`, domain profiles read `*/knowledge/**`) — no
engine change. This validates D1/D2: multi-profile access is pure config.

**The required capability it exposes.** Folders shared by multiple profiles,
includable *or excludable* in domain searches. Include already works
(`scope: work/creative/**` vs `scope: */knowledge/**`). **Exclude
(`!pattern` negation in the glob language) does not exist yet** — deferred to
P3.8; the include-side covers the main sharing flows.

---

## Open (explicitly deferred, not forgotten)

- **Exclude-negation in search** — ☑ **resolved in P3.8 (2026-08-04):** `scope`
  accepts a glob *or a list*; a `!`-prefixed entry is an exclusion
  (`scope_matches` in the shared glob language — include-any AND exclude-none).
  Grants stay positive-only; see Amendments.
- **`obsidian_move`** — `write` on source and destination, both INDEXes
  refreshed, dangling-link report returned. The biggest gap in the current surface.
- **Trash instead of permanent delete** — `.trash/` is already in `SKIP_DIRS`;
  route deletes through it, let the manager purge.
- **P4 manager** — build against current state (audit trail + on-write INDEX
  regen), not a `change-log.json` event log.
- **Starter preset + init verb** — D3/D4 made concrete.

---

## Amendments — 2026-08-03 (session close)

Status check against the shipped implementation. Append-only; nothing above was
rewritten.

- **D1** — "starter preset (to be written, `examples/`)" → **written**. The preset
  ships at `examples/starter-vault/`; the installer (`scripts/setup.py`) composes
  per-profile skills, seeds configs from `default`, enables the plugin per profile
  (symlink + `plugins enable` + `.env` agent), appends the SOUL directive, and
  scaffolds the vault (P3.7–P3.7e).
- **D3** — the preset's agents are `default` (owner), `vault-manager` (maintainer),
  `creative`/`dev`/`researcher` (contributors); trees are lowercase `system/`,
  `work/<domain>/`, per-domain `knowledge/`, `issues/` channels.
- **D4** — the minimal "init verb" grew into the full installer; the base state
  stays minimal and the convention ships beside it in `examples/`.
- **Open "Starter preset + init verb"** → **resolved** by the P3.7 series.
- **Open "P4 manager"** → **confirmed**: build on the audit trail + on-write INDEX
  regen; the manager profile + skill already exist (P3.7) — the phase is the
  maintenance logic + cron schedule.
- **New (P3.7e):** the standard install ships the **full five-agent set active** —
  nothing commented. Deny-by-default still protects *unlisted* agents. Custom
  profile sets are a future design consideration (spec `04` C1).
- **Install realities recorded** in `04-installation.md` (draft): default needs bare
  `hermes plugins enable`; re-run is safe-but-vocal; README scaffolds into the vault;
  verification = functional probe, not file presence.
- **P3.8 (2026-08-04)** — the **"Exclude-negation in search"** open item is
  resolved. `scope` accepts a glob or a list; `!`-prefixed entries are exclusions
  (`vault/grants.py:scope_matches` — include-any AND exclude-none, applied after
  the read-grant intersection). Grants stay positive-only: `path_matches` is
  unchanged, so a `!` in a grant pattern is a literal that matches nothing.
  Inline `!pattern` chosen over a separate `exclude_scope` parameter — the glob
  language gains negation (D3's wording), keeping one coherent query surface.
