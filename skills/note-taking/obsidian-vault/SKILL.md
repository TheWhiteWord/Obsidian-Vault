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
2. **Load the conventions registered for that folder** in your SOUL Convention
   manifest — each entry names the folder it covers — then verify the note
   against them and this skill's writing rules.
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
| Raise / list / resolve ledger issues | `obsidian_issue` · `obsidian_issue_list` · `obsidian_issue_resolve` |

## Knowledge layout — bundled vs maintained

`SKILL.md`, `references/`, and `templates/` are bundled and shared across
profiles — do not modify them; a change propagates to every profile, and only a
direct user instruction overrides this.

`conventions/` holds real per-profile files, yours to grow: the maintained
conventions files described below.

## Writing rules

**Before writing**

- Call `obsidian_context(folder)` — know the schema, your grants, the tags.
- Load the conventions registered for the folder (see the writing loop).

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

The maintained file is `conventions/<vault>-conventions.md` — by default one
per vault, shared by the folders you manage. A folder whose rules genuinely
diverge gets its own file (e.g. `conventions/<folder>-conventions.md`) — a
deliberate decision, taken when the user asks for different rules there. Every
file is registered in your SOUL Convention manifest, with the folder it
covers.

It grows through interaction:

- **What goes in:** user corrections about *how to write* — style, structure,
  tags, format — and standing preferences. Record them so the next session
  doesn't relearn them. The manifest line's description says which domain a
  file covers.
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
   folder is inside your domain from birth. The SOUL manifest entry (added
   by `scripts/roles.py --role bind --domain`) already covers the domain's
   conventions. Only a genuinely separate domain needs new grants — ask the
   manager (`scripts/roles.py --vault <vault> --role bind <you> --domain
   <name>` to add, `scripts/roles.py --vault <vault> --role transfer <you>
   --to <other> --domain <name>` to hand it off).
3. When the new folder's rules genuinely diverge from your main conventions,
   express them in its `.vault/config.yaml` (the scaffold delta) — the
   conventions file and the SOUL manifest stay domain-scoped and
   installer-managed (no manual registration).

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

Load only what the task calls for; never load all references up front.

## Verification

- [ ] Called `obsidian_context` for the folder before writing.
- [ ] Loaded the conventions registered for this folder (SOUL manifest) and
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
