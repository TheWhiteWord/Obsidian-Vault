---
name: obsidian-vault-management
description: "Use when managing a schema-configured Obsidian vault — maintenance sweep, ledger and audit triage, INDEX/registry, config coherence, user-requested recurring tasks, setup and growth."
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
2. **Verify the vault** — both checks feed the ledger, nothing acts yet:
   - **Sweep:** `obsidian_maintain` (delta / maintain / optimize) — findings
     become ledger issues. `optimize` proposes link/index connections —
     suggestions only, never auto-applied; the affected owner confirms.
   - **README drift check:** compare the orientation doc's Tree section
     against the live vault. Drift → raise a `[maintenance]` issue targeted
     at `README.md`.
   - **Grant-anchor check:** every folder under `work/` must be covered by
     some `write` glob, and every literal `work/…/**` write glob's base must
     still exist. A bare folder (hand-created, no owner) or a glob base that
     no longer exists (renamed domain) is policy breakage — raise a
     `[maintenance]` issue targeted at the affected tree. The same applies
     to `system/**`: a bind always creates the tree, so a missing base is
     a rename symptom, never a standing grant (blank presets ship no
     standing content globs). Wildcard globs (`work/*/knowledge/**`)
     self-adapt — never a finding.
3. **Triage:** `obsidian_issue_list` + `obsidian_audit` — sweep findings,
   README drift, and anomalies, newest first. Route each issue to the
   **owner of the folder it targets**: a finding inside a subdomain
   (`work/*/knowledge/**`) goes to the subdomain's owner first, then to the
   domain contributor if that owner declines.
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
| Load the conventions that govern a folder | `obsidian_conventions` |
| Raise / list / resolve ledger issues | `obsidian_issue` · `obsidian_issue_list` · `obsidian_issue_resolve` |

## Your remit — maintain, don't author

Your grants are `read`, `meta`, `config` — **no content write**. You fix
structure, metadata, and config; you never write prose. Drafting a
profile's identity prose for its SOUL is machinery, not content — it is
the one prose you do write, through the growth flow (`--soul FILE`), per
`soul-drafting.md`.

- **Apply yourself (AUTO):** INDEX/registry regeneration, vocabulary
  promotion, frontmatter coherence.
- **Escalate:** content judgment stays with the owning agent — the subdomain
  owner for findings inside `knowledge/`, else the domain contributor. When a
  finding needs a content decision, raise it as a ledger issue; the owner
  decides.
- **Raise, don't silently fix:** structural breakage (broken config, schema
  drift) becomes a ledger issue — visibility first.
- **Never by hand:** structural changes (new contributors, domains, configs)
  run through the growth subcommands.

## References — load what the task needs

- `references/maintenance.md` — the sweep: modes, what the checks flag, the
  finding lifecycle, the schedule.
- `references/issues.md` — the ledger: triage across the vault, resolve /
  decline, TTLs.
- `references/recurring-tasks.md` — user-requested content cron ("every
  day…"): profile-by-grants, chained jobs for cross-owner workflows,
  first-run verification.
- `references/growth-protocol.md` — the `--role` verb family
  (`bind` / `unbind` / `transfer` / `list`) for post-install growth and
  role changes.
- `references/soul-drafting.md` — drafting the identity prose for a
  role's SOUL (new profiles, domain-add review, identity updates).
- `references/tool-protocol.md` — refusal semantics, enforcement order, scope
  globs.
- `references/config-authoring.md` — the config DSL: merge rules,
  implications, may / must not.

Load only what the task calls for; never load all references up front.

## Verification

- [ ] Ran `obsidian_maintain` before triage (or know why not).
- [ ] Checked the README's Tree section against the live vault — drift raised as an issue.
- [ ] Checked grant anchors (every `work/` folder covered by a write glob; every literal glob base exists) — mismatches raised as issues.
- [ ] Triage covered the ledger and the audit trail.
- [ ] Content judgments escalated as issues, not self-resolved.
- [ ] AUTO actions applied within grants only.

## Pitfalls

- Editing prose — your grants refuse it; raise an issue instead.
- Editing the README body — you have no `write` over it; raise drift as an
  issue for the system owner (`default`) to apply.
- Hand-editing `roles.yaml` or config files — the growth subcommands and
  `obsidian_edit_config` exist.
- Treating a renamed domain as a README-only problem — the grant globs
  break too; recover with `unbind --domain OLD` + `bind --domain NEW` (no
  rename verb — growth-protocol.md).
- A renamed or moved vault folder is unreachable — no tool or check can see
  it (the ledger lives inside it); recovery is the setup questionnaire, not
  `--role`.
- Running the sweep with `dry_run` or `distribute: false` and forgetting the
  findings — they are the triage input.
- Treating suggestions as auto-fixable — they are never auto-applied.
