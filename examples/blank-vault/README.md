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

## Three levels — domains, content, subdomains

When the first domain exists, the vault works on three levels:

- **Domains** sit at the vault root (e.g. `work/creative/`). Each has an
  owner and its own rules.
- **Content folders** live inside a domain. They are ordinary folders — the
  vault adapts to them automatically.
- **Subdomains** are content folders that get *their own* owner (handed to
  another agent by the manager). A folder owned by someone else is a
  manager conversation; a folder whose owner stays the same is content
  forever.

Until then, remember: **a folder you create yourself is just a folder.** It
has no owner and no rules, so no agent can write to it. Domains are created
by the manager — you name it and say who should own it, and it appears with
its owner and rules in one step.

Once a domain exists:

- **Inside a domain, organise freely.** Create, rename, and move content
  folders whenever you like; indexes and search follow along. If you rename
  one, links pointing at the old name may break — the nightly sweep files
  them, and the domain's contributor fixes them.
- **Domains are a manager conversation.** A domain carries its owner and
  access rules under its name — creating or renaming one re-points those
  with it.
- **Never rename the vault folder itself.** Every agent is wired to the
  vault by its exact location — renaming it disconnects them all, and
  nothing inside can repair itself. If the vault must move, tell the
  manager *before* you do; it is re-attached with a fresh setup, and each
  domain's rules start over.

## Who does what — ask the right agent

| You want to… | The role that handles it |
|---|---|
| Create the first domain (and its contributor) | the **manager** |
| Add another domain later | the **manager** |
| Run something on a schedule (e.g. "every morning, collect the latest from site X into my notes") | the **manager** |
| Create or edit notes and sub-folders in a domain | that domain's **contributor** |

- **Until the first domain exists, one agent may play every role** — the
  manager is created (or reused) when you're ready to grow.
- **Contributors write only their own domain** — and their domain's
  subdomains are read-only to them. Once a domain exists, its contributor
  owns it: creates and edits notes, adds subfolders — except any subfolder
  the manager gave to another agent.
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
- The manager runs a **maintenance sweep** every night while your agent is
  running (a full check on Mondays) that catches problems before you notice
  them.
- Ask the manager for a health report anytime — what's open, what's being
  fixed, what's been declined.

## Making changes

You almost never touch files or run commands yourself. Tell the right agent
from the table above what you want, and it does the rest.

**Names are flexible, capitals included.** The vault treats `Creative`,
`creative`, and `CREATIVE` as the same folder — renaming a folder to
change only its capitalisation breaks nothing. Two folders with the same
name in different cases would confuse it; the nightly sweep catches that
and files an issue.

This file stays in sync with the vault: the manager checks the tree against
the live vault during the maintenance sweep and files an issue if it
drifts; the agent that owns this file applies the update.

Growing the vault is a manager conversation: you name a domain, say who
should own it (an existing profile or a new one), and the manager creates
the domain, the contributor's grants, and the conventions in one step.
