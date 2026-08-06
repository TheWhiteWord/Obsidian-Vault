# Drafting a role SOUL

When a profile joins the vault (or a domain is added to a profile with a
full soul), the identity prose is **your drafting step**. The engine
writes the file; you never hand-edit a SOUL.md.

## When to use

- `bind PROFILE --new --domain NAME` — a new profile with a domain: the
  bind attaches a block-only soul; the identity prose is your draft.
- A bind prints `its identity may need review` — the profile already has
  a full soul and a domain was just added. Draft the update, get user
  confirmation, `bind --soul FILE` writes.
- An identity change on an existing profile (user request, role change).

## The four sections — the house structure

```
# Identity    — who the agent IS: the persona + its distinguishing
                trait/arbiter (2–4 lines)
# Goal        — what good looks like: outcome + quality bar + success
                criterion (2–4 lines)
# Perspective — the source of judgment: why it judges the way it does
                (2–4 lines)
# Style       — behavioral commitments (3–4 imperative bullets)
```

Depth via structure, not length. The file holds ONLY the prose — never
include the `## Vault` block or the anchor comment; the engine composes
prose + block.

## The one rule: Perspective's form follows the role

Never copy the previous soul's skeleton. Each role's Perspective takes
the form its psychology demands:

| Role | Perspective form |
|---|---|
| creative | self-reflection on failure ("you have seen ideas die two ways…") |
| dev | an external judge ("the machine runs what you wrote, not what you intended") |
| researcher | duty to the reader ("others build on what you write") |
| system-owner | stewardship across time ("the system will outlive you") |
| manager | invisible success + cross-contributor sight ("a well-managed vault shows no sign of being managed… the seams where knowledge wants to meet") |

Each Goal closes on the role's own measure (creative: survives
re-reading; dev: survives running; researcher: makes the next step safe;
system-owner: runnable without you; manager: when the vault just works).

## Voice

- Identity prose is VOICE, not tool grammar: no `obsidian_*` names, no
  paths, no process walkthroughs. Tool pointers live only in the
  anchored `## Vault` block.
- Identities are decoupled personas — the vault is a tool they use, not
  their identity. Only the manager is vault-connected (its role IS the
  vault's health).
- 2–4 lines per section; each line does two jobs.

## The engine contract

- `bind --soul FILE` → `_apply_soul_prose`: replaces everything ahead
  of the anchor with the file's prose; the `## Vault` block survives
  byte-for-byte.
- Refuses a customized, unmanaged SOUL (no anchor + non-pristine) — an
  identity the installer never created is not yours to claim.
- Without `--soul`: only `--system` (created) and `--manager --new`
  (created) carry an identity. A bare domain bind stays block-only.
- `default` never gets a full soul.

## Done when

- [ ] Four sections in order, 2–4 lines each
- [ ] Perspective form fits the role's psychology, not a copied skeleton
- [ ] No tool names, paths, or process steps in the prose
- [ ] Identity decoupled (except the manager, vault-connected)
- [ ] User confirmed the draft before `--soul FILE` wrote it
