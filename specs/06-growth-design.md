# Growth Design — Installation & Vault Growth (P5)

**Status:** design — not implemented.
**Related:** `TASKS.md` P5 (P5a skill overlay · P5b SOUL + references + presets + edit tool · P5c growth protocol), `03-design-decisions.md` (D1–D9), `04-installation.md` (install spec, superseded in parts), `05-maintenance-design.md` (P4).
**Trajectory position:** Model → loader → boundary → derived artifacts → growth → navigation → maintenance → **installation/growth** → coder-plugin (P6) → MCP (P7).

This document designs how the vault **grows** after installation: what a profile may create, which config statements are digestible by the engine and what they do, and the interactive protocol an agent follows. No code is written from this doc until the design is confirmed.

---

## §1 Locked decisions (2026-08-04)

| # | Decision | Rationale / cost |
|---|---|---|
| D-1 | **No role-split tool registration.** All 14 tools register for every profile; differentiation lives in the convention layer (SOUL/skill); grants are the hard backstop. | One coherent surface; portability guard + entrypoint test + one-profile setup stay simple. Cost: contributors *see* manager tools (accept). |
| D-2 | **Two-tier growth, engine-native.** Manager owns root `.vault/` (config + roles) and creates full domains; a domain owner self-serves subdirectories + local `.vault/config.yaml` inside its own tree. | `obsidian_scaffold` gates on the `create` *operation* (write kind), not the `config` grant — verified in `vault/scaffold.py`. The manager round-trip is not needed for subdomains. |
| D-3 | **Skill overlay = symlink base, real `conventions/`.** `SKILL.md`, `references/`, `templates/` symlink to the bundle (update-propagating, base intact); `conventions/` is a real per-profile dir, seeded copy-if-missing, **never removed on re-run**. | Probe-proven 2026-08-04: Hermes resolves symlinked SKILL.md + symlinked `references/` dirs. Fixes today's survival bug (`install_skill` does `shutil.rmtree` on the whole profile skill dir). |
| D-4 | **Blank preset ships a neutral `roles.yaml`** — deny-by-default, no five-agent defaults. | Today `--preset blank` reuses the starter's five-agent roles (confirmed gap). |
| D-5 | **Starter roles: contributors gain `config: ["work/<domain>/**"]`.** | A domain owner can evolve a subdomain's fields mid-life, not just at scaffold time. Root `.vault/` stays manager-only (the glob can't reach it). **Condition (Davide):** contributors must have — or be able to retrieve — the config syntax + implications reference (see §3.3). |
| D-6 | **`obsidian_edit_config` tool is built in P5b.** | Verified gap: no tool-mediated way to edit an *existing* config today — `obsidian_scaffold` refuses ("already has a config; edit it directly"), only vocabulary registration is tool-mediated. Without the tool, the D-5 grant means hand-editing raw YAML, which violates D-5's condition. |
| D-7 | **Coder-plugin interaction = P6**, separate research + design. | Davide 2026-08-04: a specific feature deserving its own background work. |

---

## §2 P5a — Skill overlay

### 2.1 Symlink map

Per-profile skill dir — `<profile>/skills/note-taking/` (2026-08-05 split:
two role-owned skills; `obsidian-vault` = contributor, `obsidian-vault-management`
= manager; a one-profile setup holds both):

| Skill | Entry | Type | Source |
|---|---|---|---|
| obsidian-vault (contributor) | `SKILL.md`, `references/`, `templates/` | symlinks → bundle | immutable, update-propagating |
| obsidian-vault (contributor) | `conventions/` | real dir | home of the maintained file |
| obsidian-vault (contributor) | `conventions/<vault>-conventions.md` | real file, **never touched by the installer** | maintained per-vault/domain conventions (contributors only) |
| obsidian-vault-management (manager) | `SKILL.md`, `references/`, `templates/` | symlinks → bundle | immutable, update-propagating |

Invariant: the installer never deletes or overwrites
`conventions/<vault>-conventions.md`. It is created by the growth protocol
from `templates/vault-conventions.md` and grows through interaction. There
are **no role directives** — each role's rules live in its skill's SKILL.md
(the split removed contributor.md / manager.md). Skill-level role alignment
removes a role's other skill's symlinks, but never touches `conventions/`
or copy-on-write breaks.

