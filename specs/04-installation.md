# 04 — First-Time Installation

**Status: DRAFT — working install spec.** Captures the installer procedure
as proven by the clean-slate E2Es (2026-08-03 dev-machine, 2026-08-04
**fresh-machine repo install — both presets**) and the open questions that
must close before it is promoted into the plugin README. It is TWW-local;
nothing here ships in code. The README's agent-install paste-box is the
promotion (2026-08-04): one block, guided install, both presets.

**Related:** `01-vault-v2-model.md` (model), `03-design-decisions.md` (D1–D9),
`TASKS.md` (trajectory; P3.7d = the clean-slate E2E this doc records).

> **Superseded in P5d (2026-08-05):** this doc records the pre-P5d
> one-shot installer (interactive loop). The current flow is the
> deterministic stage-machine questionnaire — see `scripts/setup.py`
> `--setup` and `TASKS.md` P5d. The fresh-machine E2E results in §6
> remain valid evidence for the mechanics they exercised.

---

## 1. What the installer does (one invocation)

Source of truth: `scripts/setup.py` in the plugin bundle. This doc describes
behavior; the script's `--help` and docstring are the flag reference.

```
python3 scripts/setup.py --vault /path/to/vault --manager create
```

Then the interactive loop asks for contributor profiles, one per
`work/<domain>` (e.g. `creative` → profile `creative`, `coding` → profile
`dev`), plus an optional `researcher` profile. Empty input finishes the loop.

In one run the installer:

1. **Creates profiles** via `hermes profile create <name>` (the CLI is the
   single supported path — it wires alias, skill seeding, etc.).
2. **Installs the skill** — composes `SKILL.md` from the plugin bundle
   fragments (`base + contributor`, `+ manager` for the manager profile) into
   each profile's `skills/` dir. Never touches the bundled source.
