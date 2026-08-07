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
