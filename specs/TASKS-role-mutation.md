# P6 — Role mutation layer (the `--role` verb family)

Status: **implemented, suite + E2E green** (2026-08-05). Design: 06-growth-design §4.5.

## Why

Setup was add-only: the questionnaire binds roles once and growth only ever
*adds*. Install choices were sticky — no post-install way to bind an
existing profile, promote/demote, hand off the manager, or unbind. Davide
flagged this as the custom install feeling incomplete ("once you installed
and made the choices you must stick with them").

## Decisions locked with Davide (2026-08-05)

1. **Single vault per profile** — no multi-vault tool surface; the role
   layer stays vault-explicit so a future multi-vault doesn't need a
   redesign of the mutation layer.
2. **Unbind removes the `## Vault` SOUL block entirely** (a stale block
   lies) — new `remove_soul_sections`.
3. **A manager must always exist** — `unbind`/`transfer` enforce; the
   escape is `transfer`, never a manager-less vault.
4. **`default` is unbound-able** (system owner included) — with a warning;
   the skill stays reachable as `plugin:obsidian-vault`.
5. **Domain unown keeps the tree** — the operation prints a notice to
   remove it manually if wanted; the layer never deletes trees.

## The verb

```
--role bind PROFILE [--new] [--manager] [--domain NAME] [--config FILE]
--role unbind PROFILE [--domain NAME]
--role transfer PROFILE --to SUCCESSOR [--domain NAME]
--role list
```

The old `--add-contributor` / `--add-domain` / `--add-subdomain` / `--owner`
flags are removed (one coherent surface; `bind` absorbs them). The setup
questionnaire (`--setup`) is unchanged — it remains the initial-creation
flow; re-running it after mutations re-binds per its answers ("start over").

## Tasks

1. **Design doc** — 06-growth-design §4.5 (model, grammar, invariants,
   derivation rule). **DONE**
2. **Mutation core in scripts/setup.py** — DONE:
   - `_revoke_globs` (exact-glob revocation; emptied kind lines dropped; an
     emptied block is COMMENTED OUT preserving the original text — the
     blank preset's deny-by-default stub style)
   - `_roles_from_grants` / `_manager_profile` / `_block_span` / `_block_text`
     (grants are the truth; the SOUL block is the bind marker)
   - `remove_soul_sections` (anchored block → next level-1 heading or EOF)
   - `uninstall_skills` (symlink surfaces + this vault's conventions file +
     empty-dir pruning; copy-on-write content preserved)
   - `remove_profile_env`, `remove_manifest_entries`
   - `role_bind` / `role_unbind` / `role_transfer` / `role_list`
   - argparse: `--role` + positional PROFILE + `--to` / `--new` / `--manager`
     / `--domain` / `--config`
3. **Tests** — tests/test_growth.py rewritten: 18 new tests (bind new /
   existing / domain / manager / combined; unbind full / domain / default /
   manager-refusal + combined-manager unown regression; transfer handoff
   (combined + demote) / domain / refusals; list; remove_soul_sections).
   **302 total, green.**
4. **E2E probe** — verify-install-e2e.py: role-mutation section on the blank
   machine (list → bind --new + domain → transfer handoff → unown → unbind
   default), 16 checks. **ALL PASS.**
5. **Docs** — manager bundle growth-protocol.md rewritten to `--role`;
   engineering skill growth section updated; tracker created. **DONE**
6. **Commit prep** — `4d550ba` (mutation) + `553c281` (docs sweep), both on
   `main`, working tree clean. Davide pushes via VS Code.

## Invariants enforced

- Manager always exists (unbind refuses; transfer hands off).
- Managers hold no content grants (`--manager` × `--domain` mutually
  exclusive; domain ops refuse on the manager profile).
- `default` unbound-able with a warning.
- Trees are never deleted by the layer.
- Every write: comment-preserving, idempotent, dry-run-aware, re-parsed as
  YAML before writing.
