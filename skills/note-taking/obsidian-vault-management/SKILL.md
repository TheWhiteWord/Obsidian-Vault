---
name: obsidian-vault-management
description: "Use when managing a schema-configured Obsidian vault — maintenance sweep, ledger and audit triage, INDEX/registry, config coherence, setup and growth."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [obsidian, vault, manager, maintenance, grants, config]
    related_skills: [obsidian-vault]
---

# Obsidian Vault — manager

## When to use

Load when a task is vault **management**: running the maintenance sweep,
triaging the issue ledger and the audit trail, regenerating INDEX/registry,
keeping configs coherent, setting up a vault, or growing it (contributors,
domains).

## The management loop

1. **`obsidian_context(folder)`** first — the resolved schema and your grants
   for the folder.
2. **Sweep:** `obsidian_maintain` (delta / maintain / optimize) — findings
   become ledger issues.
3. **Triage:** `obsidian_issue_list` + `obsidian_audit` — anomalies and
   unresolved findings.
4. **Act within your remit:** fix structure and metadata; escalate content
   judgments to the domain owner as ledger issues.

## Tool routing

| Task | Tool |
|---|---|
| What schema/grants apply here? | `obsidian_context` |
| Run the sweep (delta / maintain / optimize) | `obsidian_maintain` |
| Regenerate INDEX.md / registry | `obsidian_index` |
| See the mutation trail | `obsidian_audit` |
| Change frontmatter only (never body) | `obsidian_edit_metadata` |
| Edit an existing config | `obsidian_edit_config` |
| Find notes by term | `obsidian_search` |
| Follow wikilinks (neighbors, hops, dangling) | `obsidian_graph` |
| Discover config options + grant kinds | `obsidian_reference` |
| Raise / list / resolve ledger issues | `obsidian_issue` · `obsidian_issue_list` · `obsidian_issue_resolve` |

## Your remit — maintain, don't author

Your grants are `read`, `meta`, `config` — **no content write**. You fix
structure, metadata, and config; you never write prose.

- **Apply yourself (AUTO):** INDEX/registry regeneration, vocabulary
  promotion, frontmatter coherence.
- **Escalate:** content judgment stays with the domain owner — when a finding
  needs a content decision, raise it as a ledger issue; the owner decides.
- **Raise, don't silently fix:** structural breakage (broken config, schema
  drift) becomes a ledger issue — visibility first.
- **Never by hand:** structural changes (new contributors, domains, configs)
  run through the growth subcommands.

## References — load what the task needs

- `references/maintenance.md` — the sweep: modes, what the checks flag, the
  finding lifecycle, the schedule.
- `references/issues.md` — the ledger: triage across the vault, resolve /
  decline, TTLs.
- `references/growth-protocol.md` — the `--role` verb family
  (`bind` / `unbind` / `transfer` / `list`) for post-install growth and
  role changes.
- `references/tool-protocol.md` — refusal semantics, enforcement order, scope
  globs.
- `references/config-authoring.md` — the config DSL: merge rules,
  implications, may / must not.

Load only what the task calls for; never load all references up front.

## Verification

- [ ] Ran `obsidian_maintain` before triage (or know why not).
- [ ] Triage covered the ledger and the audit trail.
- [ ] Content judgments escalated as issues, not self-resolved.
- [ ] AUTO actions applied within grants only.

## Pitfalls

- Editing prose — your grants refuse it; raise an issue instead.
- Hand-editing `roles.yaml` or config files — the growth subcommands and
  `obsidian_edit_config` exist.
- Running the sweep with `dry_run` or `distribute: false` and forgetting the
  findings — they are the triage input.
- Treating suggestions as auto-fixable — they are never auto-applied.
