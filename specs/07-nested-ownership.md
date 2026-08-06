# Nested Ownership — Domains, Subdomains, Content & Scope Directives (P7)

**Status:** design — not implemented.
**Related:** `01-vault-v2-model.md` (§3.3 config merge), `03-design-decisions.md`
(D1–D9), `05-maintenance-design.md` (P4 — superseded in part: distribution,
optimize), `06-growth-design.md` (P5/P6 — superseded in part: two-tier growth,
in-skill conventions). `TASKS.md` trajectory.
**Trajectory position:** Model → loader → boundary → derived artifacts → growth
→ navigation → maintenance → installation/growth (P5) → role mutation (P6) →
**nested ownership (P7)** → coder-plugin (P8) → MCP (P9).

This document redesigns the vault's **ownership model** around nested scopes:
domains owned by one profile, subdomains inside them owned by *another* profile,
and content folders that carry rules without changing ownership. It also moves conventions in-tree as **scope directives** and restates the
manager's optimize mode as scope-agnostic connection *proposing* (a skill
directive, not engine machinery). No code is written from this doc
until the design is confirmed (phase discipline: this changes what agents can
do — grants, delivery, the standard preset).

---

## §1 Locked decisions (2026-08-06)

| # | Decision | Rationale / cost |
|---|---|---|
| N-1 | **Three tiers, two ownership boundaries.** *Domain* = `work/<NAME>/`, owned by profile A. *Subdomain* = a subfolder owned by profile **B** (grants differ). *Content* = a subfolder with the **same** owner as its domain — no grant change, rules granularity only. The ownership boundary exists only when the profile differs; role is invisible to grants. | Decouples rules granularity from ownership granularity. Cost: a combined profile holding two roles over the same tree is content, not a boundary (accepted). |
| N-2 | **Derived ownership + shadowing, from canonical ownership globs.** Ownership derives ONLY from globs of shape `work/<d>/**` or `work/<d>/<s>/**` (one to three literal segments — `system/**`, `work/<d>/**`, `work/<d>/<s>/**` — terminal `/**` only; produced only by `bind`). Any other write glob is a *capability* glob: grants write where it matches, never establishes ownership, never shadows. `write`/`config` resolve only for the derived owner; ties refused at bind. No glob surgery on bind/unbind. | Preserves derive-don't-declare; one pure function, two rules, maximally testable; unbind is trivial (glob removed, shadowing lifts). Cost: the preset's wildcard write glob becomes literal per-domain globs (already planned, §3.2). |
| N-3 | **Shadowing applies to `write` and `config` only. `read` and `meta` stay generous** — any matching grant applies. | The domain owner keeps `read` + a `meta` backstop in subdomains (links/frontmatter fixes); knowledge stays connected where control is split. Cost: subdomain content is visible to the parent owner (a serving relationship — accepted). |
| N-4 | **Subdomain owner gains `read` over each parent domain at bind** (explicit glob `work/<d>/**`), alongside `write`/`config` on `work/<d>/<s>/**`. Omission = an isolated subdomain. | Ownership splits control, not knowledge: the subagent can verify link targets and self-serve within-domain links; the manager stops being the go-between for the common case. |
| N-5 | **Conventions move in-tree as scope directives**: `<scope>/.vault/conventions.md` at any depth, discovered by walking up exactly like config. Nearest file wins (override); absent rules fall back up the chain. | Conventions travel with their scope (rename-safe — the `<vault>-conventions.md` orphan problem dies), are vault content the sweep can see, and become the "reminders" the agent reads per scope. Cost: profile-skill `conventions/` dir + SOUL manifest retire (see §4.4). |
| N-6 | **Conventions override on conflict; fall back only on absence.** A subdomain's conventions win over its domain's; the domain's apply only where the subdomain says nothing. | The point of a second profile is different operating instructions (researcher vs writer) — nearest-wins-with-fallback is the contract. |
| N-7 | **Frontmatter relax surface:** `required: false` becomes legal at a child scope (nearest wins — replaces the accumulate-only invariant); `allowed_only` (existing) is the narrowing mechanism; **`format`/`multi` stay immutable.** | Scoped flexibility without structural drift. Cost: a tested invariant changes (`required accumulates only`) — test updates are part of this phase. |
| N-8 | **Issue delivery is ownership-routed — by the manager, not the engine.** Issue records have no addressee field; delivery = the manager targets the issue at the subdomain path (using the resolver as a shared utility) + the triage directive: *subdomain issues go to the subdomain owner first*. The domain owner's `meta` is a backstop resolver, not the addressee. | Subdomain issues go to the subagent first; nothing dead-ends; zero new engine machinery — the resolver is a utility, distribution is unchanged. |
| N-9 | **Manager optimize = connection *proposing* at any scope (skill directive).** No engine scan — connection discovery is LLM judgment. The manager skill's optimize mode directs: look across scopes for connections an owner may have missed; raise as suggestions (existing machinery: advisory-only, never auto-applied, TTL 14d), routed by the resolver. Within-domain = "did you miss this?" nudge; cross-domain = the manager is the *only* proposer. Dedupe remembers **declined-by-convention** (fingerprint), not just declined. | The manager proposes, the owner disposes — everywhere. Zero new engine machinery; the only new surface is the resolver utility + a skill directive. |
| N-10 | **No new grant surface: the manager/CLI remains the single writer of `roles.yaml`.** The domain owner *proposes* a subdomain; the manager executes `bind --domain` with a slashed path (`creative/knowledge`). | One grant-surgery surface, consistent with "never hand-edit roles.yaml". Cost: subdomain creation is a manager conversation, not fully self-serve. |

