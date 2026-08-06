# Growth protocol

How the manager grows the vault after installation: new contributors, new
domains, role changes. Every flow splits into **LLM steps**
(suggest fields, draft a SOUL — agent judgment, see `soul-drafting.md`)
and **mechanical steps**
(filesystem + config + manifest writes — `roles.py` subcommands, tested). The
agent guides; the script executes. Never improvise filesystem surgery.

## Capabilities at a glance

| Operation | Does | Reach for it when |
|---|---|---|
| `bind PROFILE [--new]` | attach a contributor (skill, SOUL, env, plugin); `--soul FILE` writes the identity prose you drafted | a profile should join the vault |
| `bind PROFILE --domain NAME [--config FILE]` | create `work/NAME/` + grant the owner | a new domain tree is needed |
| `bind PROFILE --manager` | promote to manager (combined surface if already a contributor) | the vault needs a manager |
| `unbind PROFILE [--domain NAME]` | revoke grants (commented out), remove SOUL block, uninstall skills | a profile or domain leaves |
| `transfer PROFILE --to NEW [--domain NAME]` | hand the manager role or a domain off | the manager or owner changes |
| `list` | show bindings: role, surface, domains | "who is bound, and how?" |

Rule of thumb: **bind grows, unbind shrinks, transfer re-arranges, list
inspects.** Every operation is `--dry-run`-able; `--manager` and `--domain`
are mutually exclusive (managers hold no content grants). Full flows below;
the traps are at the bottom.

## Who may do what

| Action | Who | Grant basis |
|---|---|---|
| `--role bind` | manager | `config`/`meta`/`read` on `**` |
| `--role unbind` / `--role transfer` | manager | `config`/`meta`/`read` on `**` |
| `--role bind --domain` (owner-side trees) | domain owner | `write` on the parent tree |

The manager creates contributors and domains but never authors content.
Role mutations (06-growth-design §4.5): `bind` attaches, `unbind` detaches
(refuses for the manager — transfer instead), `transfer` hands a role or
domain off, `list` inspects.

## Binding a contributor

```bash
python3 scripts/roles.py --vault /path/to/vault --role bind PROFILE [--new]
```

Binds an existing profile (or creates it with `--new`) as a contributor:
skill overlay, SOUL sections, seeded config, plugin enabled, `.env` bindings.
A bare contributor holds **no content grants yet** — domains come next:

```bash
python3 scripts/roles.py --vault /path/to/vault \
    --role bind PROFILE --domain DOMAIN [--config /path/to/domain.yaml]
```

Creates `work/DOMAIN/` + `.vault/config.yaml` (from `--config`, or a minimal
stub) when missing, appends the owner's grant block to `roles.yaml`
(`write`/`config`/`meta` on `work/DOMAIN/**` — `meta` is the backstop grant,
P7 — plus `read`, and the shared `work/*/knowledge/**` read). Conventions
live in-tree (spec 07): nothing is seeded or registered in a SOUL. On an
already-scaffolded tree it grants only.

`--domain` takes a path, so a **subdomain** binds too (`--domain
creative/knowledge`): a folder owned by another agent inside a domain. Only
one level deep; a profile that already owns the parent gets a refusal (same
owner ⇒ content — use `obsidian_scaffold`), and an ownership glob another
agent already holds is refused as well — which keeps `work/*/knowledge/**`
the researcher's alone.

### The profile's identity prose — your drafting step

A bind attaches a **block-only soul** by default (the managed `## Vault`
block, no identity). The identity prose is yours to draft — `# Identity`,
`# Goal`, `# Perspective`, `# Style` — per `soul-drafting.md`. Draft,
get the user's confirmation, then write it in the same bind:

```bash
python3 scripts/roles.py --vault /path/to/vault \
    --role bind PROFILE --new --domain DOMAIN --soul /path/to/identity.md
```

`--soul FILE` replaces everything ahead of the anchor with the file's
prose; the `## Vault` block survives byte-for-byte. It refuses a
customized, unmanaged SOUL (no anchor + non-pristine) — an identity the
installer never created is not yours to claim. When a bind prints
`its identity may need review` (a domain added to a profile that already
has a full role SOUL), do the same: draft the update, confirm, `--soul`
writes.

