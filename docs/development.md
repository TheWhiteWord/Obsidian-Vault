# Development — extending the plugin

This page is for anyone working on the plugin itself: the engine, the
installer, the bundled skills, or the test suite.

## Repo layout

```
├── __init__.py                 # plugin entrypoint — wiring only (dispatch, error shape, register())
├── plugin.yaml                 # Hermes plugin metadata + the 18 provided tools
├── vault/                      # the engine (mechanism) — see concepts/architecture.md
├── scripts/
│   ├── setup.py                # install questionnaire — the deterministic stage machine
│   ├── roles.py                # daily --role CLI (bind/unbind/transfer/list)
│   └── vault_ops.py            # shared mechanical core (imported by both, and by the tests)
├── skills/note-taking/
│   ├── obsidian-vault/         # contributor skill bundle (SKILL.md, references/, templates/)
│   └── obsidian-vault-management/  # manager skill bundle
├── souls/                      # identity prose templates for role SOULs (installer data)
├── examples/
│   ├── starter-vault/          # the standard preset (a real, working vault)
│   └── blank-vault/            # the blank preset (bare .vault/, no domains)
├── specs/                      # design history: model spec, decisions D1–D9, phase trackers
├── tests/                      # the pytest suite (434 tests)
└── docs/                       # this documentation — describes the current state
```

The live install is a symlink to this repo
(`~/.hermes/plugins/obsidian-vault -> <repo>`), so edits here are live
after a Hermes restart. There is no copy/deploy step.

## Running the tests

The test venv lives in the repo (gitignored). Run the suite with:

```bash
PATH="$PWD/.venv-test/bin:$PATH" pytest tests/ -q
```

(or `.venv-test/bin/python -m pytest tests/ -q`). The suite collects
434 tests. Always confirm the live count with
`pytest --collect-only -q` before quoting it.

Test files map to engine areas: `test_config*` (inheritance, edit
tool), `test_permissions.py` + `test_ownership.py` + `test_permission_coherence.py`
(grants and shadowing), `test_generate_and_scaffold.py`, `test_graph_and_query.py`,
`test_notes_and_context.py`, `test_issues.py` + `test_issue_tools.py`,
`test_maintain.py`, `test_protocols.py`, `test_conventions.py`,
`test_paths.py`, `test_setup*.py` (installer), `test_growth.py` (role
verbs), `test_entrypoint.py` (tool registration), `test_portability.py`
(the policy-name guard), `test_summary_field.py`.

Two gates are load-bearing:

- **`test_entrypoint.py`** calls `register()` against a fake context and
  asserts every tool registers. A missing handler inside `register()`
  passes the rest of the suite yet loads zero tools — after touching the
  entrypoint or handler wiring, run this file specifically.
- **`test_portability.py`** runs the whole engine against a deliberately
  foreign vault layout (PARA folders, different field names) and greps
  engine sources for leaked policy names (tree/folder/field/agent
  names). The engine may name only the reserved machinery constants
  (`STATE`, `VAULT`, `ISSUES` — adding a new one means extending the
  reserved list in this test too).

## Engineering rules

The codebase is held to six design invariants — derive, don't declare;
mechanism in code, policy in config; validate at the door; shared
modules, thin entrypoints, tests per phase; skill holds procedure,
vault holds content; no role-split tool registration. They are defined
in [concepts/architecture.md](concepts/architecture.md#core-invariants);
a change that breaks one is a design review, not a code review.

## Design discipline

- **Phases that change what agents can do** (grants, new tools,
  manager powers) are designed as a spec doc before any code — the
  grant model is a hard constraint that shapes the solution space.
  Mechanical refactors with a green suite as the safety net need no
  tracker.
- **Specs are the record.** `specs/` holds the model spec, the settled
  decisions (D1–D9), and the phase trackers. When a behavior changes,
  update this documentation (the current state) and the relevant spec
  tracker; the design decision itself is amended, never rewritten in
  place.

## Verification loops

Beyond the pytest suite, three patterns are used for behavioral
changes:

1. **Ad-hoc throwaway probe** — a small script that seeds a minimal
   `.vault/config.yaml` + `roles.yaml`, exercises the changed path,
   asserts, then is deleted. This is also the only layer that can probe
   live vault state (tool availability, a real context call).
2. **Fresh-machine E2E** — the dev-machine install is a symlink, so the
   installer never runs against a virgin home during development.
   `scripts/verify-install-e2e.py` drives the real stage machine as a
   subprocess against a scratch `HERMES_HOME` + vault (both presets),
   asserting profiles, skill overlays, SOUL sections, env vars, and a
   functional grant probe. Run it after installer changes.
3. **Live-state probe** — for changes that ship through the presets,
   verify against the live vault with a throwaway probe (load roles,
   assert the new grant semantics, grep for retired-model remnants),
   then delete the probe.

Two environment facts to remember: the desktop terminal inherits the
gateway's `PYTHONPATH`, which the repo venv resolves `yaml` through —
don't clobber it with `PYTHONPATH=.`; and long Python heredocs can trip
the terminal lifecycle guard — write probes to a file with the file
tool and run them instead.
