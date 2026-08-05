# Reference configs — live vault v2 (captured 2026-08-03)

These are the working `.vault` configs from the P3.x build vault, captured
before it was reset to the starter preset. They are the canonical examples of
how each engine option is expressed, and the seed material for the installer's
starter templates.

## Files

| File | What it shows |
|---|---|
| `root-config.yaml` | The root `.vault/config.yaml`: `fields` (required/vocabulary/multi/allowed/format), `defaults`, `tags.mode`, `validation` (blocking vs advisory), `paths.state`, `summary_field`, `vocabulary` promotion |
| `roles.yaml` | Grant language: `read` / `write` / `append` / `meta` / `config` kinds, glob patterns incl. `**` and `*/ISSUES/**`, one agent per role |
| `issues-channel-config.yaml` | Per-tree channel restriction via `allowed_only`: the `issue` kind and its status lifecycle are **not** global — they live only in `*/ISSUES/.vault/config.yaml` (P3.6 fix) |

## Notes

- The ISSUES config is identical across `SYSTEM/ISSUES/` and `CREATIVE/ISSUES/`
  (only the header comment differs); one copy stands for any `*/ISSUES/` channel.
- `roles.yaml` here is the **old** custom setup (`system`/`tww`/`vault_manager`,
  `CREATIVE/**`, `*/KNOWLEDGE/**`). The starter preset (P3.7) replaces it with
  the neutral layout: `default` owns `system/**`, `vault-manager` is
  maintenance-only, domain contributors own `work/<domain>/**` and read
  `*/knowledge/**`, `researcher` owns `work/*/knowledge/**`.
- The engine's grant kinds are universal; which paths each agent holds is
  per-vault policy — this is the file the installer generates from the setup
  questionnaire.
