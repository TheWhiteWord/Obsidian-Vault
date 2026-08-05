# obsidian-vault (Hermes plugin)

Schema-aware, permission-enforced Obsidian vault operations for the **Hermes
Agent**. Filesystem-first: works headless, no running Obsidian required.

The engine is generic (D1) — vault trees, fields, vocabularies, and agent
grants are all *policy* in the vault's `.vault/` configs, chosen at install
time. Nothing here assumes a specific vault's layout.

---

## Install with your agent (recommended)

Copy the block below and paste it into your agent (Hermes, or any agent
that can run a terminal). It starts a guided installation — the agent asks
you the two decision questions, then runs the installer mechanically.

```
Please help me install the Obsidian-Vault plugin for Hermes from this
repository.

1. Read README.md — the "Installation" and "Verifying" sections — and
   specs/04-installation.md for the full procedure.
2. Ask me: standard install (five-agent starter vault) or custom
   (bare blank vault, my own profiles later)?
3. Ask me where the vault should live (a directory path).
4. Run the installer from this repo:
   python3 scripts/setup.py --vault <path> [--preset default|blank]
   and answer its prompts on my behalf (manager profile, then one
   contributor profile per domain for a standard install).
5. Verify the result against the README's "Verifying" checklist and
   report what was created: profiles, skill, SOUL sections, vault tree.
```

**Requirements:** Hermes with the `hermes` CLI on PATH. Python 3.9+.
Nothing else — no running Obsidian, no other services.

---

## What you get

One installer run (the agent runs it for you, or run it yourself):

| Preset | Vault | Profiles | Use when |
|---|---|---|---|
| `default` | Starter tree (`system/`, `work/creative/`, `work/coding/` + shared `knowledge/`), five agents granted by default | `default` (system owner), `vault-manager`, one contributor per domain, `researcher` | You want a working vault now |
| `blank` | Bare `.vault/` (five core fields, deny-by-default roles) | `default` + `vault-manager` only | You bring your own tree; add domains later |

Every profile gets: the skill overlay (symlinked bundle base + real
`conventions/`), role-aware SOUL.md sections, a seeded config, the plugin
enabled, and `OBSIDIAN_VAULT_PATH` / `OBSIDIAN_VAULT_AGENT` in its `.env`.

## Manual install

```bash
git clone <this repo> && cd <this repo>
python3 scripts/setup.py --vault /path/to/vault --preset default --manager create
# answer the prompts: manager profile name, then one contributor per domain
```

Flags: `--preset default|blank` · `--manager create|reuse` (never `create`
twice for the same home) · `--yes` (accept defaults; **skips the
contributor loop**) · `--dry-run` (print, don't touch).

Re-running is safe: vault configs, seeded configs, SOUL sections, and
conventions survive; existing profiles are warned about, not clobbered.

## Growing a live vault

After install, the same script handles growth (manager + domain owner):

```bash
# manager: bind a new contributor profile
python3 scripts/setup.py --vault <path> --add-contributor <NAME>
# manager: create a full domain owned by that profile
python3 scripts/setup.py --vault <path> --add-domain <DOMAIN> --owner <NAME>
# domain owner: register a scaffolded subdomain (after obsidian_scaffold)
python3 scripts/setup.py --vault <path> --add-subdomain work/<domain>/<sub> --owner <NAME>
```

The interactive reference for these flows: `skills/obsidian-vault/references/growth-protocol.md`.

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
- `python3 -m pytest tests/ -q` in the repo → green.

## Development

```bash
python3 -m pytest tests/ -q        # the suite (259 tests)
.venv-test/bin/python -m pytest tests/ -q   # if system python lost pytest
```

Layout: `vault/` engine modules · `scripts/setup.py` installer + growth ·
`skills/obsidian-vault/` the bundled skill (base + references + templates)
· `examples/` starter/blank presets · `specs/` design history (model,
decisions D1–D9, install, maintenance, growth, TASKS) · `reference/`
external material.

**Rule:** anything used by more than one module goes in `vault/constants.py`
or `vault/paths.py`. The entrypoint holds tool schemas and dispatch only.

Tools load at Hermes startup — restart after installing or changing the
plugin.
