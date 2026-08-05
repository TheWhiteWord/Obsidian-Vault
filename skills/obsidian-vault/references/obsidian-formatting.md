# Obsidian formatting — immutable reference

The Obsidian Markdown syntax the vault uses. Load before writing any note.

## Wikilinks

- `[[Note Name]]` — link to a note by name.
- `[[Note Name|display text]]` — alias the link text.
- `[[Note Name#Heading]]` — link to a section.
- `[[Note Name#^blockid]]` — link to a block reference.
- Links are how the graph gets its edges: `obsidian_graph` derives neighbors
  and hops from `[[...]]` in note bodies. Link generously; keep links meaningful.

## Embeds

- `![[Note Name]]` — embed a whole note inline.
- `![[Image.png]]` — embed an image.

## Callouts

```
> [!note] Title
> Body text.
```

Common types: `note`, `tip`, `warning`, `danger`, `question`, `quote`.
Callouts render as colored blocks in Obsidian; keep them for emphasis, not
for ordinary prose.

## Tags

- Frontmatter `tags: [a, b]` is the **authoritative** source; body `#tags`
  are not indexed by the plugin. Put tags in frontmatter.
- Reuse canonical tags from the vault's taxonomy (see `obsidian_context`);
  inventing near-duplicate tags creates drift the manager must clean.

## Frontmatter

YAML block at the top of the note, delimited by `---`:

```yaml
---
type: note
kind: [concept]
status: draft
tags: [topic]
created: 2026-08-03
description: One-line summary shown in INDEX.
---
```

- The **effective schema** (which fields are required, what values are
  allowed) comes from `obsidian_context(folder)` — it is per-folder, via
  `.vault/config.yaml` inheritance. Validate against it, not against a
  remembered default.
- Required fields are **blocking** — a write missing them is refused with
  suggestions. Unknown vocabulary values get a warning or a refusal depending
  on the folder's `validation` mode.

## Linking discipline

- Every new note should be reachable: link it from a related note or its
  folder's INDEX (INDEX is regenerated automatically on write).
- `INDEX.md` files carry a `<!-- generated -->` marker — never hand-edit them.
- Broken `[[links]]` are reported by `obsidian_graph` (dangling) — repair them
  when you create them.
