# Permissions & ownership

Every operation an agent can perform on the vault — reading a note, editing prose,
retagging, reconfiguring a vocabulary — is gated by a grant. Grants live in one
policy file, re-read on every call, so the policy is the live source of truth. This
page covers the grant kinds, how ownership is derived from the policy, and what
lies outside the grant system.

## Grant kinds

There are five grant kinds. Each is a capability, not a role: an agent holds
whichever kinds the policy gives it, over whichever paths the policy lists.

| Kind | What it grants |
| --- | --- |
| `read` | Read notes; contribute to query context |
| `write` | Create, edit, and delete notes and folders |
| `append` | Create only — never edit or delete existing notes |
| `meta` | Edit frontmatter, links, and tags — never body prose |
| `config` | Modify vocabulary sections of `.vault/*.yaml` — never grants or field definitions |

`meta` is safe by construction: the engine splices the frontmatter block and
leaves the body bytes unchanged, so a metadata edit cannot alter prose even by
accident.

`config` is narrower than it sounds: it covers the vocabulary sections of
`.vault/*.yaml` files. The grant alone never authorizes changing grants or
field definitions — structural field changes additionally require explicit
user confirmation (`proposed.user_confirmed: true` on `obsidian_edit_config`
/ `obsidian_scaffold`).

Deny by default: an operation with no matching grant is refused. There is no
warn-and-proceed path — if the policy does not say yes, the answer is no,
deterministically.

## roles.yaml

All grants are declared in one file at the vault root: `.vault/roles.yaml`.
It lists agents, each with grant-kind keys mapping to vault-relative glob
lists:

```yaml
agents:
  default:
    write: ["system/**", "README.md", ".vault/conventions.md"]
    config: ["system/**"]
    read: ["**"]
```

The file is vault policy, not engine mechanism. The engine reads it at call
time and derives everything from it — including ownership — so the file is
the single live source of truth for who can do what.

Never hand-edit it. The growth CLI — `scripts/roles.py --role
bind/unbind/transfer/list`, documented in `guides/growth.md` — is the only
writer, and it enforces the invariants in this document: ownership glob shape,
no overlap between ownership globs, no shadowing.

## Read enforcement is uniform

Read grants filter every read surface identically: `obsidian_search`,
`obsidian_graph`, `obsidian_audit`, `obsidian_context`, and
`obsidian_issue_list`. There is no read path that bypasses the filter.

An agent may query `**` and simply receives nothing from where it cannot read
— no error, no leak. The engine does not announce what it is hiding; it just
does not return it.

Shared reference is expressed by glob, never by global access. An agent that
should see cross-domain knowledge gets an explicit pattern such as
`work/*/knowledge/**`; nobody inherits `**` as a side effect of being trusted
somewhere.

## Ownership

Ownership is derived from the live `roles.yaml`. It is never declared,
stored, or cached anywhere else; the engine computes it on demand from the
ownership globs in the file.

Ownership globs have a canonical shape: one to three literal segments plus an
optional terminal `/**`:

```
system/**
work/<d>/**
work/<d>/<s>/**
```

Only the `bind` verb of the growth CLI produces ownership globs. No other
path — no grant edit, no direct file write — can create one.

The owner of a path is the agent holding the matching ownership glob with the
most segments. Every other write glob (wildcards, deeper paths, anything
outside the canonical shape) is a capability glob: it grants write where it
matches, but it never establishes ownership and never shadows an ownership
glob.

A tie or prefix overlap between ownership globs is refused at bind time.
Ownership of a given territory is always unambiguous.

## Shadowing

`write` and `config` resolve against the derived owner only. Inside an owned
path, the owner's grants are the only ones that count; a capability glob from
anyone else cannot widen what the owner allows.

`read` and `meta` stay generous: any matching grant applies, from any agent.

The consequence inside a subdomain: the domain owner keeps `read` and a `meta`
backstop (link and frontmatter fixes) while the subdomain owner holds `write`
and `config`. Both agents can work in the same folder, but only the subdomain
owner can change its content, and neither is locked out of seeing it.

Principle: grants decide who CAN; conventions and triage routing decide who
SHOULD.

## Three tiers

| Tier | Path | Owner | Parent rights | Notes |
| --- | --- | --- | --- | --- |
| Domain | `work/<d>/` | Profile A | None | Domain-level conventions and config |
| Content | `work/<d>/<f>/` | Same as the domain | — | Rules granularity only; no ownership boundary |
| Subdomain | `work/<d>/<s>/` | Profile B | Read + meta only | A real boundary; subdomain conventions override |

The domain is the largest unit of ownership. Content tiers give a domain owner
finer-grained rule targets — per-folder conventions, per-folder config —
without creating any new ownership boundary. A subdomain is a genuine split:
a second profile owns a piece of the domain outright, and the parent keeps
read and meta only.

A subdomain owner gains read over the parent domain at bind, so it can verify
link targets and see the context around its work. Ownership splits control,
not knowledge.

## The standard preset agent set

The standard preset's `roles.yaml` defines five agents. Grant globs are quoted
exactly as they appear in the file.

**default** — the system owner. Holds `write: [system/**, README.md,
.vault/conventions.md]`, `config: [system/**]`, and `read: [**]`. It owns
the system tree and the vault's own conventions, and it can read everything.

**vault-manager** — maintenance only, structurally incapable of altering
prose. Holds `meta: [**]`, `config: [**]`, `read: [**]`, and no write over
content. It can fix frontmatter, retag, and tune vocabularies anywhere, but no
grant it holds can touch a body of prose.

**creative** and **dev** — domain owners. Each holds `write`, `config`, and
`meta` on its own `work/<domain>/**`, plus `read` on its own domain and on
`work/*/knowledge/**`.

**researcher** — owns the shared knowledge subdomains literally. Holds
`write`, `config`, and `meta` on `work/creative/knowledge/**` and
`work/coding/knowledge/**`, plus `read` on `work/*/knowledge/**` and
`system/**`.

The knowledge-sharing shape falls out of ownership. Each domain's `knowledge/`
folder is a literal subdomain owned by the researcher, so the domain owners
are shadowed from writing there — their `write` does not reach it — but they
keep `read` and `meta`. They can read shared material and fix its links and
frontmatter without being able to change its content.

## What grants do not cover

The `.state/` machinery — the audit log, the issue ledger, and the protocol
registry — is written by the engine with no grant required. No agent grant is
involved, and no agent can be blocked from the engine's own bookkeeping.

Raising an issue requires only a registered identity: any agent present in
`roles.yaml` can raise one, anywhere in the vault. Resolving an issue requires
`write` or `meta` over the issue's target — you can only close what you are
allowed to touch.

Reading the protocol registry is grant-free among registered agents.
