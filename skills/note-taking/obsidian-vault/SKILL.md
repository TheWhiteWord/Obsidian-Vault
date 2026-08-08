---
name: obsidian-vault
description: "Use when operating an Obsidian vault through the obsidian_* tools — context, writes, search, graph, index, audit, scaffold. Contributor skill; managers load obsidian-vault-management."
version: 2.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [obsidian, vault, notes, frontmatter, grants, knowledge]
    related_skills: [obsidian-vault-management]
---

# Obsidian Vault — contributor

## When to use

Load when a task touches a schema-configured Obsidian vault through the
plugin's `obsidian_*` tools as a **contributor**: reading/writing notes,
searching, graph navigation, INDEX/registry regeneration, scaffolding, raising
issues. Do **not** load for plain file operations outside a vault.

## The writing loop

1. **`obsidian_context(folder)`** first — it returns the effective schema,
   vocabulary, tags, defaults, validation mode, sibling notes, and your grants
   for the folder.
2. **`obsidian_conventions(folder)`** — load the conventions registered for
   that folder (in-tree, nearest scope wins) and verify the note against them
   and this skill's writing rules.
3. Then write. `obsidian_write`/`obsidian_edit_metadata`/`obsidian_delete`/
   `obsidian_scaffold`/`obsidian_index` enforce grants and validation
   themselves — the conventions check is *your* responsibility.

## Tool routing

| Task | Tool |
|---|---|
| What schema applies here? What can I do in this folder? | `obsidian_context` |
| Create / edit a note | `obsidian_write` |
| Change frontmatter only (never body) | `obsidian_edit_metadata` |
| Remove a note | `obsidian_delete` |
| Create a folder / propose structural change | `obsidian_scaffold` |
| Edit an existing config (domain owner) | `obsidian_edit_config` |
| Regenerate INDEX.md / registry | `obsidian_index` |
| See the mutation trail | `obsidian_audit` |
| Find notes by term | `obsidian_search` |
| Follow wikilinks (neighbors, hops, dangling) | `obsidian_graph` |
| Discover config options + grant kinds | `obsidian_reference` |
| Load the conventions that govern this folder | `obsidian_conventions` |
| Raise / list / resolve ledger issues | `obsidian_issue` · `obsidian_issue_list` · `obsidian_issue_resolve` |
| Talk to a peer profile / maintain handoffs | `obsidian_protocol_list` · `obsidian_protocol` |

## Knowledge layout — bundled vs maintained

`SKILL.md`, `references/`, and `templates/` are bundled and shared across
profiles — do not modify them; a change propagates to every profile, and only a
direct user instruction overrides this.

Conventions are **in-tree**: the vault's own `.vault/conventions.md`,
optionally per scope, loaded via `obsidian_conventions`.

## Writing rules

**Before writing**

- Call `obsidian_context(folder)` — know the schema, your grants, the tags.
- Load the folder's conventions (`obsidian_conventions(folder)` — see the
  writing loop).

**While writing**

- Frontmatter first, body second; the schema's required fields are
  non-negotiable (details in `references/obsidian-formatting.md`).
- Reuse canonical tags; if you must invent one, note it for canonization.
- Link new notes into the existing graph (INDEX regenerates on write).
- One note, one idea; prefer many small linked notes over one long one.

**After writing**

- Confirm the write result — a refusal carries errors and suggestions; honor
  them rather than forcing `overwrite`.
- If you created links, check `obsidian_graph` dangling output for breakage you
  introduced.

## Maintaining conventions

Conventions live **in the vault, in-tree**: `.vault/conventions.md` at the
root, optionally one per scope (a folder's own `.vault/conventions.md`).
`obsidian_conventions(folder)` walks the chain — nearest file wins — so
writing under a scope loads exactly that scope's rules.

**What conventions are for:** shaping *desired writing behavior on protocols
that already work* — style, structure, tags, format, standing preferences.
Record them so the next session doesn't relearn them.

**What conventions are not for:** patching broken behavior. If something is
misbehaving (a tool not used, a step skipped), that is a defect to fix at its
own level — a plugin bug, a skill gap, a ledger issue — not a convention.
A convention on top of a broken path just documents the workaround.

**Placement — who must see it?** A rule that applies to one domain goes in
that domain's file (`<domain>/.vault/conventions.md`); a rule that applies to
the whole vault goes in the root file. The root file is the *fallback*, not
the default home: prefer the narrowest scope that covers every reader. When a
folder has no scope file of its own, the chain falls back up to the root —
that is what the root file is for.

It grows through interaction:

- **What goes in:** user corrections about *how to write* — style, structure,
  tags, format — and standing preferences.
- **What does not:** vault content decisions (what the vault contains) — those
  live in the vault, not in conventions.
- **Process:** propose → confirm → record. Keep the file tight; it is loaded on
  demand, not every turn.

## Growing your domain

New folders in your domain follow **propose → confirm → execute**: you propose,
the user confirms, the tool and subcommands do the filesystem work — never
hand-create folders or configs.

1. `obsidian_scaffold` — propose the folder and its field delta (patterns in
   `references/config-authoring.md`). The proposal shows what would change;
   structural keys need user confirmation.
2. No registration step — your grant covers `work/<domain>/**`, so the new
   folder is inside your domain from birth, and conventions are already
   covered in-tree (the root file, or the scope's own). Only a genuinely
   separate domain needs new grants — ask the manager (`scripts/roles.py
   --vault <vault> --role bind <you> --domain <name>` to add,
   `scripts/roles.py --vault <vault> --role transfer <you> --to <other>
   --domain <name>` to hand it off). A folder handed to another agent
   becomes a **subdomain** — read-only to you; its owner is the one to ask.
3. When the new folder's rules genuinely diverge from your main conventions,
   give the folder its own `.vault/conventions.md` or express the field
   delta in its config (the scaffold) — a content-layer decision, no
   registration anywhere.

## References — load what the task needs

- `references/obsidian-formatting.md` — wikilinks, embeds, callouts, tags,
  frontmatter. Load before writing any note.
- `references/tool-protocol.md` — tool surface, grant kinds, refusal
  semantics, scope globs. Load when planning a multi-tool operation.
- `references/config-authoring.md` — the config DSL: how `.vault/config.yaml`
  files inherit and merge, every per-field key, and what each statement does to
  write, search, context, INDEX, and promotion. Load before proposing fields or
  editing a config.
- `references/issues.md` — the ledger lifecycle: raise / list / resolve,
  grant-filtered lists, TTLs. Load when raising or triaging issues.
- `references/inter-agent-protocol.md` — how this profile talks to peer
  profiles: request/response grammar, transport, permissions, and the
  handoff registry. Load before asking a peer for vault work (or answering
  one).

Load only what the task calls for; never load all references up front.

## Verification

- [ ] Called `obsidian_context` for the folder before writing.
- [ ] Loaded this folder's conventions (`obsidian_conventions(folder)`) and
      verified the note against them.
- [ ] Note has valid frontmatter per the effective schema (see context).
- [ ] New note is linked from its folder's INDEX (regenerated on write).

## Pitfalls

- Writing without `obsidian_context` first — you don't know the schema or your
  grants; the write may be refused or malformed.
- Editing the installed SKILL.md or a reference — bundled files are shared
  across profiles; a change propagates everywhere. Only a direct user
  instruction overrides this.
- Skipping the maintained conventions for a folder — the rules a user set
  there are exactly the ones that get corrected on review.
