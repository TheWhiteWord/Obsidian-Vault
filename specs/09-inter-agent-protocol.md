# Inter-agent protocol (P9)

**Status:** design — for approval (2026-08-07, Davide); implementation phase.
**Related:** `03-design-decisions.md` (D1 — differentiation lives in the
convention layer; D8/D9 — the grant model this extends), `05-maintenance-design.md`
(§the issues ledger — the registry's structural precedent),
`08-soul-design.md` (the previous phase), `TASKS-inter-agent.md` (this
phase's tracker).
**Trajectory position:** … → role mutation (P6) → nested ownership (P7) →
full role SOULs (P8.1) → **inter-agent protocol (P9)** → coder-plugin (P8) →
MCP (P9 later).

This phase ships the **inter-agent communication layer** for the vault
plugin: how one profile asks another for work. The mechanism is Hermes-native
(`hermes -p <profile> -z "…"` via the terminal tool — the plugin wraps
nothing); what the plugin adds is (1) a **static protocol file** the agent
loads once to communicate correctly, and (2) a **protocol registry** in the
vault where specific two-sided handoffs live as structured records.

The `agent-communication` plugin (separate repo) is **retired** — evaluation
in `DESK/inter-agent-communication/findings.md` (2026-08-07): it wrapped the
native primitive in a registry + templates + regex layer that was fragile,
partially fake, and profile-hostile. Its one real idea — discoverable
protocols — lands here, in the convention + registry layers.

---

## §1 Locked decisions (2026-08-07)

| # | Decision | Rationale / cost |
|---|---|---|
| A-1 | **Mechanism = native spawn, no wrapper.** A profile asks a peer by running `hermes -p <profile> -z "<request>"` through its terminal tool. One-shot; only the final response returns; the call blocks (sequential by construction). | Works on any Hermes install out of the box, zero plugin machinery, sequential on a single local model. Cost: no audit trail beyond the child's transcript and the parent's context. |
| A-2 | **One protocol file, transport integrated.** `references/inter-agent-protocol.md` = grammar + transport for the selected variant. Variants are whole-file templates; setup selects which becomes the file (symlink swap, never edit). | The agent makes ONE load and gets everything it needs to communicate — no second call to a `transport.md`. Whole-file replacement is simpler than editing a shared paragraph. Cost: shared sections duplicated across variants — guarded by a repo test (see A-9). |
| A-3 | **No registry in the skill file.** `inter-agent-protocol.md` is static — it never lists handoffs; it points at discovery. | A registry makes the file mutable; the skill is symlink-shared across profiles, so one edit changes every profile and the agent pays maintenance calls forever. Discovery replaces the index. |
| A-4 | **Handoffs are structured records in the vault registry** — `.state/protocols/<slug>.yaml`, derived on demand, invisible to content search (the issues-ledger model). Not `.md` prose in `.vault/`. | `.md` in `.vault/` inherits an owner (root = system owner, per-scope = scope owner) — a third party in inter-domain communication. Structured records are engine machinery with no owner; schema is machine-filterable while the `instructions` field carries prose. |
| A-5 | **Records use `requester`/`responder`, not `from`/`to`.** A handoff is a two-sided contract — the responder has obligations too (response-side instructions). Party membership drives filtering. | `from`/`to` is message-shaped (one-way); a handoff is a contract. Role-only filtering cannot distinguish pairs within a role (creative and researcher are both contributors); party membership is exact. Cost: records name actual profiles — correct because records are vault-specific policy, like `roles.yaml`; the "never name profiles" rule applies to generic artifacts (skills, templates), not per-vault data. |
| A-6 | **Read: grant-free among registered agents. Practical visibility: party-filtered.** `obsidian_protocol_list` returns handoffs where the caller is requester or responder; `peer=<profile>` narrows to one pair. | Handoffs carry protocol, never content — universal read leaks nothing. "Grants of visibility become a non-issue": relevance filtering replaces access control; agents only see their own handoffs by default. |
| A-7 | **Write: parties only.** Create requires the caller to be one of the sides (self-registration); update requires the caller to be a party. Engine-enforced. | Each profile independently manages its own communications; no curator, no manager, no default in the middle. Cost: a re-negotiation when a party leaves (record update by the remaining party, mirroring roles.yaml ownership changes). |
| A-8 | **Registry starts empty; growth on use.** No seeding of example handoffs. The universal grammar covers a first request; an agent registers a handoff when an interaction with the user becomes a repeated two-sided flow. | No speculative structure. The `research-handoff` template stays in the spec (below) as the worked example and the shape reference. |
| A-9 | **Installer/skill wiring is DEFERRED (2026-08-07, Davide).** This phase ships the engine (registry + tools) and the canonical protocol file content. `install_skills` composition, the transport symlink, the setup transport question, and the SKILL.md pointer lines land later, when the install surface needs them. | The design keeps the seam: whole-file variants under a stable filename, so wiring later is mechanical and touches no protocol content. Cost: bound profiles don't get `references/inter-agent-protocol.md` until then — acceptable, since no install surface ships this phase. |
| A-10 | **Role-specific answer behavior stays in the role skills.** The protocol file carries only universal rules; how the manager answers (facts, never writes) is role behavior and already lives there. | Nothing here duplicates the role skills — the same split that killed the rev-1/2 duplication. |

---

## §2 Scope — what ships this phase

- **`vault/protocols.py`** — the registry engine (schema, slug, list/get/
  register/update, parties-only write gate, audit rows).
- **Two tools** — `obsidian_protocol_list`, `obsidian_protocol`
  (read / register / update), registered in `__init__.py` with schemas in
  `vault/schemas.py`.
- **`bundles/transports/native.md`** — the canonical protocol file content
  (reproduced in §5; becomes the shipped file).
- **Tests** — `tests/test_protocols.py` + entrypoint wiring assertion.
- **Specs** — this file + `TASKS-inter-agent.md`; the DESK drafts stay
  out-of-repo until this phase stabilises, then the spec is the record.

**Deliberately NOT in scope** (see A-9): installer/skill wiring, setup
transport question, kanban variant, registry seeding, skill reference docs
(`references/protocol-registry.md` deferred with the wiring).

---

## §3 Access model

| Operation | Gate |
|---|---|
| Read (list / get) | registered agent identity (present in `roles.yaml`) — grant-free, like `obsidian_conventions` read |
| Create | caller ∈ {requester.profiles, responder.profiles} — self-registration |
| Update | caller ∈ {requester.profiles, responder.profiles} |
| Delete | not in scope this phase — records are append/update only; retirement is a later decision |

All mutations write audit rows (`protocol_register`, `protocol_update`) with
the record's name as target — same provenance pattern as the issues ledger.
No content pollution: the registry lives under the state dir (in `SKIP_DIRS`),
so `iter_notes` / `build_graph` / `generate` / `search` never see it.

---

## §4 Registry record schema

```yaml
# .state/protocols/research-handoff.yaml
name: research-handoff
version: 1
requester:
  profiles: [creative]
  domains: [work/creative/**]
responder:
  profiles: [researcher]
  domains: [work/*/knowledge/**]
request_format: "task + intent + expected response form"
response_format: "findings + sources + summary; final message is the deliverable"
instructions: |
  REQUEST SIDE — when you need external research to ground a conversation:
  1. Find the profile holding the research capability over the relevant domain
     (resolve by role/grant, never by name).
  2. Ask, via the transport in `inter-agent-protocol.md`:
       Research: <topic>. Intent: ground our discussion.
       Return: findings + sources + summary, ~300 words.
  3. Present the result to the user. If the user wants it saved:
  4. Check the target scope's conventions (`obsidian_conventions`) and propose
     a placement path. Ask the user to confirm placement.
  5. Ask the research holder to save (they own the domain grant); the save
     confirms path + conventions applied.
  6. Continue the conversation with the research in context.

  RESPONSE SIDE — when a peer requests research in a domain you hold:
  1. Run the search + extraction (your web tools).
  2. Return findings + sources + summary in the requested shape — your final
     message IS the deliverable.
  3. Do not save unless asked. If asked to save, check placement + conventions
     for the target scope first, write, confirm path + conventions.
```

Engine-fixed fields (mechanism); the values are per-vault policy. Slug derived
from `name` (deterministic, like the issues key). Schema lives in the module
docstring, not a separate doc — the `vault/issues.py` precedent.

---

## §5 The protocol file — native variant (canonical content)

`bundles/transports/native.md` — the whole file that becomes
`references/inter-agent-protocol.md` when the wiring ships (A-9). Shared
(non-transport) sections must stay byte-identical across variants — a repo
test asserts this once a second variant exists.

```markdown
# Inter-agent protocol

How this profile talks to peer profiles. Applies to every profile in every
vault, whatever the roles and domains. Never names a profile or assumes a
preset.

## Finding the peer

- Resolve **who** by role/grant, never by profile name: for vault work, the
  profile holding the grant over the target domain (`--role list` /
  `roles.yaml`); otherwise `hermes profile list` / `show` for what exists and
  what each profile is for.
- If the profile that can do the work is the one you run as, do it yourself.

## Request grammar

- Say: **task** (what to do), **intent** (why / what you will do with the
  result), **expected response form** (plain prose, or JSON with the keys you
  need).
- One request at a time — no parallel fan-out (matters on a single local
  model).
- Bound exploratory runs with `--max-turns N`.

## Response grammar

- Your final message is the entire deliverable — the caller receives nothing
  else (no transcript, no tool log).
- State what you did, what you found, and any paths or keys.
- If the caller asked for JSON, return valid JSON and nothing else.

## Permissions

- A request never grants permissions. Grants (`roles.yaml`) are the only
  authority.
- Never ask a peer to write where you lack grants yourself: route the write to
  the profile that holds the grant, or raise the question.
- The peer's tools enforce its own grants — a denied write is final, not a
  negotiation.

## Transport

How a request travels to a peer profile:

1. Run `hermes -p <profile> -z "<request>"` through the terminal tool.
   One-shot; ONLY the final response comes back.
2. The call blocks: your turn waits until the peer finishes.
3. Bound exploratory runs with `--max-turns N`.

## Handoffs

Specific two-sided flows (request side + response side) live in the vault's
protocol registry — this file never changes as they grow.

- **Where:** `.state/protocols/<slug>.yaml` — structured records, one per
  handoff, derived on demand like the issues ledger. Not content, not `.md`.
- **Query:** `obsidian_protocol_list` returns handoffs where you are a party
  (requester or responder); pass `peer=<profile>` to narrow to the handoffs
  you have with that specific agent; `obsidian_protocol` loads one record.
- **Maintain:** create or extend a handoff when an interaction with the user
  grows into a repeated two-sided flow. Only the parties (requester /
  responder profiles in the record) can create or update it.
```

---

## §6 Tool contracts

### `obsidian_protocol_list`
| Param | Purpose |
|---|---|
| `peer` (optional) | narrow to handoffs where the caller is one side and this profile is the other |
| `agent` / `vault` | standard args |

Returns: list of records — name, requester, responder, request/response
format (NOT the full `instructions`; the agent loads one record when it
needs it).

### `obsidian_protocol`
| Param | Purpose |
|---|---|
| `name` | read mode: load the full record (both sides' instructions) |
| `register` (record dict) | create mode — caller must be one of the sides |
| `update` (record dict) | update mode — caller must be a party; `name` selects the record |
| `confirm` | apply the write (default false = propose/dry-run) |
| `agent` / `vault` | standard args |

---

## §7 Verification (this phase)

1. `pytest tests/ -q` — full suite green (396 + new), count recorded.
2. `tests/test_protocols.py`: schema validation; slug derivation; list
   filtering (caller / peer); **adversarial parties-gate matrix** (non-party
   create refused, non-party update refused, party allowed, unknown agent
   refused); read grant-free; `.state` invisibility (search/graph never see
   records); audit rows written.
3. `tests/test_entrypoint.py` — both tools reach the registry via the real
   loader probe.
4. E2E probe extension (fresh-machine): registry dir exists and is empty;
   `obsidian_protocol_list` returns empty; non-party register refused. The
   protocol-file-presence assertion waits for the installer wiring (A-9).

---

## §8 Growth-verb interaction (Phase 4 check, 2026-08-07)

**Decision: known gap + manual step — no engine coupling.**

`role_unbind` / `role_transfer` / domain rename (`unbind --domain` + `bind
--domain`) mutate grants, SOUL, skills, env — they never touch
`.state/protocols/`. That is deliberate, not an oversight: a growth verb
rewriting party contracts would be a third party in the middle, which A-7
forbids. Handoff records are parties-owned; when a profile or domain
changes, the **remaining party** updates the affected handoff via
`obsidian_protocol` (update mode, parties-only gate). The manager's
growth-protocol reference carries the pointer ("check
`obsidian_protocol_list` after unbind/transfer/rename").

Why no update verb now: the registry starts empty (A-8), so there is nothing
to migrate; the parties-only update path already exists and is the correct
owner. A growth-verb → registry coupling would be speculative machinery for
a registry with no records. Revisit only if records prove sticky in
practice.
