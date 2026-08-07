# TASKS — inter-agent protocol (P9)

Goal: ship the inter-agent communication layer — the registry engine
(`vault/protocols.py`), two tools, and the canonical protocol file
(`bundles/transports/native.md`) — per `specs/09-inter-agent-protocol.md`.

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
- **File name for the canonical protocol:** `bundles/transports/native.md`
  (the whole-file variant; the future `kanban.md` sits beside it).

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

- [x] `bundles/transports/native.md` — the canonical content from spec §5
      (grammar + transport + handoffs pointer).
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

- [ ] **Mutations / vault-growth actions vs the protocol.** Domain rename,
      ownership transfer (`--role transfer`), unbind — do they need to take
      the protocol registry into account now? At minimum: confirm whether
      handoff records (which name profiles/domains) must be updated on
      transfer/rename, and record the decision (update verb now vs a known
      gap + manual step). Spec-09 §4/A-7 already notes re-negotiation on
      party leave — verify the growth verbs don't orphan or mis-scope
      records.
- [ ] **Existing reference files still true.** Grep the shipped skill
      references (`tool-protocol.md`, `issues.md`, `config-authoring.md`) for
      any claim the new tools/registry contradict (tool lists, grant tables,
      refusal semantics). Zero-hit = done; a stale claim is edited.
- [ ] **READMEs current.** Three to check: repo README (technical: tool list,
      suite count, layout), `examples/starter-vault/README.md` +
      `examples/blank-vault/README.md` (user-facing: capability routing —
      protocol tools only if they change what a user can *ask the agent to
      do*, not tool grammar). Update the parts that are now false; leave
      tool-grammar out per the user-facing README rule.

## Out of scope (explicitly NOT done this phase)

- Installer/skill wiring (`install_skills` composition, transport symlink,
  SKILL.md pointer lines) — spec A-9.
- Setup transport question — waits for a second variant.
- Kanban transport variant — not written until the setup question exists.
- Registry seeding — starts empty; growth on use.
- `references/protocol-registry.md` skill doc — deferred with the wiring.
- Delete/retire verb for records — later decision.
