# Growth protocol

How the manager grows the vault after installation: fresh setups, new
contributors, new domains. Every flow splits into **LLM steps** (suggest
fields, draft a SOUL — agent judgment) and **mechanical steps** (filesystem +
config + manifest writes — `setup.py` subcommands, tested). The agent guides;
the script executes. Never improvise filesystem surgery.

## Who may do what

| Action | Who | Grant basis |
|---|---|---|
| `--add-contributor` | manager | `config`/`meta`/`read` on `**` |
| `--add-domain` | manager | `config`/`meta`/`read` on `**` |
| `--add-subdomain` | domain owner | `write` on the parent tree |

The manager creates contributors and domains but never authors content.

## Adding a contributor

```bash
python3 scripts/setup.py --vault /path/to/vault --add-contributor NAME
```

Creates the profile (if missing) with the skill overlay, SOUL sections,
seeded config, plugin enabled, and `.env` bindings.

## Adding a domain

```bash
python3 scripts/setup.py --vault /path/to/vault \
    --add-domain DOMAIN --owner PROFILE [--config /path/to/domain.yaml]
```

Creates `work/DOMAIN/` + `.vault/config.yaml` (from `--config`, or a minimal
stub), appends the owner's grant block to `roles.yaml` (`write`/`config` on
`work/DOMAIN/**`, `read` + the shared `work/*/knowledge/**`), seeds the
owner's maintained conventions file from the template, and appends the
manifest entry to the owner's SOUL.

Refused when: the vault is not scaffolded, the owner profile does not exist
(`--add-contributor` first), or `--config` is broken YAML. An owner with
existing grants is **extended**, never refused — role accumulation (one
profile, several roles/domains) is first-class. Order matters:
`--add-contributor` before `--add-domain`.

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

The agent's job is relay-only: no improvising prompts, no filesystem
surgery, no invented stages — the script's question is the question.

## Pitfalls

- **Order:** `--add-contributor` before `--add-domain`; scaffold (tool,
  contributor-side) before `--add-subdomain`.
- **Dry-run first:** every subcommand supports `--dry-run` — it prints the
  actions without touching the filesystem.
- **`--vault` is required** with growth subcommands.
- **roles.yaml is policy with comments:** grants are added by
  comment-preserving text surgery, never round-tripped (comments would die).
- **Broken YAML is refused** before any write (`--config` and appended grant
  blocks are re-parsed).