## Binding a manager

```bash
python3 scripts/roles.py --vault /path/to/vault --role bind PROFILE --manager
```

`meta`/`config`/`read` on `**`, manager skill + manager SOUL. A contributor
who becomes the manager gets the **combined** surface (both skills, the
dual-role SOUL block). Managers hold no content grants: `--manager` and
`--domain` are mutually exclusive.

## Unbinding and transferring

```bash
python3 scripts/roles.py --vault /path/to/vault --role unbind PROFILE
python3 scripts/roles.py --vault /path/to/vault --role unbind PROFILE --domain DOMAIN
python3 scripts/roles.py --vault /path/to/vault --role transfer PROFILE --to NEW
python3 scripts/roles.py --vault /path/to/vault --role transfer PROFILE --to NEW --domain DOMAIN
python3 scripts/roles.py --vault /path/to/vault --role list
```

- `unbind` revokes grants (the block is commented out, deny-by-default —
  re-bindable), removes the SOUL `## Vault` block, uninstalls the skill
  overlay, drops the vault env vars. Owned domain trees remain — the notice
  says to remove them manually. **Refuses for the manager** (a vault must
  keep one) — use `transfer`.
- `unbind --domain` unowns just that domain: globs revoked, tree kept.
- `transfer` without `--domain` hands off the **manager role**: the successor
  is re-derived (combined when it already holds content grants), the old
  manager is re-derived from its remaining grants (contributor surface, or
  full unbind when nothing remains).
- `transfer --domain` moves domain ownership A→B in one step (grants; both
  stay contributors).
- `default` is unbound-able (the skill stays reachable as
  `plugin:obsidian-vault`) — the operation warns.

## Renames and relocation

There is no rename verb — a domain rename is `unbind` + `bind`:

```bash
python3 scripts/roles.py --vault /path/to/vault --role unbind PROFILE --domain OLD
python3 scripts/roles.py --vault /path/to/vault --role bind PROFILE --domain NEW
```

The old globs are revoked, the new ones granted; the tree is whatever the
user already renamed it to. Do this right after a rename — until then the
domain is unowned and nobody can write to it.

- **Detecting a rename:** the manager's verify step (grant-anchor check)
  catches the mismatch — a `work/` write-glob whose base no longer exists.
  Raise the issue first, then run the two commands.
- **The vault itself is NOT a growth operation.** Its location is wired into
  every bound profile's `.env` (`OBSIDIAN_VAULT_PATH`); renaming the folder
  disconnects all agents, and the ledger lives inside the vault so nothing
  can see the break. Recovery = re-run the setup questionnaire at the new
  location — not `--role`.
- **Conventions are in-tree (spec 07), so they follow the folder.** The
  root `.vault/conventions.md`, or the scope's own — a rename moves them
  with the tree; nothing re-registers. (The old per-profile
  `conventions/<vault>-conventions.md` + SOUL manifest model is retired.)

## Pitfalls

- **The questionnaire is install-time only** (`scripts/setup.py --setup`,
  relayed by the human — the manager profile does not exist yet while it
  runs). Re-running it after role mutations re-binds per its answers: a
  start-over flow, not a mutation tool — use `--role`.
- **Grants are the truth:** role/skill/SOUL derive from the live
  `roles.yaml` block; the SOUL block is the bind marker. Never hand-edit
  roles.yaml or the SOUL block — use `--role`.
- **Manager invariant:** the vault must always have a manager; `unbind` and
  `transfer` enforce it.
- **Dry-run first:** every subcommand supports `--dry-run` — it prints the
  actions without touching the filesystem.
- **`--vault` is required** with `--role`.
- **roles.yaml is policy with comments:** grants are added and revoked by
  comment-preserving text surgery, never round-tripped (comments would die);
  a revoked block is commented out in place, not deleted.
- **Broken YAML is refused** before any write (`--config` and appended grant
  blocks are re-parsed).
