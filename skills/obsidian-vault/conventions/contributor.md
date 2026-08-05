# Contributor conventions — role directive (immutable)

> What acting as a contributor means, for every contributor profile. This
> file is a **role directive**: it is the same for all contributors and is
> not a per-profile growing file. **The maintained, growing file is
> `conventions/<vault>-conventions.md`** (see "Maintaining conventions"
> below). If a rule applies to every contributor, it belongs in the bundle,
> not in a profile copy.

## Before writing

1. Call `obsidian_context(folder)` — know the schema, your grants, the tags.
2. Load the conventions skill from `conventions_ref`.
3. Draft the note, then verify frontmatter and links against both.

## While writing

- Frontmatter first, body second; the five required fields are non-negotiable.
- Reuse canonical tags; if you must invent one, note it for canonization.
- Link new notes into the existing graph (INDEX regenerates on write).
- One note, one idea; prefer many small linked notes over one long one.

## After writing

- Confirm the write result — a refusal carries errors and suggestions; honor
  them rather than forcing `overwrite`.
- If you created a link, check `obsidian_graph` dangling output for breakage
  you introduced.

## Maintaining conventions

The **maintained** conventions file is `conventions/<vault>-conventions.md`
— one per vault (or per domain/subdomain when its rules diverge). It is
created from `templates/vault-conventions.md` and grows through interaction:

1. **Create**: copy the template to `conventions/<vault>-conventions.md`
   when a vault (or domain) needs its own rules. The filename embeds the
   vault name (e.g. `conventions/TWW-conventions.md`).
2. **Wire**: the vault's root config already points at the skill
   (`conventions: {skill: ...}`); the per-vault file is the profile-side
   counterpart — mention it in the SOUL Convention manifest.
3. **Maintain**: rules worth keeping (a user correction, a standing
   preference) land in that file — propose and apply on confirmation. Keep
   it tight; it is loaded on demand, not every turn.
4. **Register**: each new convention file is added to the **Convention
   manifest** section of the profile's SOUL.md (one line per file).

Role directives (`contributor.md` / `manager.md`) are not touched by this
process — they describe how the role acts, not what a vault needs.

## Interaction hygiene

- User corrections about *how to write* belong in `<vault>-conventions.md` —
  record them so the next session doesn't relearn them.
- Vault content decisions (what the vault contains) belong in the vault, not
  here.
