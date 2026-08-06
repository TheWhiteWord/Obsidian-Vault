# Full SOUL.md for Role Profiles (P8.1)

**Status:** design — approved 2026-08-06 (Davide); implementation phase.
**Related:** `reference/soul-md-research.md` (the raw Hermes findings),
`06-growth-design.md` (§3.1–3.2 — the `## Vault` block design this
extends), `03-design-decisions.md` (D1 — differentiation lives in the
convention layer), `04-installation.md` (profile creation), `TASKS.md`
trajectory.
**Trajectory position:** … → role mutation (P6) → nested ownership (P7)
→ **full role SOULs (P8.1)** → coder-plugin (P8) → MCP (P9).

This phase ships a **full SOUL.md** for the standard preset's role
profiles — identity + style prose in front of the existing anchored
`## Vault` block — with a content-based replace-vs-append rule that
mirrors Hermes' own "safe to overwrite" precedent
(`is_legacy_template_soul`, `hermes_cli/default_soul.py`). It also
designs (but defers the mechanics of) the **generation step**: composing
a full SOUL when a *new profile is created for a new domain*.

---

## §1 Locked decisions (2026-08-06)

| # | Decision | Rationale / cost |
|---|---|---|
| S-1 | **Full SOUL templates ship for five identities:** `manager`, `system-owner`, `creative`, `researcher`, `dev`. Each = `# Identity` (2–3 lines) + `# Style` (4–6 lines) + the **existing anchored `## Vault` block unchanged** (the role's own block). | The vault reads as one capability among the identity — the "functionality amongst others" framing. Cost: five files to maintain; the vault block is already generated, so the templates carry only the prose. |
| S-1b | **Identities are decoupled personas (2026-08-06 review).** The contributor identities state who the agent IS (creative partner, researcher, developer, system owner), not that it belongs to a vault — the vault is a tool they use as memory layer + domain knowledge, expressed by the anchored block. **The manager is the one exception:** its identity is directly connected to the vault (its role IS the vault's health). | The agents have roles and identities beyond any one tool. Cost: the block is the only vault-facing surface for contributors — the identity prose never names the vault. |
| S-2 | **Replace-vs-append is content-based, one rule:** a SOUL.md that is missing, *exactly* `DEFAULT_SOUL_MD`, or a known legacy template → replace wholesale with the full role SOUL; anything else → append/replace **only the anchored vault block**, never touch the rest. | Mirrors Hermes' own guarantee: template-matching content carries zero user intent and is provably safe to replace (`is_legacy_template_soul`). Cost: a pristine check against `DEFAULT_SOUL_MD` text — a constant copy, kept in sync. |
| S-3 | **`default` is always append-only — even when pristine.** It receives the vault section, never a full soul, never a role identity. | `default` is the user's primary profile; claiming its identity is out of the plugin's scope. Its behavior *in relation to the vault* is expressible as a section; its identity is the user's. (Davide, 2026-08-06.) |
| S-4 | **The manager HAS a full soul (2026-08-06 review — overrides the original "no identity for manager").** It applies when a **NEW profile is created for the manager role**: standard always (its `vault-manager` is created); blank only on the `create` answer (a `default`/`existing:NAME` manager keeps its own identity, block-only). Combined (one-agent) and a bare blank contributor still get block-only — no single identity exists to write. | The manager is an important part of the system even without a domain; its identity is vault-connected by nature. The "new profile" gate matches the other roles: identity is only ever claimed on profiles the installer creates. Cost: the manager template + wiring; a manager mapped to an existing profile keeps block-only. |
| S-5 | **The `system-owner` template ships and applies to any profile created with `--system`** (a user may want a dedicated system-owner profile, not `default`). | Growth `--role bind <NAME> --new --system` already creates the tree + grants; the template gives that profile an identity. Cost: a template whose standard-preset consumer is `default` — which S-3 exempts — so its real consumer is the growth path. |
| S-6 | **Generation trigger = new profile created *for* a new domain** (`bind --new --domain X`). Domain-bind to an *existing* profile does not generate (no identity context; the profile's identity isn't ours to claim). Setup's questionnaire does not generate. | Identity generation needs who+what (the new profile's role and the domain's purpose) — context that exists exactly when a profile is born for a domain. Cost: the manager (agent) must draft prose — an LLM step, separate from the mechanical write. |
| S-7 | **Generation/update mechanics = `--soul FILE` on `bind` (implemented this phase).** Composed identity+style text in, engine preserves the managed block and writes the prose ahead of it (`_apply_soul_prose`); `ensure_soul_sections` refreshes the block. Refuses a customized, unmanaged SOUL (never claims an identity the installer did not create). | One coherent surface, tested, dry-run aware; the LLM step (drafting) stays in the manager's skill, the mechanical step stays in the CLI. Cost: new flag + tests. |
| S-8 | **Domain-add review notice (note c, 2026-08-06).** `bind --domain X` on a profile that already has identity content ahead of the block (`_soul_has_identity` — any non-empty, non-pristine prefix, deliberately FORMAT-AGNOSTIC so a user reformatting the prose cannot break it) prints: its identity may need review after adding the domain — the manager drafts an update, user confirms, `--soul FILE` writes. | Adding domains to an existing profile can stale its identity; the notice surfaces the review step at exactly the moment it's relevant. A user-customised soul gains the notice too (its identity may also need the new domain). Cost: a print in `role_bind`; the manager skill documents the flow. |

---

## §2 The replace-vs-append rule

`ensure_soul_sections(soul_path, role, *, profile_name="", identity="")`
(currently `(soul_path, role)`) gains the pristine check:

```
target_content:
  missing                  → write full role SOUL      (or block, S-4)
  == DEFAULT_SOUL_MD       → replace with full role SOUL (or block, S-4)
  legacy template          → replace (as above)
  anything else            → append/replace vault block only
```

Hard carve-outs applied before the content check:

- `profile_name == "default"` → **block-only path always** (S-3).
- Role without a template (`manager`, `combined`, bare contributor
  without domain) → **block-only path always** (S-4). `identity` is
  derived by the caller: setup passes `_soul_identity(roles)` (a pure
  `{creative|dev|researcher}` → template key mapping, empty otherwise);
  `role_bind --system` passes `"system-owner"`; the transfer/unbind
  re-alignment path passes nothing (generic grants carry no identity —
  the anchor-replace path refreshes the block and preserves any existing
  identity prose untouched).

The pristine check is a *content* test applied to the file — or, when an
anchored block is already present, to the **prefix before the anchor**.
That makes re-runs converge: `DEFAULT + block` (engine-written on a
pristine profile) upgrades to the full soul on a later identity-bearing
run; a full soul refreshes only its block; user content is never
touched. `DEFAULT_SOUL_MD`'s exact text is copied as a constant in
`vault_ops.py` (the plugin cannot import `hermes_cli`); a comment marks
it as engine-synced. The legacy templates list mirrors
`default_soul._LEGACY_TEMPLATE_SOULS` (normalized comparison: line
endings unified, BOM stripped, trimmed — same normalization as Hermes).

The existing idempotent block replace keeps working: an anchored block is
replaced in place on re-run, so a full soul that later gets a re-run
only refreshes its `## Vault` section.

## §3 The templates

Live in `souls/<identity>.md` at the repo root (NOT under a preset:
these are profile templates shared across presets — the manager is used
by blank too — and examples/ is vault content only). Structure (the
four-section house style, 2026-08-06 — depth via structure, not length;
each section 2–4 lines):

```
# Identity
<who the agent IS — the persona and its arbiter, 2–4 lines>

# Goal
<outcome + quality bar + success criterion — what "good" looks like>

# Perspective
<the source of judgment — the role's psychology, its form follows the
 role: scars (creative), external judge (dev), duty (researcher),
 stewardship across time (system-owner); NOT a fixed skeleton>

# Style
<3–4 imperative bullets, role-true voice>

<!-- vault-soul: managed by the installer; do not edit -->
## Vault
<the generated contributor block — appended by the engine, not stored>
```

Key discipline (from the research): the identity sections are **voice,
not tool grammar** — no `obsidian_*` names, no paths beyond the role's
own domain, no process walkthroughs. The tool pointers live only in the
anchored `## Vault` block, which is engine-generated and stays the
single managed boundary (`remove_soul_sections` spans anchor → next
level-1 heading or EOF).

The engine composes: `template prose` + `\n\n` + `_soul_block("contributor")`
— the stored template file holds only the prose, so the vault block
cannot drift from the engine. (Engine-side constant templates are
rejected: presets are the single source of truth, and the prose is
user-editable — `examples/` is the edit surface, like the preset
READMEs.)

### Role identities (prose summaries — 2026-08-06 enrichment)

| Template | Identity (who the agent IS — decoupled) | Goal (what good looks like) | Perspective (source of judgment) |
|---|---|---|---|
| `manager` | the vault manager — keeps the vault healthy (structure, health, growth); holds no content; measure is the health of the whole | good management is invisible: when the vault just works, the job is done; connects what no single contributor can — missed links, ambiguous tags | invisible success + cross-contributor sight: the only one who reads across every domain; quiet breaks two ways (machinery rotting, keepers reaching for the pen); hold the ledger, not the pen |
| `system-owner` | steward of the durable record + architect of what the system becomes | records runnable without you, legible enough to design from | stewardship across time: the system outlives you; design what comes next from what is there; the dev builds, you design |
| `creative` | the creative partner — thinks alongside the user, not for them | idea far enough to act on, deep enough to re-read | self-reflection: ideas die overcooked or undercooked; write in motion, against pushback |
| `researcher` | the researcher — gathers, verifies, curates; claims are worth their sources | solid ground: verified enough to build on, honest enough to not mislead | duty: others build on what you write; honest "not yet" over borrowed certainty |
| `dev` | the developer — builds software that works; arbiter is reality | ship working artifacts; record for the next engineer or future you | external judge: the machine runs what you wrote, not what you intended; two hard lessons |

The contributor identities are **personas, not vault roles**: they never
name the vault, a domain folder, or an `obsidian_*` tool (S-1b). The
vault enters only through the anchored block. The manager identity is the
deliberate exception — it is vault-connected by definition (S-1b). No
person names, no hardcoded paths beyond the role's own domain, no tool
names in the prose.

## §4 Applicability map (every install/growth case)

| Case | SOUL result |
|---|---|
| Standard install: new `creative`/`dev`/`researcher` profile | full template soul (pristine → replace) |
| Standard install: new `vault-manager` profile | **full manager soul** (S-4) |
| Standard install: `default` (system owner) | **block only** (S-3) |
| Blank install: new manager profile (`create` answer) | **full manager soul** (S-4) |
| Blank install: manager → `default` / `existing:NAME` | block only (S-4 gate: not a new profile) |
| Blank install: new contributor, no domain yet | contributor block only (S-4) |
| Growth: `bind --new --system` | system-owner template (S-5) |
| Growth: `bind --new --domain X` + `--soul FILE` | phase-2 generation via `--soul` (S-6/S-7) |
| Growth: `bind --new --manager` | full manager soul (S-4) |
| Growth: bind an *existing* profile + domain | vault block only + **review notice** (S-8) — profile already has an identity |
| One-agent setup (all roles on one profile) | combined block only (S-4) |

## §5 The generation step

Trigger: `bind --new --domain X` — a profile born for a domain.

Flow:

1. **LLM step (manager's skill):** draft `# Identity` + `# Style` from
   the domain's purpose, using the shipped templates as the skeleton and
   `reference/soul-md-research.md` as the standard (persona, not tool
   grammar; 2–3 + 4–6 lines; no generic filler). Proposed in chat, user
   confirms.
2. **Mechanical step (CLI):** `bind --new --domain X --soul FILE` reads
   the confirmed prose (`_apply_soul_prose`), writes it ahead of the
   contributor vault block, and `ensure_soul_sections` refreshes the
   block. A `--new` profile is pristine by construction.

The same `--soul FILE` mechanism is the **update path** (S-8): when a
domain is added to an existing profile, the bind prints a review notice,
the manager drafts the updated identity (now covering the new domain),
the user confirms, and `bind --soul FILE` replaces the prose — the
managed block and anything after it survive byte-for-byte.

The questionnaire does not generate (it has enough stages; a domain may
not exist yet at finalize). The manager skill's growth reference gains a
"compose a full SOUL" directive alongside the `--soul` flag.

## §6 Verification

- Pytest: pristine→replace, customized→append, legacy→replace, **default
  carve-out**, manager full soul (own identity, no conventions section),
  manager ignores contributor identities, combined block-only, missing
  file, template presence (all five ship `# Identity` + `# Style` + no
  anchor), `_soul_identity` mapping, `_apply_soul_prose` (replace keeps
  block, pristine write, refusal on customized-unmanaged), domain-add
  review notice.
- E2E probe: standard new profiles assert full souls (incl. the manager);
  `default` asserts block-only; blank manager (created) asserts full
  manager soul.
- Live-vault re-run: `creative`/`dev`/`researcher`/`vault-manager`
  transition to full souls; `default` shows block-only; a user-customized
  section (`## CODING BEST PRACTICES` on the live `default`) survives
  byte-for-byte — proof the append path never touches user content.
- Suite count confirmed via `pytest --collect-only` before quoting.

## §7 Out of scope

- Editing the vault block's wording (unchanged from P5b).
- A combined-role identity template (S-4 — deliberately absent: one
  profile holding every role has no single identity to write).
- Auto-regeneration of a full soul when domains are added: the review
  notice (S-8) surfaces the need, but the rewrite is always a
  manager-drafted, user-confirmed `--soul FILE` — never automatic.
