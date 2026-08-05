---
type: note
kind: [note]
status: active
tags: [vault, orientation]
created: "@today"
description: Vault orientation — layout, roles, and how the issue ledger works.
---
# Starter vault — suggested layout (standard preset)

A copyable example of the plugin's **convention layer** (D1/D3): mechanism is
in the engine, this is one coherent named pattern offered at setup. Copy into
a vault root and adapt — never checked by the engine.

## Tree

```
VAULT/
├── .vault/
│   ├── config.yaml        # root schema + conventions.skill pointer
│   └── roles.yaml         # agents + grants
├── system/                # owned by `default` (system-wide knowledge + records)
│   ├── handbook/
│   ├── logs/
│   └── decisions/
└── work/                  # container of domain vaults
    ├── creative/          # owned by `creative` profile
    │   ├── knowledge/     # shared: `creative` + `researcher`
    │   └── projects/
    └── coding/            # owned by `dev` profile
        ├── knowledge/     # shared: `dev` + `researcher`
        └── projects/
```

Issues do **not** live in the tree: the issue layer is a ledger of structured
records under `.state/issues/` (spec 05), invisible to search/graph/INDEX,
accessed only through `obsidian_issue*` tools.

## Roles (D8/D9)

- `default` — owns `system/**`; the only profile with `.hermes`-wide reach.
  Uses the plugin as one tool among many. Manager conventions appended to its
  skill copy.
- `vault-manager` — maintenance only: `meta`/`config`/`read` everywhere, no
  prose write, no `.hermes` authority.
- Domain contributors (`creative`, `dev`, ...) — own `work/<domain>/**`, read
  `work/*/knowledge/**` (their own + all shared knowledge).
- `researcher` — owns `work/*/knowledge/**`: provides research for every
  domain; knowledge INDEXes are its maintainer's job.

> Glob note: knowledge folders sit two levels under the root
> (`work/<domain>/knowledge/`), so the shared glob is `work/*/knowledge/**` —
> the single-segment `*` (which does not cross separators) plus `**` (which
> does).

## Files

- `.vault/config.yaml` — root schema (five fields, defaults, tags mode,
  validation, `paths.state`, `summary_field`, `conventions.skill`).
- `.vault/roles.yaml` — the full standard agent set, all active: `default`
  (system owner), `vault-manager` (maintenance only), and the domain
  contributors `creative`, `dev`, `researcher` (D8/D9). The vault is built
  for exactly these profiles, so nothing ships commented. Custom installs
  with different profile sets are a future design consideration.
- `.state/issues/` — created on first use: the issue ledger (records, not
  notes; engine machinery, no config to copy).

## Extending

- Add a domain: `obsidian_scaffold work/<name>/` → create the profile → add
  the contributor's grant block to `roles.yaml` (copy the pattern from the
  standard set) → generate `<name>-conventions.md` from the template.
- The full flow is scripted: `scripts/setup.py` (plugin) runs the setup
  questionnaire, composes the per-profile skill, and writes these files.
