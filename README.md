# obsidian-vault (Hermes plugin)

Schema-aware, permission-enforced Obsidian vault operations for the **Hermes
Agent**. Filesystem-first: works headless, no running Obsidian required.

The engine is generic (D1) — vault trees, fields, vocabularies, and agent
grants are all *policy* in the vault's `.vault/` configs, chosen at setup
time. Nothing here assumes a specific vault's layout.

---

## Install (one sentence for your agent)

Paste this into Hermes (or any agent with a terminal) and let it do the rest:

```
Please help me install the Obsidian-Vault plugin for Hermes from this
repository: https://github.com/TheWhiteWord/Obsidian-Vault
```

The agent relays a short questionnaire (vault location, vault name, preset,
per-role profile assignment) and runs the setup script deterministically —
it never improvises. **Requirements:** Hermes with the `hermes` CLI on
PATH. Python 3.9+. Nothing else — no running Obsidian, no other services.

### Install vs. setup

- **Install** is Hermes-native: `hermes plugins install <git-url>` clones
  the repo into `~/.hermes/plugins/` and auto-installs the runtime
  dependencies declared in `plugin.yaml` (`pip_dependencies`).
- **Setup** is the questionnaire: `scripts/setup.py --setup` run once per
  stage, `--answer <value>` per answer, `--reset` to start over. The script
  owns the sequence, validation, and every filesystem decision; questions
  come back machine-readable (`SETUP:question` JSON) and the agent relays
  them.

### Updating (2026-08-07)

Code updates are Hermes-native: `hermes plugins update` pulls the latest
repo. But the installer also writes per-profile COPIES — SOUL managed
blocks (new sections land there), the peer/role memory seed, skill
overlays, config seeds, plugin enablement — and those are not refreshed
by a code pull. Run the refresh verb after updating to re-apply them:

```bash
python scripts/setup.py --refresh     # idempotent; --dry-run to preview
```

Refresh discovers vault-bound profiles from the live install (`.env`
with `OBSIDIAN_VAULT_PATH`, or a SOUL carrying the vault anchor), reads
each profile's role back from its SOUL block, and re-runs the same
idempotent ensures setup's finalize runs. It never touches grants
(`roles.yaml` is vault policy), never rewrites user identity prose, and
never clobbers a converged memory note. Restart Hermes after refreshing
so the new tools load.

## What you get

| Preset | Vault | Profiles | Use when |
|---|---|---|---|
| `standard` | Starter tree (`system/`, `work/creative/`, `work/coding/` + shared `knowledge/`), five agents granted by default | `default` (system owner), `vault-manager`, one contributor per domain, `researcher` | You want a working vault now |
| `blank` | Bare `.vault/` (five core fields, deny-by-default roles) | `default` + `vault-manager` | You bring your own tree; add domains later |

Every profile gets: the skill overlay (symlinked bundle base), role-aware
SOUL.md sections, a seeded config, the plugin enabled, and
`OBSIDIAN_VAULT_PATH` / `OBSIDIAN_VAULT_AGENT` in its `.env`.

One-agent setups are allowed: assign every role to a single profile (e.g.
`default`) and it gets both skills (combined role) and unioned grants.

## Growing a live vault

**You don't run these yourself** — tell your Hermes agent what you want
(e.g. "add a domain for recipes, owned by a new profile"), and it executes
them for you, typically on the vault-manager profile. The commands below
are the agent's grammar and your reference for what's possible:

```bash
# bind a contributor profile (--new creates it); --domain adds a domain
python3 scripts/roles.py --vault <path> --role bind <NAME> [--new] [--domain <DOMAIN>] [--config <FILE>]
# bind the system-tree owner — creates system/ + the write/config grant
# (the standard preset's `default` block, available as a growth action)
python3 scripts/roles.py --vault <path> --role bind <NAME> --system
# bind a manager (a contributor who becomes the manager gets the combined surface)
python3 scripts/roles.py --vault <path> --role bind <NAME> --manager
# hand the manager role off (the successor is re-derived; the old manager
# keeps any domains it owned)
python3 scripts/roles.py --vault <path> --role transfer <NAME> --to <SUCCESSOR>
# unbind (grants commented out, SOUL block removed; trees stay — remove
# manually if wanted). Refuses for the manager — transfer instead.
python3 scripts/roles.py --vault <path> --role unbind <NAME>
# who is bound, with which role, surface, and domains
python3 scripts/roles.py --vault <path> --role list
```

The interactive reference for these flows:
`skills/note-taking/obsidian-vault-management/references/growth-protocol.md`.
Every subcommand supports `--dry-run`.

## Verifying

- `hermes profile list` — `default` + the created profiles.
- `hermes --profile <name> plugins list` — obsidian-vault **enabled**.
- Each profile's `.env` has `OBSIDIAN_VAULT_PATH` + `OBSIDIAN_VAULT_AGENT`.
- The vault has `.vault/config.yaml` + `.vault/roles.yaml` (+ per-domain
  configs for the standard preset).
- Functional probe — grants actually fire: as `default`, writing into
  `system/**` succeeds; an agent **not in** `roles.yaml` gets nothing
  (search count 0, all-false grants row); each contributor writes its own
  domain and is refused outside it.
- `.venv-test/bin/python -m pytest tests/ -q` in the repo → green.

## Development

```bash
.venv-test/bin/python -m pytest tests/ -q   # the suite (425 tests)
```

Layout: `vault/` engine modules · `scripts/setup.py` setup questionnaire ·
`scripts/roles.py` daily role verbs · `scripts/vault_ops.py` shared core ·
`souls/` identity prose templates (installer data: read at setup, growth
bind, and unbind; the manager template serves both presets — `examples/`
holds vault presets only) · `skills/note-taking/obsidian-vault/` +
`skills/note-taking/obsidian-vault-management/` the bundled skills (base +
references + templates) · `skills/…/references/inter-agent-protocol.md` the
inter-agent protocol reference (ships with the contributor skill; the
installer picks the transport variant at setup when the wiring ships) ·
`examples/` starter/blank presets · `specs/` design history
(model, decisions D1–D9, install, maintenance, growth, TASKS) ·
`reference/` external material.

**Rule:** anything used by more than one module goes in `vault/constants.py`
or `vault/paths.py`. The entrypoint holds tool schemas and dispatch only.

Tools load at Hermes startup — restart after installing or changing the
plugin.
