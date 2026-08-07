# Architecture

The plugin is a general vault engine: a set of mechanism modules, two
bundled skills that tell agents how to use them, and per-vault
configuration that decides what the vault is. This page maps the whole
system — the layers, the modules, the write path, and the invariants
that hold it together.

## Three layers

| Layer | What it is | Lives where | Imposed? |
|---|---|---|---|
| **Mechanism** | validation, grants, derive-don't-declare, audit trail, scaffolding, maintenance | `vault/*.py` | imposed — invisible, universal |
| **Convention** | how to write, how the manager works, growth flows | bundled skills + in-tree `.vault/conventions.md` | offered |
| **Configuration** | trees, fields, vocabularies, agent grants | `.vault/config.yaml` + `.vault/roles.yaml` per vault | private — yours |

The engine hardcodes no tree, folder, field, or agent name. A
**portability guard** test (`tests/test_portability.py`) runs the whole
engine against a deliberately foreign vault layout (PARA folders,
different field names) and greps the sources for leaked policy names —
so the split cannot regress without the suite failing.

## Engine modules

Every module in `vault/`, with its responsibility:

| Module | Responsibility |
|---|---|
| `config.py` | config loading + inheritance resolution (`resolve_config`, `ResolvedConfig`) |
| `constants.py` | engine-reserved names, `SKIP_DIRS` — mechanism only, no policy names |
| `paths.py` | vault-root resolution, `safe_join` (refuses escapes, case-corrects), state path |
| `grants.py` | grant resolution + enforcement, deny-by-default, the shared glob language |
| `ownership.py` | derived ownership from canonical ownership globs + shadowing |
| `validate.py` | frontmatter validation, blocking vs advisory |
| `write.py` | the mutation pipeline: `write_note`, `edit_metadata`, `delete_note` |
| `audit.py` | append-only JSONL audit ledger |
| `notes.py` | note parsing (via `python-frontmatter`), tag/vocabulary derivation |
| `generate.py` | derived INDEX files + the config registry |
| `graph.py` | the wikilink graph, derived on demand from note bodies |
| `query.py` | deterministic search + read-grant intersection |
| `context.py` | `obsidian_context` — the merged schema, vocabulary, tags, grants for a folder |
| `reference.py` | the engine's self-describing config reference (drives `obsidian_reference`) |
| `scaffold.py` | folder scaffolding + `edit_config` (the config-gated sibling) |
| `conventions.py` | in-tree scope directives (`.vault/conventions.md`, nearest wins) |
| `issues.py` | the issue ledger (structured records under `.state/issues/`) |
| `maintain.py` | the maintenance sweep (delta / maintain / optimize) |
| `protocols.py` | the inter-agent handoff registry (`.state/protocols/`) |
| `schemas.py` | tool schemas — the agent-facing surface, reviewable as a whole |

The library surface is exported through `vault/__init__.py`; the
plugin's tool handlers live in the repo-root `__init__.py`.

## The write pipeline

Every mutation passes through the same order — no path skips a step:

1. **Resolve path** — `paths.safe_join` refuses escapes outside the
   vault and case-corrects to the real on-disk name.
2. **Check grant** — `grants.RoleRegistry` denies by default; the
   caller must hold the operation's grant kind over the path (with
   ownership shadowing applied for `write`/`config`).
3. **Validate** — `validate.validate_frontmatter` checks the resolved
   schema; `blocking` violations refuse the write with the specific
   problems listed, `advisory` ones warn.
4. **Write** — the note (or metadata splice / deletion) lands.
5. **Audit + index** — the mutation is appended to the audit ledger and
   affected INDEX files are regenerated.

`obsidian_edit_metadata` splices only the frontmatter block — body
bytes stay identical, enforced by test, not trust.

## Thin entrypoint

The repo-root `__init__.py` is **wiring only**: resolve arguments,
dispatch, serialise errors. All logic lives in `vault/`.

- `_dispatch` wraps every handler and turns failures into structured
  JSON (`{"ok": false, "error": ..., "message": ...}`) — an agent
  always receives an actionable object, never a stack trace, never a
  silent success.
- `_available()` refuses to load the tools unless the vault root has
  `.vault/config.yaml`, so the tools never light up against an
  unconfigured tree (a v1 vault, or a plain folder).
- `register()` registers the 18 tools (schema + handler + emoji) and
  the two bundled skills as the pre-install fallback and immutable
  upstream. Agent identity resolves from the `agent` argument →
  `$OBSIDIAN_VAULT_AGENT` → `default`.

## Tool families

| Family | Tools |
|---|---|
| Writing | `obsidian_context` · `obsidian_write` · `obsidian_edit_metadata` · `obsidian_delete` |
| Structure | `obsidian_scaffold` · `obsidian_edit_config` · `obsidian_conventions` |
| Derived | `obsidian_index` |
| Read | `obsidian_search` · `obsidian_graph` · `obsidian_audit` · `obsidian_reference` |
| Issues | `obsidian_issue` · `obsidian_issue_resolve` · `obsidian_issue_list` |
| Protocols | `obsidian_protocol_list` · `obsidian_protocol` |
| Maintenance | `obsidian_maintain` |

Full contracts: [reference/tools.md](../reference/tools.md).

## Scripts

Three layers, no duplication:

| Script | Role |
|---|---|
| `scripts/setup.py` | the install questionnaire — a deterministic stage machine (location → name → preset → per-role assignment → finalize); questions come back machine-readable (`SETUP:question` JSON) |
| `scripts/roles.py` | the daily `--role` CLI for growth (bind / unbind / transfer / list) |
| `scripts/vault_ops.py` | the shared mechanical core — both scripts import it, and the tests import it directly |

`setup.py` parses no role flags (a `setup.py --role …` call is an
argparse error, and that boundary is tested); `roles.py` holds no
mechanical logic. The core is never duplicated.

## Bundled skills & souls

- `skills/note-taking/obsidian-vault` — the **contributor** skill
  (writing loop, formatting, tool routing).
- `skills/note-taking/obsidian-vault-management` — the **manager**
  skill (sweep, triage, growth).
- The installer overlays them per profile as symlinked bundles
  (update-propagating); a copy-on-write break of a symlink is the rare,
  deliberate escape hatch for a profile that must customise a
  reference.
- `souls/*.md` — identity prose templates (`manager`, `system-owner`,
  `creative`, `researcher`, `dev`) that the installer writes ahead of
  the managed `## Vault` block in a profile's SOUL.md. Prose-only, so
  the vault block cannot drift from the engine.

## Core invariants

1. **Derive, don't declare** — anything computable from the vault is
   computed (INDEX, registry, graph, tag lists); generated files are
   overwritten without warning.
2. **Mechanism in code, policy in config** — no tree/folder/field/agent
   name in engine code; enforced by the portability guard.
3. **Validate at the door** — enforcement on write, not in a cleanup
   pass; maintenance repairs decay, it does not compensate for missing
   enforcement.
4. **Shared modules, thin entrypoints, tests per phase** — anything
   used by more than one module lives in `constants.py`/`paths.py`; the
   entrypoint holds schemas and dispatch only.
5. **Skill holds procedure, vault holds content** — behavior rules live
   in the role skills, never embedded in tool payloads; conventions
   live in-tree.
6. **No role-split tool registration** — all 18 tools register for
   every profile; differentiation lives in the convention layer, and
   grants are the hard backstop.
