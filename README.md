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

## What you get

| Preset | Vault | Profiles | Use when |
|---|---|---|---|
| `standard` | Starter tree (`system/`, `work/creative/`, `work/coding/` + shared `knowledge/`), five agents granted by default | `default` (system owner), `vault-manager`, one contributor per domain, `researcher` | You want a working vault now |
| `blank` | Bare `.vault/` (five core fields, deny-by-default roles) | `default` + `vault-manager` | You bring your own tree; add domains later |

Every profile gets: the skill overlay (symlinked bundle base; real
`conventions/` on contributor skills), role-aware SOUL.md sections, a seeded
config, the plugin enabled, and `OBSIDIAN_VAULT_PATH` / `OBSIDIAN_VAULT_AGENT`
in its `.env`.

One-agent setups are allowed: assign every role to a single profile (e.g.
`default`) and it gets both skills (combined role) and unioned grants.

## Growing a live vault

After setup, the same script handles growth (manager + domain owner):

```bash
# manager: bind a new contributor profile
python3 scripts/setup.py --vault <path> --add-contributor <NAME>
# manager: create a full domain owned by that profile
python3 scripts/setup.py --vault <path> --add-domain <DOMAIN> --owner <NAME>
# domain owner: register a scaffolded subdomain (after obsidian_scaffold)
python3 scripts/setup.py --vault <path> --add-subdomain work/<domain>/<sub> --owner <NAME>
```

The interactive reference for these flows: `skills/note-taking/obsidian-vault/references/growth-protocol.md`.

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
.venv-test/bin/python -m pytest tests/ -q   # the suite (284 tests)
```

Layout: `vault/` engine modules · `scripts/setup.py` setup questionnaire +
growth · `skills/note-taking/obsidian-vault/` + `skills/note-taking/
obsidian-vault-management/` the bundled skills (base + references +
templates) · `examples/` starter/blank presets · `specs/` design history
(model, decisions D1–D9, install, maintenance, growth, TASKS) ·
`reference/` external material.

**Rule:** anything used by more than one module goes in `vault/constants.py`
or `vault/paths.py`. The entrypoint holds tool schemas and dispatch only.

Tools load at Hermes startup — restart after installing or changing the
plugin.
