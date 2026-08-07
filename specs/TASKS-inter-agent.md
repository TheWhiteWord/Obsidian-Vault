# TASKS — inter-agent protocol (P9)

Goal: ship the inter-agent communication layer — the registry engine
(`vault/protocols.py`), two tools, and the canonical protocol file
(`skills/note-taking/obsidian-vault/references/inter-agent-protocol.md`) —
per `specs/09-inter-agent-protocol.md`.

**Scope boundary (2026-08-07, Davide):** installer/skill wiring, setup
transport question, kanban variant, registry seeding, and skill reference
docs are **out of scope** this phase (spec A-9). The design keeps the seam so
they land later without touching protocol content.

## Principles (apply to every file)

1. **Layers, not batches** — engine → content → specs, each green before the
   next, per the repo's layered-commit discipline.
2. **Tool-first** — if a tool exposes it, don't document it; the registry is
   engine machinery, the protocol file points at the tools.
3. **No history** — state current truth. The retired `agent-communication`
   plugin gets its record in the spec, not in shipped files.
4. **Mechanism in code, policy in config** — record field names and the
   registry layout are engine-fixed; profile names and domains are per-vault
   policy, never engine constants.
5. **Test the refusal, not just the happy path** — the parties gate is the
   whole point; the adversarial matrix is the test that matters.

## Phase 0 — decisions (LOCKED 2026-08-07)

- **A-1..A-10** per `specs/09-inter-agent-protocol.md` §1.
- **Registry location:** `.state/protocols/` (state dir, `SKIP_DIRS` by
  construction) — the issues-ledger model, not `.vault/` prose.
- **Write gate:** parties only, engine-enforced; delete is out of scope this
  phase.
- **File name for the canonical protocol:**
  `skills/note-taking/obsidian-vault/references/inter-agent-protocol.md` — a
  plain reference file in the contributor skill (no separate bundle; the
  whole-file variant story and the future `kanban` variant sit in the spec
  §5, decided 2026-08-07 cleanup).

## Phase 1 — engine (vault/protocols.py + tools)

- [x] `vault/constants.py`: `PROTOCOLS_DIRNAME = "protocols"` (under the
      state dir). Verify `.state` already excluded from content walks — assert
      in tests, don't assume.
- [x] `vault/protocols.py`:
  - [x] record schema dataclass/dict contract (name, version, requester,
        responder, request_format, response_format, instructions)
  - [x] slug derivation from name (deterministic, like issues key)
  - [x] `list_protocols(state, agent, peer=None)` — party filter
  - [x] `get_protocol(state, name)` — full record
  - [x] `register_protocol(state, record, agent)` — parties gate
  - [x] `update_protocol(state, name, record, agent)` — parties gate
  - [x] audit rows: `protocol_register`, `protocol_update`
  - [x] module docstring documents the record shape (issues.py precedent)
- [x] `vault/schemas.py`: `OBSIDIAN_PROTOCOL_LIST`, `OBSIDIAN_PROTOCOL`;
      add to `ALL_SCHEMAS`.
- [x] `__init__.py`: register both tools (thin entry points, handlers in
      `vault/protocols.py`).
- [x] `tests/test_protocols.py`:
  - [x] schema validation
  - [x] slug derivation
  - [x] list filtering (caller; caller+peer)
  - [x] **adversarial parties-gate matrix** — non-party create refused,
        non-party update refused, party allowed, unknown agent refused
  - [x] read grant-free for registered agents
  - [x] `.state` invisibility: search/graph/index never see records
  - [x] audit rows written
- [x] `tests/test_entrypoint.py`: both tools wired through the real loader.

**Check:** `pytest tests/ -q` green; count recorded. **425 passed.**

## Phase 2 — content (the protocol file)

- [x] `skills/note-taking/obsidian-vault/references/inter-agent-protocol.md`
      — the canonical content from spec §5 (grammar + transport + handoffs
      pointer); ships as a plain reference in the contributor skill.
