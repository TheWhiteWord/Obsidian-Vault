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

Per-profile skill dir (`<profile>/skills/obsidian-vault/`):

| Entry | Type | Source |
|---|---|---|
| `SKILL.md` | symlink → bundle | immutable, update-propagating |
| `references/` | symlink → bundle | immutable, update-propagating |
| `templates/` | symlink → bundle | immutable, update-propagating |
| `conventions/contributor.md` | real file, **refreshed from bundle each run** | immutable role directive (contributor profiles + combined) |
| `conventions/manager.md` | real file, **refreshed from bundle each run** | immutable role directive (manager + combined) |
| `conventions/<vault>-conventions.md` | real file, **never touched by the installer** | maintained per-vault/domain conventions (contributors only) |

Invariant: the installer never deletes or overwrites `conventions/<vault>-conventions.md`. Role directives are refreshed (they are immutable, bundle-owned); the maintained file is created by the growth protocol from `templates/vault-conventions.md` and grows through interaction.

### 2.2 Role routing in base SKILL.md

The base SKILL.md carries a routing section (composition replaced by routing):

- contributor profile → read `conventions/contributor.md` (role directive) + the `<vault>-conventions.md` files for the domains it manages
- manager profile → read `conventions/manager.md` only. **A manager is not a contributor** (2026-08-04, verified against grants: meta/config/read, no content write — needs none of the authoring discipline); it does not maintain conventions
- one-profile combined → read both directives + per-vault convention files

### 2.3 Copy-on-write escape hatch

If a profile must customise a reference (e.g. a profile-specific tool protocol): break the symlink for that file, copy the bundle version, edit the copy. Document this once in the protocol reference (§4). It is a deliberate, rare act — the default is shared immutable references.

### 2.4 Tests

- symlinked SKILL.md + references resolve via `skill_view` (probe pattern)
- conventions survive an installer re-run (the survival regression)
- conventions seed on first install, never clobber on re-run
- portability + entrypoint suites stay green (the role-routing section is engine-free prose, but the installer changes are real)

---

## §3 P5b — SOUL, references, presets, edit tool

### 3.1 SOUL.md — one `## Vault` umbrella with `###` subsections

`ensure_soul_sections` writes a single anchored block (2026-08-04
correction: nested under one heading, not flat). Each subsection is a
pointer (tools + references), never prose instruction:

1. **`## Vault`** — one-liner: operating this vault — tools, conventions,
   issues, and maintenance; each subsection points at what governs it.
2. **`### Vault operations`** — the existing paragraph (load the
   `obsidian-vault` skill first; it routes to tools + conventions).
3. **`### Issues`** — raise via `obsidian_issue`; list via
   `obsidian_issue_list`; resolution is grant-gated. Contributors raise,
   they do not run the maintenance sweep — that is the manager's job
   (`references/maintenance.md`).
4. **`### Convention maintenance`** — role directives are immutable; the
   maintained file is `conventions/<vault>-conventions.md`, created per
   vault/domain from `templates/vault-conventions.md` and registered in the
   manifest. Managers: no per-vault convention files (contributor process).
5. **`### Convention manifest`** — a strict, parseable markdown list of
   convention files relevant to this profile. Role directives listed as
   immutable; maintained per-vault files appended by the growth protocol.
   Starter: empty-but-directed (a header + one commented example).

### 3.2 Role variants

Three SOUL templates, each assembled from the four subsections with
role-appropriate pointers (2026-08-04 correction: manager is NOT a
contributor — no contributor.md, no per-vault convention maintenance):

| Variant | Subsections | Convention pointers |
|---|---|---|
| contributor | all | `conventions/contributor.md` (role directive) + `references/obsidian-formatting.md`, `references/config-authoring.md`; maintained file `<vault>-conventions.md` |
| manager | all | `conventions/manager.md` (role directive) only + `references/maintenance.md`, `references/issues.md`; no convention maintenance |
| combined (one-profile) | all | both role directives + per-vault convention files |

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

### 4.1 Subdomain by contributor (Eg1 — "recipes")

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
| Field suggestion, SOUL drafting, topic interpretation | LLM | agent, guided by references |
| fs + config writes, grant lines, profile creation, manifest append | mechanical | `setup.py` subcommands (`--add-domain`, `--add-contributor`, `--add-subdomain`) |
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
