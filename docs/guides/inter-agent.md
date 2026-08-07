# Inter-agent communication

Profiles talk to each other through a **Hermes-native** mechanism: one
profile asks a peer by running `hermes -p <profile> -z "<request>"`
through its terminal tool. The plugin wraps nothing — what it adds is
(1) a **protocol file** the agent loads once to communicate correctly,
and (2) a **handoff registry** in the vault for repeated two-sided
flows.

The canonical protocol file ships with the contributor skill:
`skills/note-taking/obsidian-vault/references/inter-agent-protocol.md`.
It is static — it never lists handoffs; it points at discovery.

## Finding the peer

- Resolve **who** by role/grant, never by profile name: for vault work,
  the profile holding the grant over the target domain (`--role list` /
  `roles.yaml`); otherwise `hermes profile list` / `show` for what
  exists and what each profile is for.
- If the profile that can do the work is the one you run as, do it
  yourself.

## Request grammar

- Say: **task** (what to do), **intent** (why / what you will do with
  the result), **expected response form** (plain prose, or JSON with the
  keys you need).
- One request at a time — no parallel fan-out (matters on a single
  local model).
- Bound exploratory runs with `--max-turns N`.

## Response grammar

- Your final message is the **entire deliverable** — the caller
  receives nothing else (no transcript, no tool log).
- State what you did, what you found, and any paths or keys.
- If the caller asked for JSON, return valid JSON and nothing else.

## Permissions

- A request never grants permissions. Grants (`roles.yaml`) are the
  only authority.
- Never ask a peer to write where you lack grants yourself: route the
  write to the profile that holds the grant, or raise the question.
- The peer's tools enforce its own grants — a denied write is final,
  not a negotiation.

## The handoff registry

Repeated two-sided flows live as **structured records** in the vault:
`.state/protocols/<slug>.yaml`. Records are engine machinery (in
`SKIP_DIRS` — invisible to search, the graph, and INDEX by
construction), not `.md` prose: a prose file would inherit an owner,
and inter-domain communication has no single owner.

```yaml
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
  REQUEST SIDE — ...
  RESPONSE SIDE — ...
```

A handoff is a **two-sided contract**: it uses `requester`/`responder`
(not `from`/`to`), and the `instructions` field carries both sides'
prose. The record names actual profiles — correct, because records are
per-vault policy, like `roles.yaml`; the "never name profiles" rule
applies to generic artifacts (skills, templates), not per-vault data.

### Access

| Operation | Gate |
|---|---|
| Read (list / load) | any registered agent — grant-free; handoffs carry protocol, never content |
| Create | caller must be one of the sides (`requester.profiles` or `responder.profiles`) — self-registration |
| Update | caller must be a party of the existing record |

`obsidian_protocol_list` returns the handoffs where you are a party;
`peer=<profile>` narrows to one pair. `obsidian_protocol` loads one
record (read mode) or registers/updates one (pass `confirm: true` to
apply; without it the call validates and returns the would-be record).

### Lifecycle

The registry starts **empty**; an agent registers a handoff when an
interaction with the user grows into a repeated two-sided flow. No
seeding, no curator — each profile manages its own communications.
Growth verbs (`--role unbind/transfer`) never touch the registry: when
a party leaves, the **remaining party** updates the affected handoff.

## Awareness

Communication is a Hermes capability, not a vault one — so awareness is
not gated behind the obsidian-vault skill. The installer writes two
universal things:

- A `## Inter-agent awareness` section in every bound profile's
  SOUL.md: peer discovery (`hermes profile list` covers every profile,
  vault-bound or not; `--role list` adds domains + grants), the memory
  contract (keep the peer/role list current, never erase), the
  transport, and the registry pointer.
- A memory seed in `<profile>/memories/MEMORY.md` ("Peers and roles:
  none available yet — discover with `hermes profile list` / `--role
  list` … keep this note current") — true in every setup, and it
  converges at the first session. It is never pre-populated, because
  profile names are user-customizable and domains grow post-install.
