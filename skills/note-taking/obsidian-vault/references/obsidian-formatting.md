# Obsidian formatting

The Markdown syntax the vault uses.

## Wikilinks

- `[[Note Name]]` — link to a note by name.
- `[[Note Name|display text]]` — alias the link text.
- `[[Note Name#Heading]]` — link to a section.
- `[[Note Name#^blockid]]` — link to a block reference.
- The graph's edges come from `[[...]]` in note bodies (`obsidian_graph`).
  Link generously; keep links meaningful.

## Embeds

- `![[Note Name]]` — embed a whole note inline.
- `![[Image.png]]` — embed an image.

## Callouts

```
> [!note] Title
> Body text.
```

Common types: `note`, `tip`, `warning`, `danger`, `question`, `quote`.
Use callouts for emphasis, not for ordinary prose.

## Tags

- Frontmatter `tags:` is the **authoritative** source; body `#tags` are not
  indexed by the plugin. Put tags in frontmatter.
- Reuse canonical tags from the folder's vocabulary — `obsidian_context` shows
  the tags in use.

## Frontmatter

YAML block at the top of the note, delimited by `---`:

```yaml
---
type: note
kind: [concept]
status: draft
tags: [topic]
created: 2026-08-03
description: One-line summary (shown in INDEX when the folder config names it as the summary field).
---
```

- The **effective schema** — which fields are required, what values are
  allowed — is per-folder and comes from `obsidian_context(folder)`. Validate
  against it, never against a remembered default.
- Required fields are **blocking**: a write missing them is refused with
  suggestions. Unknown vocabulary values are refused or warned per the
  folder's `validation` mode (context shows it).

## INDEX

- Every folder's `INDEX.md` is regenerated on write and carries a
  `<!-- generated -->` marker — never hand-edit it.
- A new note should be reachable: link it from a related note or its folder's
  INDEX.
