# obsidian-vault (Hermes plugin)

Schema-aware, permission-enforced Obsidian vault operations.
Filesystem-first — works headless, no running Obsidian required.

**Spec:** `/media/theww/AI/TWW/DESK/specs/01-vault-v2-model.md`
**Tasks:** `/media/theww/AI/TWW/DESK/specs/TASKS.md`

## Status

| Phase | State |
|---|---|
| P0 — config loader + `obsidian_context` | ✅ done |
| P1 — write + grant enforcement | next |
| P2 — generated INDEX/registry · P2b scaffold · P3 graph/query · P4 vault manager · P5 MCP | planned |

## Layout

```
__init__.py          plugin entrypoint — register(ctx), tool schemas, dispatch
vault/
├── constants.py     shared constants (field names, skip dirs, defaults)
├── paths.py         vault-root resolution + safe_join traversal guard
├── config.py        .vault/config.yaml loader + inheritance resolver
├── notes.py         frontmatter parsing, wikilinks, vocabulary derivation
└── context.py       obsidian_context payload assembly
tests/               pytest — 29 tests, run before every commit
```

**Rule:** anything used by more than one module goes in `constants.py` or
`paths.py`. The entrypoint holds tool schemas and dispatch only — no logic.

## Design notes

- `Note` mirrors Obsidian's REST `NoteJson` shape (`path`/`content`/
  `frontmatter`/`tags`), so a future MCP adapter (P5) fills the same struct
  with no second data model.
- Frontmatter parsing uses `python-frontmatter`, not a hand-rolled splitter
  (spec principle 6: borrow before building).
- Malformed notes never raise — `Note.error` is set and surfaces as
  `malformed_notes`, so one bad file can't break a vault scan.
- `safe_join` is the single chokepoint for agent-supplied paths. The P1
  permission model is only as strong as that guarantee.

## Dependencies

`python-frontmatter`, `PyYAML` (already present), `pytest` (dev).

## Running tests

```bash
cd ~/.hermes/plugins/obsidian-vault
python -m pytest tests/ -q
```

## Enabling

```bash
hermes plugins enable obsidian-vault
```

Requires `OBSIDIAN_VAULT_PATH` in `$HERMES_HOME/.env`. The tool hides itself
via `check_fn` when the vault root or a dependency is missing.

Tools load at Hermes startup — restart after changes.