- [x] Verify the shared (non-transport) sections match the spec text
      byte-for-byte; the drift guard test is added when a second variant
      exists (noted, not built).

**Check:** file matches spec §5; no profile names, no role names beyond the
abstract "contributor"/"manager" role language already in the plugin's
vocabulary.

## Phase 3 — tracker record

- [x] `TASKS.md` trajectory line: add inter-agent protocol (P9).
- [ ] Commit layers per repo discipline (engine → content → specs), each
      self-contained and bisectable; no `--amend` across layers.
- [ ] Report: suite count, files, folder layout — WHAT the system produced.

## Phase 4 — end-of-phase integration checks (2026-08-07, Davide)

Not implementation — verification passes that the new machinery does not
silently break what exists.

- [x] **Mutations / vault-growth actions vs the protocol.** Verified:
      `role_unbind` / `role_transfer` / domain rename never touch
      `.state/protocols/` — deliberate (a growth verb rewriting party
      contracts would be the third party A-7 forbids). Decision: known gap +
      manual step — the remaining party updates the handoff via
      `obsidian_protocol`; manager's growth-protocol reference carries the
      pointer; recorded in spec-09 §8. No engine coupling (registry starts
      empty, A-8).
- [x] **Existing reference files still true.** Grepped `tool-protocol.md`,
      `issues.md`, `config-authoring.md` (both bundles): no tool count, no
      exhaustive tool list, no grant table the new tools contradict — the
      agent discovers tools via `obsidian_reference` (tool-first rule).
      Zero stale claims. New-tool documentation belongs with the deferred
      wiring (A-9), not a doc patch now. **One addition made:** the manager's
      `growth-protocol.md` gains the handoff-not-touched-by-growth-verbs
      pointer (the runnable manual step).
- [x] **READMEs current.** Repo README: stale suite count fixed (360 → 425),
      layout gains the protocol reference (in the contributor skill, no
      `bundles/` — cleanup decision 2026-08-07).
      `examples/starter-vault/README.md`
      + `examples/blank-vault/README.md` (user-facing): unchanged — the
      inter-agent protocol is invisible to users (they ask the researcher;
      the protocol is how agents talk), so capability routing stays as is.
- [x] **Awareness — SKILL.md + SOUL.md (Davide's question).** Communication
      is a Hermes capability, not a vault one — awareness must not be gated
      behind skill loading. Contributor SKILL.md: reference listed in
      "References — load what the task needs" + tools in the routing table.
      `_soul_block` (role-keyed → both presets): `## Inter-agent awareness`
      now the FIRST top-level managed section (before `## Vault`),
      covering peer discovery (`hermes profile list` = every profile,
      `--role list` = domains), the memory contract, peer requests, and
      the role-aware handoff registry — contributor/combined point at the
      reference; manager carries the essentials inline (no dangling
      pointer). Recorded in spec-09 §9.
- [x] **Universal memory seed (`ensure_peer_memory`).** The installer
      writes the seed ("Peers and roles: none available yet — discover
      with `hermes profile list` / `--role list` …") into
      `<profile>/memories/MEMORY.md` on first bind, in EVERY case
      (setup `_finalize` + growth `role_bind`; copy-if-missing, never
      clobbers a converged note). True in every setup — single-agent,
      multi-agent, blank. No pre-populated list: profile names are
      user-customizable (`existing:NAME`) and domains grow post-install,
      so a hardcoded list would be wrong/stale. `remove_soul_sections`
      updated for the two-section block. Tests: 4 new (seed written /
      copy-if-missing / idempotent / default path) — 429 green.

## Out of scope (explicitly NOT done this phase)

- Installer/skill wiring (`install_skills` composition, transport symlink,
  SKILL.md pointer lines) — spec A-9.
- Setup transport question — waits for a second variant.
- Kanban transport variant — not written until the setup question exists.
- Registry seeding — starts empty; growth on use.
- `references/protocol-registry.md` skill doc — deferred with the wiring.
- Delete/retire verb for records — later decision.
