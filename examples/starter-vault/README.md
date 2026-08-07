---
type: note
kind: [note]
status: active
tags: [vault, orientation]
created: "@today"
description: Vault orientation — what's here, who does what, and how to ask for changes.
---
# Starter vault — suggested layout (standard preset)

This vault is organised as a set of **domains** — folders owned by different
agents, each with its own rules. This file is for you: what's here, who to
ask, and how the vault stays healthy. The agents have their own
instructions; you don't need to know any commands.

## Tree

```
VAULT/
├── .vault/            # machinery: schema + who has access (leave alone)
├── system/            # system-wide knowledge and records (handbook, logs, decisions)
└── work/              # the domains
    ├── creative/      # creative work: knowledge/ + projects/
    └── coding/        # coding work: knowledge/ + projects/
```

## Three levels — domains, content, subdomains

The vault works on three levels, and they behave differently:

- **Domains** sit at the vault root (`work/creative/`, `work/coding/`). Each
  has an owner and its own rules.
- **Content folders** live inside a domain (`knowledge/`, `projects/`, or
  anything you add). They are ordinary folders — the vault adapts to them
  automatically.
- **Subdomains** are content folders owned by *another* agent. In the
  starter vault, `work/*/knowledge/` is the researcher's subdomain, not the
  domain contributor's. A folder owned by someone else is a manager
  conversation; a folder whose owner stays the same is content forever.

What you can move yourself, and what goes through the manager:

- **Inside a domain, organise freely.** Create, rename, and move content
  folders whenever you like; indexes and search follow along. If you rename
  one, links pointing at the old name may break — the nightly sweep files
  them, and the domain's contributor fixes them. Your domain's subdomains
  are not yours to reorganise — they belong to another agent.
- **Domains are a manager conversation.** A domain carries its owner and
  access rules under its name, so creating or renaming one re-points those
  with it. Ask the manager; it happens in one step.
- **Never rename the vault folder itself.** Every agent is wired to the
  vault by its exact location — renaming it disconnects them all, and
  nothing inside can repair itself. If the vault must move, tell the
  manager *before* you do; it is re-attached with a fresh setup, and each
  domain's rules start over.

## Who does what — ask the right agent

| You want to… | The role that handles it |
|---|---|
| Create or edit notes and sub-folders in a domain | that domain's **contributor** |
| Write in a domain's `knowledge/` (a subdomain) | the **researcher** |
| Add a new domain, or a new contributor | the **manager** |
| Change vault-wide rules (schema, who has access) | the **manager** |
| Run something on a schedule (e.g. "every morning, collect the latest from site X into my notes") | the **manager** |
| Fix something broken (broken link, stale index) | the **manager**, or the contributor who owns that folder |

- **Contributors write only their own domain** — and their domain's
  subdomains are read-only to them. A note in one domain can't be edited by
  another domain's contributor; a note in `knowledge/` belongs to the
  researcher. Ask the owner.
- **The manager maintains, it doesn't write prose.** It restructures,
  sweeps for problems, and changes rules, but never edits your content.
- **One profile can hold several roles.** A single-agent setup puts
  everything on one profile; a profile can be both manager and
  contributor. Ask the same way — the agent knows its own grants.
- **Reading is wider than writing.** Every agent reads more than it writes;
  shared knowledge is readable across domains.

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
from the table above what you want, and it does the rest — creating
folders, updating indexes, keeping the rules consistent.

**Names are flexible, capitals included.** The vault treats `Creative`,
`creative`, and `CREATIVE` as the same folder — renaming a folder to
change only its capitalisation breaks nothing. Two folders with the same
name in different cases would confuse it; the nightly sweep catches that
and files an issue.

This file stays in sync with the vault: the manager checks the tree against
the live vault during the maintenance sweep and files an issue if it
drifts; the agent that owns this file applies the update.

A *new* domain (a new area of work with its own contributor) is a manager
conversation: name it, say who should own it, and it's created.
