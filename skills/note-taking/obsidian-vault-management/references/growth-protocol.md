# Growth protocol

How the manager grows the vault after installation: fresh setups, new
contributors, new domains, role changes. Every flow splits into **LLM steps**
(suggest fields, draft a SOUL — agent judgment) and **mechanical steps**
(filesystem + config + manifest writes — `setup.py` subcommands, tested). The
agent guides; the script executes. Never improvise filesystem surgery.

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
python3 scripts/setup.py --vault /path/to/vault --role bind PROFILE [--new]
```

Binds an existing profile (or creates it with `--new`) as a contributor:
skill overlay, SOUL sections, seeded config, plugin enabled, `.env` bindings.
A bare contributor holds **no content grants yet** — domains come next:

```bash
python3 scripts/setup.py --vault /path/to/vault \
    --role bind PROFILE --domain DOMAIN [--config /path/to/domain.yaml]
```

Creates `work/DOMAIN/` + `.vault/config.yaml` (from `--config`, or a minimal
stub) when missing, appends the owner's grant block to `roles.yaml`
(`write`/`config` on `work/DOMAIN/**`, `read` + the shared
`work/*/knowledge/**`), seeds the owner's maintained conventions file from
the template, and appends the manifest entry to the owner's SOUL. On an
already-scaffolded tree it grants only.

## Binding a manager

```bash
python3 scripts/setup.py --vault /path/to/vault --role bind PROFILE --manager
```

`meta`/`config`/`read` on `**`, manager skill + manager SOUL. A contributor
who becomes the manager gets the **combined** surface (both skills, the
dual-role SOUL block). Managers hold no content grants: `--manager` and
`--domain` are mutually exclusive.

## Unbinding and transferring

```bash
python3 scripts/setup.py --vault /path/to/vault --role unbind PROFILE
python3 scripts/setup.py --vault /path/to/vault --role unbind PROFILE --domain DOMAIN
python3 scripts/setup.py --vault /path/to/vault --role transfer PROFILE --to NEW
python3 scripts/setup.py --vault /path/to/vault --role transfer PROFILE --to NEW --domain DOMAIN
python3 scripts/setup.py --vault /path/to/vault --role list
```

- `unbind` revokes grants (the block is commented out, deny-by-default —
  re-bindable), removes the SOUL `## Vault` block, uninstalls the skill
  overlay, drops the vault env vars. Owned domain trees remain — the notice
  says to remove them manually. **Refuses for the manager** (a vault must
  keep one) — use `transfer`.
- `unbind --domain` unowns just that domain: globs revoked, manifest entry
  removed, tree kept.
- `transfer` without `--domain` hands off the **manager role**: the successor
  is re-derived (combined when it already holds content grants), the old
  manager is re-derived from its remaining grants (contributor surface, or
  full unbind when nothing remains).
- `transfer --domain` moves domain ownership A→B in one step (grants +
  manifest entry; both stay contributors).
- `default` is unbound-able (the skill stays reachable as
  `plugin:obsidian-vault`) — the operation warns.

## Fresh setup (the questionnaire)

The setup flow is a **deterministic stage machine** — the script owns every
decision; the agent only relays:

```bash
python3 scripts/setup.py --setup                    # print the current question
python3 scripts/setup.py --setup --answer <value>   # validate + build the stage
python3 scripts/setup.py --setup --reset            # start over
```

Questions come back machine-readable (`SETUP:question` JSON); relay them
in-chat and feed the user's answer back. An invalid answer loops back with
`SETUP:alert` + the same question.

Stages: **location** → **name** → **preset** (`standard`|`blank`) →
per-role profile assignment → **finalize** (recap + state reset).

- `standard` recreates the five-agent starter (manager, creative, dev,
  researcher + the implicit `default` system owner); `blank` is a bare
  deny-by-default vault.
- Each role accepts `create` (canonical profile name), `default` (map the
  role onto the default profile), or `existing:NAME`.
- **Role accumulation:** several roles on one profile get both skills plus
  unioned grants — one-agent setups are first-class.
- The preset answer scaffolds the vault immediately; profile building
  happens at finalize (accumulation needs all answers first).
- Re-running the questionnaire after role mutations re-binds per its answers
  — it is the "start over" flow, not a mutation tool.

The agent's job is relay-only: no improvising prompts, no filesystem
surgery, no invented stages — the script's question is the question.

## Pitfalls

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