---

## §2 The model — three tiers, two boundaries

### 2.1 Tiers

| Tier | Path | Owner | Parent's rights | Conventions | Frontmatter |
|---|---|---|---|---|---|
| Domain | `work/<d>/` | profile A | — | `work/<d>/.vault/conventions.md` | domain config (extends root) |
| Content | `work/<d>/<f>/` | same profile A | full (it's theirs) | optional content conventions = "scope directive" | local config |
| Subdomain | `work/<d>/<s>/` | profile B | `read` + `meta` only | subdomain conventions **override** | local config, relax surface |

### 2.2 Ownership resolver

For a path `p`, ownership is derived from the live `roles.yaml`:

1. **Ownership globs** = write globs of canonical shape: one to three literal
   segments + optional terminal `/**` (`system/**`, `work/<d>/**`,
   `work/<d>/<s>/**`). Only `bind` produces them.
2. Candidates = agents holding an ownership glob that matches `p`.
3. Owner = the candidate with the **most segments** in its ownership glob
   (`work/<d>/<s>/**` beats `work/<d>/**`).
4. Tie (identical or prefix-overlapping ownership globs) → refused at bind
   time (the bind validates no two ownership globs share a prefix).

Every other write glob (wildcards, deeper paths) is a **capability glob**: it
grants write where it matches, but never establishes ownership and never
shadows an ownership glob. The old `work/*/knowledge/**` write glob is
capability-only by construction — which is why the preset moves the researcher
to literal per-domain globs (§3.2).

### 2.3 Shadowing scope

- `write` / `config` operations: resolved against the **derived owner** only.
- `read` / `meta` operations: resolved against **any** matching grant
  (unchanged semantics). This is what makes the parent owner a `meta`
  backstop and keeps the graph readable within a domain.
- **Principle: grants decide who CAN; conventions and triage routing decide
  who SHOULD.** Three agents can legitimately touch a subdomain note's links
  (owner `write`, parent `meta`, manager `meta` `**`) — accepted, deliberate.

### 2.4 Worked example — the researcher (standard preset)

- `bind researcher --domain creative/knowledge` grants: `write`/`config` on
  `work/creative/knowledge/**`, `read` on `work/creative/**`.
- `creative` holds `write`/`config` on `work/creative/**` — shadowed inside
  `knowledge/` (the knowledge ownership glob has more segments), so the writer
  can no longer write there; `read` on `work/creative/**` and a new `meta`
  backstop keep it visible and maintainable.
- The researcher links research → project notes and vice versa (read over the
  parent makes targets verifiable); the writer links project → research from
  its own notes. The domain reads as one coherent knowledge space.

---

## §3 Grants & bind surface

### 3.1 CLI: `--role bind PROFILE --domain <path>`

`--domain` accepts a single segment (today: `creative`) or a slashed path
(`creative/knowledge`):

| Case | Grants added |
|---|---|
| `--domain creative` | owner: `write`/`config`/`meta` on `work/creative/**` (meta is new — the backstop grant) |
| `--domain creative/knowledge` | subowner: `write`/`config`/`meta` on `work/creative/knowledge/**`, `read` on `work/creative/**`; parent owner gains nothing (its `meta` on `work/creative/**` already covers the subdomain) |

`unbind --domain creative/knowledge` revokes the subowner's globs; shadowing
lifts and the parent regains write. The tree is kept (as today).

### 3.2 Preset implication (sign-off A)

The standard preset restructures to the nested model:

- `researcher` = subdomain owner of `work/creative/knowledge` **and**
  `work/coding/knowledge` (two `bind --domain` calls), replacing the
  `work/*/knowledge/**` write glob (which survives as a *read* glob only).
- `creative` / `dev` lose `write` in their `knowledge/` (keep `read`, gain
  `meta` on their domain).
- README orientation text updates: "contributors write only their own domain"
  becomes "…and their domain's subdomains are read-only to them".

---

## §4 Conventions — in-tree scope directives

### 4.1 File & discovery

`<scope>/.vault/conventions.md` may sit at any depth (domain, content folder,
subdomain). Discovery mirrors config: walk up from the working folder; the
nearest file wins; the chain continues to the root (vault-wide conventions).
Files are machinery (in `SKIP_DIRS` — invisible to note-walks, INDEX, search).

### 4.2 Override semantics

- Conflicting rules: the nearest scope wins (subdomain > content folder >
  domain > vault root).
- Absent rules: fall back up the chain (an agent reads the resolved chain, not
  one file).
- SOUL = who the agent *is*; conventions = how to behave *for this scope*.
  The plugin's role system (contributor/manager) is unrelated to a
  "scope directive" — the docs use the latter term.

### 4.3 Context pointer

`obsidian_context` gains a one-line `conventions` pointer: the nearest
conventions file for the queried folder (e.g. `conventions:
work/creative/.vault/conventions.md`). The chain content itself comes from
`obsidian_conventions` (§4.5) — agents fetch the full directives only when the
task needs them, not on every context call.

### 4.4 Retirement (sign-off B)

- The profile-skill `conventions/` dir and `conventions/<vault>-conventions.md`
  retire. `templates/vault-conventions.md` becomes `templates/conventions.md`
  (scope-agnostic).
- The SOUL **Convention manifest** (the `<!-- add:` marker block) retires —
  the tree IS the registry now. `append_manifest_entry` / the add-marker guard
  go with it. The SOUL keeps a **Conventions** section, restated for the new
  design (§4.6): the manifest is gone, the maintenance duty stays.
- Migration (one-time, LLM step): existing `<vault>-conventions.md` content is
  folded into the domain scope's file per vault; the old file is deleted.
- Installer surface changes: `setup.py`, `vault_ops.ensure_conventions_file`,
  SOUL section writer, and their tests.

### 4.5 Edit path — `obsidian_conventions`, not a write carve-out

One file per **scope**, shared by every agent (conventions = scope policy;
agent-specific behavior stays in the agent's SOUL). The tool mirrors
`obsidian_edit_config` (the config-sibling of scaffold): policy prose gets a
policy tool, and `write.py`'s machinery wall keeps **no exceptions**.

- **Read:** `obsidian_conventions` returns the resolved chain (nearest file +
  fallbacks) for a folder. Any agent may read; the raw file is also readable
  in Obsidian (plain markdown in `.vault/`).
- **Edit:** the **derived owner of the scope** only — `obsidian_conventions`
  gates on `write` over the containing scope, writes `.vault/conventions.md`
  (audited, no INDEX), and skips note validation (it is not a note).
- **Forbidden:** the manager (never writes prose — suggests changes as
  issues); the parent owner over a subdomain's conventions (suggests via
  issue); `meta`-only holders.
- **Content folders:** same owner as the domain, so the domain owner edits
  their conventions directly (no boundary).

### 4.6 SOUL — restated, not removed

The manifest block dies, the maintenance duty survives. Contributor SOUL,
`### Conventions` (replaces "Convention maintenance" + "Convention manifest"):

    ### Conventions
    - Per-scope directives live in the vault: `<scope>/.vault/conventions.md`
      (root, domain, content folder, or subdomain — nearest scope wins).
    - Create one when a user preference about writing rules lands for that
      scope; maintain it as the scope's rules grow. You own the files of the
      scopes you own.

No registry — the tree is the registry, and `obsidian_conventions` surfaces
the chain (§4.5) with `obsidian_context` carrying the pointer (§4.3). The
manager SOUL stays conventions-free: the manager never writes prose and routes
convention requests to the scope owner. `append_manifest_entry` and the
add-marker guard retire with the manifest.

---

## §5 Frontmatter — the relax surface

| Operation | Current | New |
|---|---|---|
| Add a `required` field | allowed (accumulates) | allowed (unchanged) |
| **Drop a `required` field** | refused | **allowed at child scope (`required: false` — nearest wins)** |
| Narrow `allowed` | `allowed_only` (sets `restricted`) | unchanged |
| Widen `allowed` | union | unchanged |
| Redefine `format` / `multi` | `ConfigError` | **stays `ConfigError`** (sign-off C) |

The relax is scoped to validation of notes *in that scope*; parent scopes are
unaffected. The merged chain is re-resolved in memory before any write, so a
relax can never leak upward.

---

## §6 Issue delivery — ownership-routed by the manager

1. The **resolver is a shared utility**: grants use it for shadowing; the
   manager uses it to route. Issue records have no addressee field —
   distribution stays target + visibility, unchanged.
2. The manager targets an issue at the subdomain path (the derived owner is
   the addressee); the triage directive states: *subdomain issues go to the
   subdomain owner first*.
3. Resolve rights unchanged: `write` **or** `meta` over the target. The domain
   owner (`meta` backstop) can resolve subdomain issues but is not the
   addressee.
4. **Declined-by-convention dedupe:** a suggestion declined because the
   scope's conventions already cover it carries the conventions file's
   fingerprint in its `reason`; re-suggestion is allowed only when the
   fingerprint changes. No new fields — key dedupe + reason.

---

## §7 Manager optimize — connection proposing at any scope (directive)

A **skill directive**, not engine machinery — connection discovery is LLM
judgment, and the suggestion machinery already exists.

1. In optimize mode the manager reviews the graph across scopes (its view is
   complete — `read: ["**"]`) and looks for connections an owner may have
   missed.
2. Candidate connections → **suggestions** (existing contract: advisory-only,
   never auto-applied, TTL 14d, ledger records targeted at the note).
3. Routing by the resolver: within-domain nudge → the owner; sibling
   subdomains → both owners; cross-domain → both owners (the manager is the
   only proposer here).
4. The manager executes a link **only on explicit approval** (via `meta`).

Findings (health) and suggestions (connections) stay distinct, both advisory.

---

## §8 CLI / install surface changes

- `scripts/roles.py --role bind/unbind --domain` accepts slashed paths
  (subdomain form); `--dry-run` covers it.
- `scripts/setup.py` questionnaire: unchanged (presets still land two domains);
  the *resulting* `roles.yaml` differs (nested researcher grants).
- `scripts/vault_ops.py`: conventions seeding per-scope; SOUL manifest writer
  retired; bind/unbind subdomain form (slashed `--domain`); ownership-glob
  validation (canonical shape, prefix-overlap refusal).
- `vault/*`: ownership resolver (grants.py or new `vault/ownership.py`),
  relax surface (config.py merge), `obsidian_conventions` tool (schemas.py +
  new module), `obsidian_context` conventions pointer (context.py).
  **No maintain.py changes** — delivery and optimize are skill directives.
- Manager skill: triage directive (subdomain issues → subdomain owner first)
  + optimize directive (connection proposing, §7).
- Portability guard: no new engine-reserved names beyond `conventions`
  (already reserved); verify.

---

## §9 Tests

- **Resolver:** most-segments wins (`work/<d>/<s>/**` beats `work/<d>/**`);
  capability globs (`work/*/knowledge/**`) never establish ownership or
  shadow; tie/prefix-overlap → bind-time refusal; the knowledge/ example
  (researcher owns, writer shadowed, read+meta remain).
- **Shadowing:** `write`/`config` owner-only; `read`/`meta` generous; unbind
  lifts shadowing (writer regains write).
- **Relax surface:** `required: false` at child scope validates; parent scope
  unaffected; `format`/`multi` redefine still `ConfigError`; merge-chain
  violation refused before write.
- **Conventions:** nearest wins; absent falls back; rename of a domain or the
  vault leaves conventions attached to their scope; `obsidian_conventions`
  returns the resolved chain and gates edit on write-over-scope; `write.py`
  still refuses `.vault/` paths with no exceptions; machinery stays out of
  note-walks/INDEX/search.
- **Delivery:** resolver utility answers owner queries (manager routing);
  parent owner resolves via `meta`; declined-by-convention dedupe keyed on the
  conventions fingerprint.
- **Preset:** fresh-machine E2E (both presets) with the nested researcher —
  grant probes prove writer-no-write-in-knowledge, researcher read-over-parent.
- Portability + entrypoint suites stay green.

---

## §10 Open sign-offs (needed before implementation)

- **A — Standard preset behavior:** `creative`/`dev` lose `write` in their
  `knowledge/` (read + `meta` remain). Confirm the researcher-owns-knowledge
  shape is the shipped default.
- **B — Conventions retirement:** profile-skill `conventions/` dir, the SOUL
  Convention manifest, and `<vault>-conventions.md` are removed in favour of
  in-tree scope files — **including the §4.5 edit path** (the new
  `obsidian_conventions` tool; manager and parent owner propose via issues;
  `write.py` keeps its machinery wall intact) **and the §4.6 SOUL restatement**
  (manifest gone, maintenance duty kept as a Conventions section in the
  contributor SOUL). Confirm the install-surface churn and the one new tool are
  accepted.
- **C — Relax bounds:** `format`/`multi` stay immutable even inside a
  subdomain's own config.
- **D — Phase ordering:** nested ownership (P7) lands before the coder-plugin
  interaction work.