### 2.2 Role → skill (the split, 2026-08-05)

- contributor profile → `note-taking/obsidian-vault` (the authoring skill: writing
  loop, formatting, maintained conventions)
- manager profile → `note-taking/obsidian-vault-management` only. **A manager is
  not a contributor** (verified against grants: meta/config/read, no content
  write — needs none of the authoring discipline); it does not maintain
  conventions
- one-profile combined → both skills (roles unioned)

### 2.3 Copy-on-write escape hatch

If a profile must customise a reference (e.g. a profile-specific tool protocol): break the symlink for that file, copy the bundle version, edit the copy. Document this once in the protocol reference (§4). It is a deliberate, rare act — the default is shared immutable references.

### 2.4 Tests

- symlinked SKILL.md + references resolve via `skill_view` (probe pattern)
- conventions survive an installer re-run (the survival regression)
- `conventions/` dir created on install (contributor skills), the maintained
  file never seeded, never clobbered on re-run
- portability + entrypoint suites stay green (role→skill mapping is
  installer-side; the engine is role-agnostic)

---

## §3 P5b — SOUL, references, presets, edit tool

### 3.1 SOUL.md — one `## Vault` umbrella with `###` subsections

`ensure_soul_sections` writes a single anchored block (2026-08-04
correction: nested under one heading, not flat). Each subsection is a
pointer (tools + references), never prose instruction:

1. **`## Vault`** — one-liner: operating this vault — tools, conventions,
   issues, and maintenance; each subsection points at what governs it.
2. **`### Vault operations`** — load the role's skill first (the
   `obsidian-vault` / `obsidian-vault-management` skill); it holds the
   writing loop / management procedure.
3. **`### Issues`** — raise via `obsidian_issue`; list via
   `obsidian_issue_list`; resolution is grant-gated. Contributors raise,
   they do not run the maintenance sweep — that is the manager's job
   (`references/maintenance.md`).
4. **`### Convention maintenance`** — the maintained file is
   `conventions/<vault>-conventions.md`, created per vault/domain from
   `templates/vault-conventions.md` and registered in the manifest.
   Managers: no per-vault convention files (contributor process).
5. **`### Convention manifest`** — a strict, parseable markdown list of
   convention files relevant to this profile; maintained per-vault files
   appended by the growth protocol. Starter: empty-but-directed (a header
   + one commented example).

### 3.2 Role variants

Three SOUL templates, one per skill role (2026-08-04 correction: manager is
NOT a contributor; 2026-08-05 split: role → skill, no role directives):

| Variant | Skill | Convention pointers |
|---|---|---|
| contributor | `obsidian-vault` | `references/obsidian-formatting.md`, `references/config-authoring.md`; maintained file `<vault>-conventions.md` |
| manager | `obsidian-vault-management` | `references/maintenance.md`, `references/issues.md`; no convention maintenance |
| combined (one-profile) | both skills | maintains conventions; dual-role operational bullet ("sweep findings about your own domains are yours to fix; about other domains, raise them") |

All lean; every bullet names a tool or a reference, nothing more.

### 3.3 `references/config-authoring.md` — the config DSL (Davide's clarification)

> The way these `config.yaml` files work amongst themselves and for themselves must be expressed somewhere, so an agent that writes one knows what that does: what possibilities are digestible by the system, what the implications are, and how they affect search and creation.

This is the **config-authoring reference** (renamed from the earlier "field-patterns" idea — the scope is the whole DSL, not just field patterns). Contents:

**3.3.1 Location and inheritance.** `.vault/config.yaml` at any tree level. `resolve_config` merges **upward**: a child config inherits from its ancestors; the effective schema for a folder is the merge of every config from the root down to it. `obsidian_context` shows the *resolved* result.

**3.3.2 Top-level keys** (engine options — authoritative list always available via `obsidian_reference`):
`fields` · `defaults` · `tags` (`mode`) · `validation` · `vocabulary` (promotion thresholds) · `paths` (state relocation) · `conventions` (skill pointer) · `roles` lives in the separate `roles.yaml`.

