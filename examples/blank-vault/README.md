---
type: note
kind: [note]
status: active
tags: [vault, orientation]
created: "@today"
description: Vault orientation — a bare vault, and how it grows.
---
# Blank vault (custom installation)

A **bare** vault: the root schema and a deny-by-default roles file, with no
domains yet. Domains are added when there is something to organise — by the
manager, through the growth protocol.

## Tree

```
VAULT/
├── .vault/
│   ├── config.yaml        # root schema (five core fields) + conventions.skill
│   └── roles.yaml         # `default` active; manager commented until created
├── README.md              # this file
└── (domains appear as work/<name>/ when the manager adds them)
```

No `system/`, no `work/` — those are the *standard* preset's shape.
A blank vault starts empty and grows deliberately.

## Who does what

- `default` — system owner, reads everything; the only active agent until
  the manager (or a contributor) is created.
- **Manager** — to start using the vault, create a manager profile (or reuse
  one) and give it the maintenance grants: `meta`/`config`/`read` on `**`.
  The custom-install flow walks through this.
- **Contributors** — created per domain, when a domain exists: each owns
  `work/<domain>/**`, reads shared knowledge.

## Growing the vault

- Add a domain (manager): name it, pick an existing profile or create one,
  propose the field delta (e.g. `type.allowed_only: [recipe]` +
  `source`/`retrieved` required), confirm, and the domain + profile + grants
  + SOUL manifest entry are created.
- Add a subdirectory (domain owner): `obsidian_scaffold` inside your own
  tree — no manager round-trip needed.
- Issues are ledger records under `.state/issues/` (spec 05) — invisible to
  search/graph/INDEX, accessed only through `obsidian_issue*` tools.

## Files

- `.vault/config.yaml` — minimal root schema: the five core fields,
  defaults, tags mode, validation, `conventions.skill`.
- `.vault/roles.yaml` — deny-by-default; only `default` active, manager
  block commented until a manager exists.
- `.state/issues/` — created on first use: the issue ledger.

## Extending

The full flow is scripted: `scripts/setup.py` (plugin) runs the setup
questionnaire (standard vs blank), installs the per-profile skill
overlay, and writes these files.
