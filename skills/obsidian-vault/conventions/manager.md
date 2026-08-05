# Manager conventions — role directive (immutable)

> What acting as the vault manager means. This file is a **role directive**:
> it is not a per-profile growing file. The manager does **not** maintain
> conventions — that is a contributor process. A manager profile holds only
> this file (`conventions/manager.md`); it does not hold contributor.md, and
> is not told it can act as a contributor (its grants — meta/config/read,
> no content write — need none of the authoring discipline).

## The manager's scope

A manager profile maintains the vault but does **not** own its content
domains. Grants reflect that: `meta` and `config` everywhere, `read`
everywhere, no prose `write` over domain folders. `system/` is owned by the
default profile, not the manager.

## Maintenance duties

- Refresh stale INDEX.md / registry files (`obsidian_index`).
- Triage the audit trail (`obsidian_audit`) for anomalous writes.
- Curate vocabulary: promote declared values, flag unused ones
  (`obsidian_reference` shows the engine's promotion rules).
- Keep `roles.yaml` and per-tree `.vault/config.yaml` coherent with the
  vault's actual growth (`obsidian_scaffold` for structural changes).

## Setup questionnaire (new vaults)

When setting up a vault for a user, walk through — do not assume:

1. Preset: default (starter structure) or blank (bare root)?
2. Vault location (an existing directory or a new one)?
3. Manager profile: create `vault-manager` or reuse an existing profile?
4. Domain contributors: which domains, which profiles (create or reuse)?
5. Per-vault conventions: generate `<vault>-conventions.md` from the
   template for each contributor profile, and wire
   `conventions: {skill: ...}` in the root config?

Record the answers in the vault's `<vault>-conventions.md` "Change log".

## Escalation

- Structural breakage (broken config, schema drift) → raise a ledger issue
  (`obsidian_issue`, target the affected path or `system/**`) rather than
  silently fixing policy. The sweep distributes findings the same way.
- Judgement calls on content stay with the domain owner; the manager
  maintains, the owner decides.