**3.3.3 Per-field keys and merge rules** (verified in `vault/config.py`):

| Key | Semantics on inheritance |
|---|---|
| `allowed` | **union** — child adds to inherited vocabulary (order-preserving, deduped) |
| `allowed_only` | **replaces** the inherited vocabulary; sets `restricted` — child opts into a narrower set |
| `required` | **accumulates only** — a child may add a requirement, never drop one (`ConfigError` if it tries) |
| `multi` / `format` / `vocabulary` / `default` | child wins, but redefining `format`/`multi` is a `ConfigError` (uniformity contract) |

**3.3.4 Implications map — what a statement *does* (the "digested by our tools" part):**

| Engine surface | Effect |
|---|---|
| `obsidian_write` | `validation.fields: blocking` refuses non-conforming notes; `allowed_only` narrows what passes; `required` makes a field mandatory; tags advisory per `validation.tags` |
| `obsidian_search` / `obsidian_graph` | vocabulary fields shape what's searchable/traversable; a restricted field yields a smaller namespace |
| `obsidian_context` | returns the effective resolved schema + vocabulary + your grants; drives suggestions |
| INDEX / registry | `description` (advisory `summary_field`) surfaces in INDEX; type/kind shape how notes are grouped |
| `obsidian_maintain` | observed values past the `vocabulary` threshold get promoted (config grant) |

**3.3.5 What an agent may do / must not do:**