3. **Appends the SOUL.md directive** ("load the `obsidian-vault` skill
   first…") — idempotent, one occurrence per profile.
4. **Seeds profile configs** from the system `default` config.yaml
   (copy-if-missing; `memory:` presence is the stub discriminator; default
   config carries no identity keys, so verbatim copy is safe).
5. **Enables the plugin per profile**:
   - named profiles: symlink `~/.hermes/profiles/<name>/plugins/obsidian-vault`
     → `~/.hermes/plugins/obsidian-vault` + `hermes --profile <name> plugins
     enable obsidian-vault --no-allow-tool-override`
   - `default`: bare `hermes plugins enable …` (the bundle already lives at
     the HERMES_HOME root; *still needs the enable* — a stripped default has
     no `plugins.enabled` entry).
   - every profile gets `OBSIDIAN_VAULT_PATH` + `OBSIDIAN_VAULT_AGENT` in its
     `.env`.
6. **Scaffolds the vault** from the starter preset (or blank):
   - `.vault/config.yaml` + `.vault/roles.yaml`, per-domain
     `.vault/config.yaml` files (5: system, work/creative, work/coding, both
     knowledge/), issues-channel configs, and `README.md` — all
     **copy-if-missing** (customised policy survives re-runs).
   - tree directories re-ensured every run (mkdir is idempotent).

## 2. Pre-requisites

- Hermes installed; `hermes` on PATH.
- Plugin bundle at `~/.hermes/plugins/obsidian-vault/` (or the profile's
  plugins dir for named profiles).
- Nothing else. No running Obsidian, no TWW paths — the engine is portable
  (D1).

## 3. Install realities (learned the hard way — keep these)

1. **`default` must be enabled, not just env'd.** Before P3.7d,
   `enable_plugin_for_profile` skipped `default` (env-only) — invisible until
   a strip removed `plugins.enabled`. Now: bare `hermes plugins enable`.
2. **Re-run is safe but vocal.** `hermes profile create` exits 1 on existing
   profiles; the installer now surfaces that as a WARNING (was silent
   success). `.vault` configs, README, seeded configs, SOUL directive: all
   preserved on re-run.
3. **README is scaffolded into the vault** (P3.7d) — but the *vault
   orientation* README (`examples/starter-vault/README.md`) is distinct from
   the *plugin install* README (this doc's promotion target). Don't conflate.
4. **Standard installs ship the full agent set active.** The starter
   `roles.yaml` includes all five agents — `default`, `vault-manager`,
   `creative`, `dev`, `researcher` — **granted by default**. The vault is
   built for exactly these profiles, so nothing ships commented. Deny-by-
   default still protects *unlisted* agents (any agent not in roles.yaml
   gets nothing). Custom installs with a different profile set are a future
   design consideration (C1), not the default.

## 4. Verification (what "it works" means)

From the P3.7d clean-slate run, the minimum proof set:

- `hermes profile list` shows default + the created profiles; each named
  profile's `config.yaml` ≈ default size (~9 KB) with `memory:` present.
- `hermes --profile <name> plugins list` shows obsidian-vault **enabled**;
  `readlink ~/.hermes/profiles/<name>/plugins/obsidian-vault` resolves to the
  bundle.
- Each profile `.env` has both `OBSIDIAN_VAULT_*` vars; `default`'s too.
- Vault has `.vault/config.yaml`, `.vault/roles.yaml`, per-domain configs,
  README.
- Functional probe (deny-by-default actually fires — file presence is not
  enough):
  - write as `default` into `system/**` → ok
  - search as `default` finds it; search as an agent **not in roles.yaml**
    → count 0
  - context as an agent **not in roles.yaml** → `grants` row all-false,
    `siblings` empty
  - each standard contributor can write/read its own domain and is refused
    outside it (e.g. `creative` writes `work/creative/**`, denied in
    `work/coding/**`)
- `pytest tests/` in the bundle → 164 green (P3.7e).

## 5. Open considerations (resolve before promoting to README)

- **C1 — custom profile sets (RESOLVED for standard).** Standard installs
  ship the five standard agents all active — the vault is built for exactly
  them, so there is no reason to ship grants commented. A future *custom*
  install (different domains/profile names) will need its own design:
  installer-written grant blocks per profile, or a `--no-contributors`
  escape hatch, or a scaffold-time grant editor. Deferred until a real
  custom install is requested.
- **C2 — `default` vs `blank` preset.** When is blank right? (Currently:
  blank = bare `.vault/` only; used when the user brings their own tree.)
- **C3 — distribution for a non-TWW user.** The bundle + `setup.py` should
  install standalone (D1). What must the README omit to stay generic?
  (TWW paths, D8/D9 ownership choices — those are vault policy, not engine.)
- **C4 — how much D8/D9 to state.** The README is for "any agent"; the
  `default` owns `system/` rule is TWW vault policy, not engine mechanism.
  Keep policy out of the README; point at the vault's `roles.yaml`.

## 6. Fresh-machine E2E (2026-08-04 — repo install, both presets)

Ran the README's agent-install flow against a **fresh HERMES_HOME + vault**
for `default` and `blank` presets (scratch dirs, real installer, real
`hermes` CLI via HERMES_HOME). Two real bugs surfaced, both fixed:

1. **Blank preset: manager created but never granted.** Blank `roles.yaml`
   ships the manager block commented (deny-by-default until a manager
   exists); the installer created the profile but never activated the block
   → a custom-install manager holds zero grants. Fixed: `_ensure_manager_grant`
   un-comments/activates it (no-op on the starter preset, which ships it
   active).
2. **Default profile: plugin enable failed on a fresh machine** —
   "Plugin 'obsidian-vault' is not installed or bundled." The old code
   assumed the bundle already lived at the HERMES_HOME root (true only on a
   dev machine that symlinked it by hand). Fixed: `enable_plugin_for_profile`
   links the bundle into the default profile's root `plugins/` dir, same as
   named profiles — discovery scans `<home>/plugins`.

The probe script (`/tmp/hermes-verify-install-e2e.py` pattern, re-created
per run) verifies: profile creation, skill overlay symlinks, SOUL sections,
.env vars, vault tree + configs, **zero enable WARNINGs**, and a functional
grant probe through the engine (deny-by-default fires; contributors scoped).

## 7. Promote to README when…

- [ ] C1–C4 resolved.
- [ ] Procedure stable across P3.8 (`!pattern` exclusions) and P4
      (vault-manager cron agent) — no installer churn expected.
- [ ] Zero TWW paths in the text; reads as a generic engine install.
- [ ] The README is thin: one `python3 scripts/setup.py` invocation + a
      pointer to the `obsidian-vault` skill for conventions.
