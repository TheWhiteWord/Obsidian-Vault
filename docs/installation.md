# Installation & setup

The plugin is installed in two distinct steps: **install** (Hermes
pulls the code into `~/.hermes/plugins/`) and **setup** (a
questionnaire that creates the vault and binds profiles to it). The
setup script is deterministic — the agent relays its questions, it
never improvises.

**Requirements:** Hermes with the `hermes` CLI on PATH, Python 3.9+.
Nothing else — no running Obsidian, no other services.

## Install

Hermes-native:

```
hermes plugins install <git-url>
```

This clones the repo into `~/.hermes/plugins/` and auto-installs the
runtime dependencies declared in `plugin.yaml` (`python-frontmatter`,
`PyYAML`). For this repository:

```
Please help me install the Obsidian-Vault plugin for Hermes from this
repository: https://github.com/TheWhiteWord/Obsidian-Vault
```

The agent then runs the setup questionnaire below and relays it to you.

## Setup — the questionnaire

`scripts/setup.py` is a **deterministic stage machine**. It runs once
per stage:

```bash
python3 scripts/setup.py --setup                    # print the current question
python3 scripts/setup.py --setup --answer <value>   # validate + build the stage
python3 scripts/setup.py --setup --reset            # start over
```

Questions come back machine-readable (`SETUP:question` JSON); invalid
answers loop back with `SETUP:alert`; the finalize stage emits
`SETUP:done`. The script owns the sequence, validation, and every
filesystem decision.

**Stages:**

1. **Location** — absolute path to the *parent* folder where the vault
   will live.
2. **Name** — the vault's folder name; the installer creates
   `<location>/<name>`. Slashes and `.`/`..` are rejected.
3. **Preset** — `standard` or `blank` (see below).
4. **Per-role profile assignment** — for each role, map it to a profile:
   `create` (new), `default`, or `existing:NAME`. Several roles on one
   profile produce the combined surface (both skills, unioned grants) —
   a one-agent setup is allowed.
5. **Finalize** — applies everything and emits `SETUP:done`.

## Presets

| Preset | Vault | Profiles | Use when |
|---|---|---|---|
| `standard` | Starter tree (`system/`, `work/creative/`, `work/coding/` + shared `knowledge/`), five agents granted by default | `default` (system owner), `vault-manager`, one contributor per domain, `researcher` | you want a working vault now |
| `blank` | Bare `.vault/` (five core fields, deny-by-default roles) | `default` + `vault-manager` | you bring your own tree; add domains later |

## What every bound profile gets

- the **skill overlay** — `SKILL.md`, `references/`, `templates/`
  symlinked to the plugin's bundled skill (contributor, manager, or
  both for a combined profile); updates propagate on the next installer
  run;
- **role-aware SOUL.md sections** — the managed `## Vault` block (plus
  the `## Inter-agent awareness` section), written by the installer;
  full identity prose for profiles it creates with a role template
  ([guides/growth.md](guides/growth.md) — SOULs);
- a **seeded config**, the **plugin enabled**, and
  `OBSIDIAN_VAULT_PATH` + `OBSIDIAN_VAULT_AGENT` in the profile's
  `.env`.

The `default` profile lives at the Hermes home root
(`~/.hermes/SOUL.md`, `~/.hermes/skills/`), not under `profiles/` —
but it still needs the explicit plugin enable the questionnaire
performs.

## Updating

Code updates are Hermes-native: `hermes plugins update` pulls the
latest repo. But the installer also writes per-profile **copies** —
SOUL managed blocks, the peer/role memory seed, skill overlays, config
seeds, plugin enablement — and those are not refreshed by a code pull.
After updating, re-apply them:

```bash
python scripts/setup.py --refresh     # idempotent; --dry-run to preview
```

Refresh discovers vault-bound profiles from the live install (`.env`
with `OBSIDIAN_VAULT_PATH`, or a SOUL carrying the vault anchor), reads
each profile's role back from its SOUL block, and re-runs the same
idempotent ensures setup's finalize runs. It never touches grants
(`roles.yaml` is vault policy), never rewrites user identity prose, and
never clobbers a converged memory note.

**Restart Hermes after installing or refreshing** — tools load at
startup.

## Verifying an install

- `hermes profile list` — `default` + the created profiles.
- `hermes --profile <name> plugins list` — obsidian-vault **enabled**.
- Each profile's `.env` has `OBSIDIAN_VAULT_PATH` + `OBSIDIAN_VAULT_AGENT`.
- The vault has `.vault/config.yaml` + `.vault/roles.yaml` (plus
  per-domain configs for the standard preset).
- Functional probe — grants actually fire: as `default`, writing into
  `system/**` succeeds; an agent **not** in `roles.yaml` gets nothing
  (search count 0, all-false grants row); each contributor writes its
  own domain and is refused outside it.
- `.venv-test/bin/python -m pytest tests/ -q` in the repo → green.
