---
name: obsidian-vault
description: "Use when operating an Obsidian vault through the obsidian_* tools — context, writes, search, graph, index, audit, scaffold."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [obsidian, vault, notes, frontmatter, grants, knowledge]
---

# Obsidian Vault

## When to use

Load when a task touches a schema-configured Obsidian vault through the
plugin's `obsidian_*` tools: reading/writing notes, searching, graph
navigation, INDEX/registry regeneration, audit, scaffolding structure.
Do **not** load for plain file operations outside a vault.

## The cascade — read this before any vault work

1. **`obsidian_context(folder)`** first — it returns the effective schema,
   vocabulary, tags, sibling notes, your grants for the folder, and a
   `conventions_ref` pointer.
2. **Load the conventions skill the pointer names.** It is the vault's writing
   rules (this skill by default). Verify your note against it before writing.
3. Then use the tools. `obsidian_write`/`obsidian_edit_metadata`/
   `obsidian_delete`/`obsidian_scaffold`/`obsidian_index` enforce grants and
   validation themselves — the conventions check is *your* responsibility.

## Tool routing

| Task | Tool |
|---|---|
| What schema applies here? What can I do in this folder? | `obsidian_context` |
| Create / edit a note | `obsidian_write` |
| Change frontmatter only (never body) | `obsidian_edit_metadata` |
| Remove a note | `obsidian_delete` |
| Create a folder / propose structural change | `obsidian_scaffold` |
| Edit an existing config (domain owner, D-5) | `obsidian_edit_config` |
| Regenerate INDEX.md / registry | `obsidian_index` |
| See the mutation trail | `obsidian_audit` |
| Find notes by term | `obsidian_search` |
| Follow wikilinks (neighbors, hops, dangling) | `obsidian_graph` |
| Discover config options + grant kinds | `obsidian_reference` |
| Raise a ledger issue / list / resolve | `obsidian_issue` · `obsidian_issue_list` · `obsidian_issue_resolve` |
| Run the maintenance sweep (manager) | `obsidian_maintain` |

## Knowledge layout — immutable vs mutable

The installed skill is an **overlay**: the base is a symlink to the plugin
bundle; `conventions/` holds real per-profile state.

- **Bundled (immutable, symlinked)** — SKILL.md, `references/`, `templates/`.
  Same for every vault; never edit them here — edits go to the bundle and
  propagate on the next installer run. A reference you must customise for a
  single profile: break the symlink, copy, edit the copy (copy-on-write).
- **Role directives (immutable, real files)** — `conventions/contributor.md`
  (how a contributor acts — every contributor profile) and
  `conventions/manager.md` (maintenance duties — manager profiles only).
  They are the same for every profile of that role, not maintained per
  profile.
- **Maintained conventions (mutable, real files)** — `conventions/<vault>-conventions.md`,
  one per vault/domain a contributor manages, created from
  `templates/vault-conventions.md` and grown through interaction. Managers
  do not maintain conventions.

## Role routing

The base is shared by every profile; your role decides which convention
files apply.

- **Contributor**: `conventions/contributor.md` (role directive) + the
  `<vault>-conventions.md` files for the domains you manage.
- **Manager**: `conventions/manager.md` only. A manager is **not** a
  contributor — its grants (meta/config/read, no content write) need none of
  the authoring discipline, and it does not maintain conventions.
- **One-profile setup** (a single profile acting as both): both directives
  plus the per-vault convention files.

## References — load what the task needs

- `references/obsidian-formatting.md` — wikilinks, embeds, callouts, tags,
  frontmatter. Load before writing any note.
- `references/tool-protocol.md` — tool surface, grant kinds, refusal
  semantics, scope globs. Load when planning a multi-tool operation.
- `references/config-authoring.md` — the config DSL: how `.vault/config.yaml`
  files inherit and merge, every per-field key (`allowed` vs `allowed_only`,
  `required`, `format`/`multi`), and what each statement does to write,
  search, context, INDEX, and promotion. Load before proposing fields or
  editing a config (`obsidian_scaffold` / `obsidian_edit_config`).
- `references/issues.md` — the ledger lifecycle: raise / list / resolve,
  grant-filtered lists, TTLs. Load when raising or triaging issues
  (role-routed from the SOUL Issues section).
- `references/maintenance.md` — the sweep: `obsidian_maintain` modes
  (delta / maintain / optimize), who runs it, how findings become ledger
  records. Manager-only (role-routed from the SOUL Issues section).
- `references/growth-protocol.md` — how a vault grows and how a fresh
  setup runs (the P5d questionnaire): `--add-contributor` /
  `--add-domain` / `--add-subdomain` (`scripts/setup.py`), LLM-step vs
  mechanical-step split, SOUL manifest maintenance, copy-on-write escape
  hatch. Load when setting up a vault or adding a contributor, domain, or
  subdomain.

Load only what the task calls for; never load all references up front.

## Conventions

Your profile's writing rules live in `conventions/` — real files, not the
symlinked base: `contributor.md` for every profile, plus `manager.md` for
manager profiles. This section of the base stays empty by design; the
per-profile files are where the profile's rules accumulate.

## Verification

- [ ] Called `obsidian_context` for the folder before writing.
- [ ] Loaded the conventions skill named by `conventions_ref`.
- [ ] Note has valid frontmatter per the effective schema (see context).
- [ ] New note is linked from its folder's INDEX (regenerated on write).

## Pitfalls

- Writing without `obsidian_context` first — you don't know the schema or your
  grants; the write may be refused or malformed.
- Editing the installed SKILL.md or a reference — they are symlinks to the
  plugin bundle, so your edit changes the bundle for every profile. Keep
  profile-specific rules in `conventions/`; for a one-off reference
  customisation, break the symlink and copy (copy-on-write).
- Forgetting `conventions_ref` — it is a pointer, not decoration; the vault's
  rules live where it points.