- MAY: `obsidian_scaffold` (new subfolder + delta, write-gated), `obsidian_edit_config` (existing configs, config-gated, structural keys need user confirmation), `obsidian_reference` (self-doc), `obsidian_context` (resolved view).
- MUST NOT: hand-edit raw YAML (the edit tool exists precisely to close this), drop an inherited `required`, touch root `.vault/` (out of a contributor's glob), edit `roles.yaml` (manager-only, always).

**3.3.6 Canonical examples.** The starter root config + the KNOWLEDGE config (both real, verified) as the two anchor examples — one broad, one restricted (`allowed_only: [knowledge]`).

### 3.4 New references

- `references/issues.md` — ledger lifecycle: raise / list / resolve; grant-filtered lists; TTLs (14d suggestions, 30d prune); raise ≠ fix.
- `references/maintenance.md` — the sweep: `obsidian_maintain` modes (delta/maintain/optimize), who runs it (manager), what each check flags, how findings become ledger records.

### 3.5 Neutral blank preset

`--preset blank` currently reuses the starter's five-agent `roles.yaml` (confirmed gap). P5b ships a neutral preset:
- `roles.yaml`: only `default` (system owner, as today) + a commented manager stub; deny-by-default for everything else.
- `config.yaml`: minimal root config (the five core fields, no domain vocabulary).
- README orientation adjusted to "no domains yet — ask the manager to create one".

### 3.6 `obsidian_edit_config` — tool shape (design)

- Gate: `edit_config` operation → `config` grant over the target config path (D-5 gives contributors `config` on their own tree).
- Target: an existing `.vault/config.yaml` (relative path).
- Delta: dict of field changes; **reuses** `scaffold._delta_against_inherited` + `_needs_confirmation` so edit and scaffold cannot drift (STRUCTURAL_KEYS → explicit user confirmation, mirroring scaffold).
- Write path: same merge semantics as `resolve_config`; never a raw rewrite of the file.
- Refusals: cannot edit `roles.yaml`; cannot drop an inherited `required`; cannot redefine `format`/`multi`; `edit_config` never touches grants.
- Audited (like scaffold).
- Schema + tests land in the P5b implementation, not here.

---

## §4 P5c — Growth protocol

Reference doc `06` companion: `references/growth-protocol.md` (or the SOUL manifest pointer). The three canonical flows come from Davide's 2026-08-04 examples. Every flow splits into **LLM steps** (suggest fields, draft SOUL, interpret topic — agent judgment) and **mechanical steps** (fs + config + manifest writes — subcommands, tested).

## 4 Growth flows

> The mechanical steps in §4.1–4.3 name the P5c-era subcommands
> (`--add-subdomain` / `--add-contributor` / `--add-domain`). §4.5 supersedes
> them with the `--role` verb family; the flows themselves are unchanged.

### 4.1 Subdomain by contributor (Eg1 — "recipes/keto")

*Who:* domain owner + user, mid-conversation. *Grant basis:* D-2 (scaffold is write-gated).

1. Contributor proposes: `obsidian_scaffold(path, intent, proposed, confirm=false)` → delta shown (e.g. `type.allowed_only: [Recipe]`, `source.required`, `retrieved.required`).
2. User confirms name + fields; contributor may suggest a field setup (LLM step, informed by `references/config-authoring.md` patterns).
3. Mechanical: scaffold creates the directory + `.vault/config.yaml` delta + regenerates parent INDEX.
4. Mechanical: `--add-subdomain` appends the convention-manifest line to this profile's SOUL.
5. Report: directory live, schema applied, what changed.

The new directory is part of the contributor's own domain by default — no grant change, no manager involvement.

### 4.2 Full domain by manager (Eg3 — "RECIPES" + profile BOB)

*Who:* manager. *Grant basis:* manager holds `config`/`meta`/`read` on `**`.

1. Manager asks: name; existing profile or new? If new, name (LLM step: `hermes profile create`, config seed, plugin enable — the P3.7b machinery, now a subcommand `--add-contributor`).
2. Manager proposes the field base + domain-specific suggestion (LLM step).
3. User describes topic/domain; manager drafts a **tailored SOUL** for BOB (LLM step) or writes the standard variant.
4. Mechanical: `--add-domain` creates `work/<domain>/` + `.vault/config.yaml` + `roles.yaml` grant line + SOUL manifest entry.
5. Report: domain + profile + grants + SOUL, and what to do next.

### 4.3 Custom install (Eg2 — "LIBRARY" vault, manager Billy)

*Who:* agent driving a fresh install. *Grant basis:* D-4 (neutral preset).

1. Agent asks: custom or standard default? (Brief difference — standard recreates the five-agent starter; custom is a bare vault.)
2. Custom: vault location + name; manager profile (new "Billy" or existing) — LLM + mechanical.
3. SOUL tailoring choice: full tailored manager SOUL vs basic editable default (LLM step).
4. Mechanical: vault scaffolded (neutral preset, no domains), manager profile created, overlay installed, SOUL written.
5. Report: vault created, manager = Billy, no domains yet — "to start using the vault, ask Billy to create a domain" (§4.2).

### 4.4 LLM-step vs mechanical-step split (summary)

| Step | Kind | Where |
|---|---|---|
### 4.5 Role mutation — the `--role` verb family (2026-08-05)

**Problem.** Setup is add-only: the questionnaire binds roles once, and growth
only ever *adds* (contributors, domains, subdomains). Install choices are
sticky — no post-install way to bind an existing profile, promote/demote,
hand off the manager role, or unbind. Decisions locked with Davide
(2026-08-05): single vault per profile (no multi-vault tool surface);
unbind removes the `## Vault` SOUL block entirely; **a manager must always
exist** — the escape is `transfer`, never a manager-less vault; `default` is
unbound-able (with a warning — the skill stays reachable as
`plugin:obsidian-vault`); domain unown keeps the tree (notice points at
manual removal).

**The verb.** One coherent surface (no parallel flag families):

```
--role bind PROFILE [--new] [--manager] [--domain NAME] [--config FILE]
--role unbind PROFILE [--domain NAME]
--role transfer PROFILE --to SUCCESSOR [--domain NAME]
--role list
```

All take `--vault PATH` + `--dry-run`. The old `--add-contributor` /
`--add-domain` / `--add-subdomain` / `--owner` / `--config` flags are
removed — `bind` absorbs them.

| Action | What it does |
|---|---|
| `bind PROFILE` | profile-level bind: `--new` creates the profile first; skill overlay + SOUL variant + config seed + plugin enable + env, per role (`--manager` or contributor). Grants: manager gets `meta/config/read: ["**"]`; a bare contributor gets **no content grant** yet — domains come next |
| `bind PROFILE --domain NAME` | contributor-only (manager holds no content grants, D3): create `work/<name>/` + `.vault/config.yaml` (stub or `--config`) if missing; grant `write/append: ["work/<name>/**"]`; ensure the conventions file + SOUL manifest entry |
| `unbind PROFILE` | full unbind: grant block **commented out** (comment-preserving, deny-by-default, re-bind-able — the blank preset's manager-stub pattern); SOUL `## Vault` block **removed**; skill overlay uninstalled (symlinks + this vault's conventions file + empty `conventions/`); vault env vars removed; notice: owned domain trees remain, remove manually if wanted. **Refuses when PROFILE is the manager** (vault must keep a manager) and when PROFILE is the last bound profile |
| `unbind PROFILE --domain NAME` | unown one domain: the domain's globs removed from the grant block (line surgery; empty kind lines dropped; an emptied block is commented out), the domain's manifest entry removed, tree kept + notice. No SOUL/skill change |
| `transfer PROFILE --to B` | manager handoff: B gets the manager grant + manager/combined skill + SOUL (combined when B already holds content grants); PROFILE loses the manager grant (commented) and is **re-derived from its remaining grants** — contributor SOUL/skills if it still owns content, full unbind if not |
| `transfer PROFILE --to B --domain NAME` | domain owner change in one step: grant moved A→B, manifest entry moved, both SOULs untouched (both remain contributors) |
| `list` | who is bound: per profile — role variant (contributor/manager/combined), skill installed, SOUL block present, grants by kind, domains owned |

**Derivation — grants are the truth.** A profile's role is derived from its
live roles.yaml block: the active `meta/config/read: ["**"]` block ⇒
manager; any content-grant globs ⇒ contributor; both ⇒ combined; none ⇒
unbound. The SOUL block is the *bind marker* (present ⟺ bound), written by
`ensure_soul_sections`, removed by the new `remove_soul_sections`. The
setup questionnaire remains the initial-creation flow; re-running it after
mutations re-binds per its answers (documented: setup is "start over").

**Invariants.** Manager always exists (`unbind`/`transfer` enforce);
managers never hold content grants; `default` unbound-able with a warning;
domain trees are never deleted by the layer; every write stays
comment-preserving + idempotent + dry-run-capable.
| Field suggestion, SOUL drafting, topic interpretation | LLM | agent, guided by references |
| fs + config writes, grant lines, profile creation, manifest append | mechanical | `setup.py` `--role` subcommands |
| Everything auditable | mechanical | audit log + SOUL manifest |

The agent is *aided through the process* (the user's ask): it knows the options at each stage, presents them, and executes mechanically — it does not improvise filesystem surgery.

---

## §5 Test strategy

- Subcommand dry-runs (no side-effects) + full runs against a scratch `HERMES_HOME` (existing pattern).
- Grant correctness: contributor can scaffold + edit config inside its tree; cannot reach root `.vault/` or `roles.yaml`; manager can do both.
- Manifest updates: append idempotent, no prose rewrite.
- Symlink overlay: resolves, conventions survive re-run (regression for the rmtree bug).
- Existing 213-test suite stays green; entrypoint + portability guards remain the load/fork gates.

---

## §6 Open items / checkpoints

| Item | Status |
|---|---|
| `obsidian_edit_config` exact schema + tests | design here (§3.6); implementation in P5b |
| Starter-roles regression cost (D-5) | accepted; update `test_starter_roles_ship_full_agent_set_active`-adjacent expectations |
| Copy-on-write escape hatch documentation | **done in P5c** — `references/growth-protocol.md` §7 |
| Growth-protocol interactive reference | **done in P5c** — `references/growth-protocol.md` (bundle; registered in SKILL.md References) |
| Human-visible issue board (from P4) | still deferred — unchanged |
| MCP transport | demoted to P7 — unchanged |

**Checkpoint (per trajectory's standing rule — nothing after P1 is committed to):** asked after P5b — *is the two-tier growth model earning its complexity, or is the grant split fighting the work?* **Answer (2026-08-04): the model stands.** P5c's three subcommands map 1:1 onto the tiers (manager: contributor+domain; owner: subdomain), the engine's grants enforce the split with zero new enforcement code (tests prove it via `load_roles`), and the growth protocol's refusals (existing-grant owner, missing profile, non-owner) are the design's own guards — not friction the design fights.
