# obsidian-vault (Hermes plugin) — documentation

Schema-aware, permission-enforced Obsidian vault operations for the
**Hermes Agent**. Filesystem-first: it works headless, with no running
Obsidian required, so maintenance can run from cron.

The engine is **generic**. Vault trees, fields, vocabularies, and agent
grants are all *policy* chosen at setup and stored in the vault's
`.vault/` configs — nothing in the code assumes a specific vault's
layout. TWW's vault is one configuration of the engine, which ships as
the `standard` preset.

## The three layers

Everything in the plugin follows one split — **mechanism in code,
policy in config**:

The plugin is built in three layers: **mechanism** (validation,
grants, derived artifacts — `vault/*.py`), **convention** (bundled
skills + in-tree conventions), and **configuration** (`.vault/*.yaml`
per vault). Full detail:
[concepts/architecture.md](concepts/architecture.md).

The engine hardcodes no tree, folder, field, or agent name — a
portability guard test keeps the split honest
([concepts/architecture.md](concepts/architecture.md)).

## What you get

- **Validated writes** — every mutation flows through one chokepoint:
  path safety → grant check → schema validation → write → audit +
  index regeneration. No path skips a step.
- **Derived artifacts** — INDEX files, the config registry, and the
  wikilink graph are computed from the live vault, never
  hand-maintained. A generated file cannot drift.
- **Permission enforcement** — deny-by-default grants (`read` /
  `write` / `append` / `meta` / `config`) with derived ownership:
  domains, subdomains, and shadowing. Read boundaries apply uniformly
  to search, graph, audit, and context.
- **An issue ledger** — issues are structured records under `.state/`,
  not notes: invisible to search and the graph by construction, seen
  only through the issue tools.
- **A maintenance sweep** — `obsidian_maintain` (delta / maintain /
  optimize) detects decay, distributes findings as ledger issues, and
  promotes observed vocabulary. Installed as cron on the manager
  profile.
- **A growth CLI** — `scripts/roles.py --role bind/unbind/transfer/list`
  grows the vault after install: new profiles, domains, subdomains,
  managers.
- **Inter-agent communication** — profiles ask each other for work via
  native `hermes -p <profile> -z`, with a handoff registry in the
  vault for repeated two-sided flows.
- **Bundled skills** — the installer overlays a contributor skill and a
  manager skill per profile, so agents know how to use the tools.

## Quick start

Paste this into Hermes and let it do the rest:

```
Please help me install the Obsidian-Vault plugin for Hermes from this
repository: https://github.com/TheWhiteWord/Obsidian-Vault
```

The agent relays a short questionnaire (vault location, vault name,
preset, per-role profile assignment) and runs the setup script
deterministically. Full walkthrough: [installation.md](installation.md).

## Documentation map

| Doc | What it holds | Read it when… |
|---|---|---|
| [installation.md](installation.md) | install, setup questionnaire, presets, updating, verification | installing or re-running setup |
| [concepts/model.md](concepts/model.md) | the vault data model: config inheritance, fields, vocabulary lifecycle, derived artifacts, machinery folders | you want to understand how the vault is shaped and validated |
| [concepts/grants.md](concepts/grants.md) | grant kinds, deny-by-default, ownership, shadowing, the standard agent set | you want to understand who may do what, or edit `roles.yaml` |
| [concepts/architecture.md](concepts/architecture.md) | the three layers, engine module map, write pipeline, invariants | you want the whole-system picture or are extending the engine |
| [guides/configuration.md](guides/configuration.md) | the `.vault/config.yaml` DSL: every key, merge semantics, what each statement does | authoring or editing configs |
| [guides/growth.md](guides/growth.md) | the `--role` verb family, domains/subdomains, conventions, SOULs, scaffolding | growing a live vault: new profiles, domains, folders |
| [guides/maintenance.md](guides/maintenance.md) | the issue ledger lifecycle, the sweep, cron, health | running or triaging maintenance |
| [guides/inter-agent.md](guides/inter-agent.md) | peer communication, request/response grammar, the handoff registry | talking to a peer profile or designing a handoff |
| [reference/tools.md](reference/tools.md) | all 18 `obsidian_*` tools: purpose, key parameters, gates | choosing a tool for a task |
| [development.md](development.md) | repo layout, tests, portability guard, engineering rules | extending or debugging the plugin |

## How this relates to the rest of the repo

- **`docs/decisions.md`** is the settled-decisions ledger (D1–D9) —
  the record of *why things are the way they are*; this documentation
  describes *what exists now*. Where a current behavior needs its
  rationale, the docs give one line and the ledger holds the full
  record.
- **`skills/`** holds the agent-facing procedures (the contributor's
  writing loop, the manager's maintenance judgment). Those documents
  tell an agent *how to do its job*; these docs tell a reader *how the
  plugin works*.
- **`README.md`** is the one-page entry point (install + what you get +
  growing). These docs are the full reference.
