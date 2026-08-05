---
type: note
kind: [note]
status: active
tags: [vault, orientation]
created: "@today"
description: Vault orientation — a bare vault, who does what, and how it grows.
---
# Blank vault (custom installation)

A **bare** vault: the rules exist, the content doesn't yet. There are no
domains — they appear when there is something to organise. This file is for
you: who to ask, and how the vault grows. The agents have their own
instructions; you don't need to know any commands.

## Tree

```
VAULT/
├── .vault/            # machinery: schema + who has access (leave alone)
└── README.md          # this file
```

No `system/`, no `work/` — those are the *standard* preset's shape.
A blank vault starts empty and grows deliberately.

## Who does what — ask the right agent

| You want to… | The role that handles it |
|---|---|
| Create the first domain (and its contributor) | the **manager** |
| Add another domain later | the **manager** |
| Create or edit notes in a domain | that domain's **contributor** |

- **Until the first domain exists, one agent may play every role** — the
  manager is created (or reused) when you're ready to grow.
- **Contributors write only their own domain.** Once a domain exists, its
  contributor owns it: creates and edits notes, adds subfolders.
- **The manager maintains, it doesn't write prose.** It creates domains,
  sweeps for problems, and changes rules, but never edits content.
- **One profile can hold several roles.** A single-agent setup puts
  everything on one profile — ask the same way; the agent knows its own
  grants.

## How the vault stays healthy

Problems are tracked automatically as **issues** — records about the vault,
kept apart from your notes. When something is wrong (a broken link, a stale
index, a note missing a required field), the vault files it, and the agent
that owns the affected folder is the one that fixes it.

- Any agent can report a problem; the owner of the folder resolves it.
- The manager runs a **maintenance sweep** every night (a full check on
  Mondays) that catches problems before you notice them.
- Ask the manager for a health report anytime — what's open, what's being
  fixed, what's been declined.

## Making changes

You almost never touch files or run commands yourself. Tell the right agent
from the table above what you want, and it does the rest.

This file stays in sync with the vault: the manager checks the tree against
the live vault during the maintenance sweep and files an issue if it
drifts; the agent that owns this file applies the update.

Growing the vault is a manager conversation: you name a domain, say who
should own it (an existing profile or a new one), and the manager creates
the domain, the contributor's grants, and the conventions in one step.
