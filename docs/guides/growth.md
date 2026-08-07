# Growing a live vault

After installation, the vault grows through the `--role` verb family in
`scripts/roles.py`. Every flow splits into **LLM steps** (suggest
fields, draft a SOUL — agent judgment) and **mechanical steps**
(filesystem + config writes — the CLI, tested). The agent guides; the
script executes. Never improvise filesystem surgery.

The interactive reference for these flows is the manager skill's
`growth-protocol.md`; this page documents the surface.

## Capabilities at a glance

| Operation | Does | Reach for it when |
|---|---|---|
| `bind PROFILE [--new]` | attach a contributor (skill, SOUL, env, plugin); `--soul FILE` writes drafted identity prose | a profile should join the vault |
| `bind PROFILE --domain NAME [--config FILE]` | create `work/NAME/` + grant the owner | a new domain tree is needed |
| `bind PROFILE --manager` | promote to manager (combined surface if already a contributor) | the vault needs a manager |
| `unbind PROFILE [--domain NAME]` | revoke grants (commented out), remove the SOUL block, uninstall skills | a profile or domain leaves |
| `transfer PROFILE --to NEW [--domain NAME]` | hand the manager role or a domain off | the manager or owner changes |
| `list` | show bindings: role, surface, domains | "who is bound, and how?" |

Rule of thumb: **bind grows, unbind shrinks, transfer re-arranges,
list inspects.** Every operation supports `--dry-run`; `--manager` and
`--domain` are mutually exclusive (managers hold no content grants).

Syntax:

```bash
python3 scripts/roles.py --vault <path> --role bind PROFILE [--new] [--manager] [--domain PATH] [--system] [--config FILE]
python3 scripts/roles.py --vault <path> --role unbind PROFILE [--domain PATH]
python3 scripts/roles.py --vault <path> --role transfer PROFILE --to SUCCESSOR [--domain PATH]
python3 scripts/roles.py --vault <path> --role list
```

## Binding a contributor

```bash
python3 scripts/roles.py --vault /path/to/vault --role bind PROFILE [--new]
```

Binds an existing profile (or creates it with `--new`) as a
contributor: skill overlay, SOUL sections, seeded config, plugin
enabled, `.env` bindings. A bare contributor holds **no content grants
yet** — domains come next:

```bash
python3 scripts/roles.py --vault /path/to/vault \
    --role bind PROFILE --domain DOMAIN [--config /path/to/domain.yaml]
```

Creates `work/DOMAIN/` + `.vault/config.yaml` (from `--config`, or a
minimal stub) when missing, and appends the owner's grant block to
`roles.yaml` — `write`/`config`/`meta` on `work/DOMAIN/**` plus `read`
on the domain and the shared `work/*/knowledge/**`. On an
already-scaffolded tree it grants only.

`--domain` takes a path, so a **subdomain** binds too
(`--domain creative/knowledge`): a folder owned by another agent inside
a domain, one level deep. Refusals: a profile that already owns the
parent (same owner ⇒ content — use `obsidian_scaffold` instead), and an
ownership glob another agent already holds (which keeps
`work/*/knowledge/**` the researcher's alone).

`--system` binds the reserved system tree: creates `system/` + a config
stub and grants write/config over `system/**` — the standard preset's
`default` block as a growth action.

## Binding a manager

```bash
python3 scripts/roles.py --vault /path/to/vault --role bind PROFILE --manager
```

Grants `meta`/`config`/`read` on `**`, installs the manager skill +
manager SOUL. A contributor who becomes the manager gets the
**combined** surface (both skills, the dual-role SOUL block). Managers
hold no content grants.

## SOULs

A bind attaches a **block-only soul** by default (the managed `## Vault`
block, no identity). Identity prose is drafted per role — `# Identity`,
`# Goal`, `# Perspective`, `# Style` — then written in the same bind:

```bash
python3 scripts/roles.py --vault /path/to/vault \
    --role bind PROFILE --new --domain DOMAIN --soul /path/to/identity.md
```

`--soul FILE` replaces everything ahead of the anchor with the file's
prose; the `## Vault` block survives byte-for-byte. It refuses a
customized, unmanaged SOUL (no anchor + non-pristine) — an identity the
installer never created is not yours to claim.

Five identity templates ship in `souls/`: `manager`, `system-owner`,
`creative`, `researcher`, `dev`. The installer writes a full soul only
on profiles it **creates** for a role (`bind --new`); `default` always
stays block-only, and binding an existing profile adds the block plus a
review notice when the profile already has identity content — draft the
update, confirm with the user, `--soul` writes it.

## Unbinding and transferring

```bash
python3 scripts/roles.py --vault /path/to/vault --role unbind PROFILE
python3 scripts/roles.py --vault /path/to/vault --role unbind PROFILE --domain DOMAIN
python3 scripts/roles.py --vault /path/to/vault --role transfer PROFILE --to NEW
python3 scripts/roles.py --vault /path/to/vault --role transfer PROFILE --to NEW --domain DOMAIN
```

- `unbind` revokes grants (the block is **commented out** in place,
  deny-by-default, re-bindable), removes the SOUL `## Vault` block,
  uninstalls the skill overlay, drops the vault env vars. Owned domain
  trees remain — the notice says to remove them manually. **Refuses for
  the manager** (a vault must keep one) — use `transfer`.
- `unbind --domain` unowns just that domain: globs revoked, tree kept.
- `transfer` without `--domain` hands off the **manager role**: the
  successor is re-derived (combined when it already holds content
  grants), the old manager is re-derived from its remaining grants
  (contributor surface, or full unbind when nothing remains).
- `transfer --domain` moves domain ownership A→B in one step (grants;
  both stay contributors).
- `default` is unbound-able with a warning (the skill stays reachable
  as `plugin:obsidian-vault`).

**Grants are the truth:** role, skill, and SOUL derive from the live
`roles.yaml` block; the SOUL block is the bind marker. `roles.yaml` is
policy with comments — the CLI edits it by comment-preserving text
surgery, never round-tripped (comments would die).

**Inter-agent handoffs are not touched by these verbs.** The protocol
registry (`.state/protocols/`) is parties-owned
([guides/inter-agent.md](inter-agent.md)): growth verbs change grants,
never party contracts. When a profile or domain changes, the
**remaining party** updates any affected handoff — check
`obsidian_protocol_list` after unbind/transfer/rename.

## Renames and relocation

There is no rename verb — a domain rename is `unbind` + `bind`:

```bash
python3 scripts/roles.py --vault /path/to/vault --role unbind PROFILE --domain OLD
python3 scripts/roles.py --vault /path/to/vault --role bind PROFILE --domain NEW
```

The old globs are revoked, the new ones granted; the tree is whatever
the user already renamed it to. Do this right after a rename — until
then the domain is unowned and nobody can write to it.

- **Case is cosmetic.** The engine matches paths case-insensitively: a
  case-only rename (`creative` → `Creative` / `CREATIVE`) needs no
  unbind/bind — grants keep resolving, writes land in the real folder,
  and the tools report the real on-disk casing back.
- **The vault itself is not a growth operation.** Its location is wired
  into every bound profile's `.env` (`OBSIDIAN_VAULT_PATH`); renaming
  the folder disconnects all agents, and the ledger lives inside the
  vault so nothing can see the break. Recovery is re-running the setup
  questionnaire at the new location — not `--role`.
- **Conventions are in-tree**, so they follow the folder: the root
  `.vault/conventions.md`, or the scope's own, moves with the tree;
  nothing re-registers.

## Growing content: folders, conventions

New folders inside a domain follow **propose → confirm → execute** —
never hand-create folders or configs:

1. `obsidian_scaffold(path, intent, proposed, confirm=false)` — propose
   the folder and its field delta. The proposal shows only what the
   folder needs **beyond inheritance**; structural keys (new required
   fields) need user confirmation, vocabulary values do not. Empty
   deltas write no config.
2. The folder is inside the owner's domain from birth — no grant
   change. Only a genuinely separate domain needs new grants
   (`--role bind … --domain`).

Conventions are **scope directives** in the vault:
`.vault/conventions.md` at any depth, nearest file wins on conflict,
absent rules fall back up the chain. Read any agent may (`obsidian_conventions`
returns the resolved chain); write only the **derived owner of the
scope** — the manager never writes conventions (it never writes
prose), and a parent owner over a subdomain's conventions suggests via
issues instead.

## Pitfalls

- **The questionnaire is install-time only** — `scripts/setup.py
  --setup` is relayed by the human (the manager profile does not exist
  yet while it runs). Re-running it after role mutations re-binds per
  its answers: a start-over flow, not a mutation tool — use `--role`.
- **Manager invariant:** the vault must always have a manager; `unbind`
  and `transfer` enforce it.
- **Dry-run first** — every subcommand prints its actions without
  touching the filesystem.
- **`--vault` is required** with `--role`.
- **Broken YAML is refused** before any write (`--config` and appended
  grant blocks are re-parsed).
