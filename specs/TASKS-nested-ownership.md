# P7 — Nested ownership (domains, subdomains, content & scope directives)

Status: **design confirmed (2026-08-06) — implementation pending.**
Design: `07-nested-ownership.md` (§1 N-1…N-10; sign-offs A–D all given).

## Why

The two-tier model conflates *rules granularity* with *ownership granularity*.
A subfolder owned by a different profile (the researcher's `knowledge/` inside
a writer's domain) is today an overlap hack — two agents hold write over the
same tree and "owner" is ambiguous. P7 makes ownership nested and exclusive
(derived, not declared), moves conventions in-tree as per-scope directives
(killing the `<vault>-conventions.md` orphan problem), allows scoped frontmatter
relaxation, and restates the manager's optimize mode as connection *proposing*
(a skill directive, not engine machinery).

## Decisions locked (spec §1, 2026-08-06)

- **N-1** three tiers, ownership boundary only when the profile differs
- **N-2** derived ownership from **canonical ownership globs** (`work/<d>/**`,
  `work/<d>/<s>/**` — bind-produced only); capability globs never shadow
- **N-3** shadowing: `write`/`config` owner-only; `read`/`meta` generous
- **N-4** subdomain owner gains `read` over each parent domain at bind
- **N-5/N-6** conventions in-tree, nearest wins, fallback on absence only
- **N-7** relax surface: `required: false` legal at child scope; `format`/`multi`
  stay immutable
- **N-8** issue delivery ownership-routed **by the manager** (resolver as shared
  utility; distribution unchanged)
- **N-9** optimize = connection proposing, a **skill directive** (no engine scan)
- **N-10** single grant-surgery surface — manager executes `bind --domain`
  with slashed paths

Sign-offs: **A** writer loses write in `knowledge/` (read+meta remain) ·
**B** conventions retirement incl. the `obsidian_conventions` tool and §4.6 SOUL
restatement · **C** `format`/`multi` immutable · **D** P7 before coder-plugin.

## Tasks

1. **Design doc** — `07-nested-ownership.md` (drafted, verified for
   contradictions/over-engineering, reframed: canonical globs, dedicated
   conventions tool, no engine dispatcher/scan). **DONE**

2. **P7.1 — Engine: ownership resolver + shadowing** (grants.py or new
   `vault/ownership.py`) — **DONE (325 tests, suite green)**
   - `owner_of(path)`: canonical ownership globs only (1–3 literal segments);
     most-segments wins; capability globs excluded by construction
   - `write`/`config`/append resolution shadowed to the derived owner;
     `read`/`meta` untouched (generous)
   - bind-time validation: canonical shape + duplicate-ownership-glob refusal
   - Tests: most-segments, capability-never-shadows, tie/overlap refusal,
     knowledge/ example, unbind lifts shadowing, config/append shadowed,
     meta/read generous. Fixture gained the D-5 owner-config grant; legacy
     append/issues-channel tests moved to owner-consistent targets.
   - **Carry-forward for P7.7:** (a) the manager's config authority is now
     root/unowned-only in owned scopes — manager skill must state it;
     (b) vocabulary promotion silently no-ops in owned scopes (warning log)
     — the manager raises a suggestion instead; (c) append is effectively
     dead in owned vaults (unowned trees only) — the preset ships none.

3. **P7.2 — Engine: relax surface** (config.py merge) — **DONE (326 tests,
   suite green)**
   - `required: false` at a child scope (nearest declaration wins); the
     load-time ConfigError and edit_config's pre-write refusal both removed;
     `format`/`multi` redefine still `ConfigError`
   - Tests: child relax validates + parent unaffected; dropped-required field
     still format-checks when present; edit_config relax lands in the file;
     format/multi immutability holds. Doc claims updated (schemas.py tool
     text, reference.py entry, scaffold.py docstrings).

4. **P7.3 — Engine: conventions in-tree + `obsidian_conventions` tool** —
   **DONE (344 tests, suite green)**
   - `vault/conventions.py`: walk-up discovery (root-first chain, nearest
     wins), resolved chain with content, fingerprint, write gate
   - `obsidian_conventions` tool (schemas.py + `_handle_conventions`):
     read chain (any agent) / edit gated on write-over-scope (audited, no
     INDEX, no note validation); `write.py` machinery wall untouched
   - `obsidian_context` gains the one-line `conventions` pointer (§4.3)
   - constants.CONVENTIONS_FILENAME; RESERVED_NAMES + plugin.yaml +
     EXPECTED_TOOLS all carry the 16th tool
   - Tests: discovery (nearest/fallback/root-first), write gate (owner,
     non-owner, manager-never, subdomain shadowing), machinery invisibility,
     audit + no-INDEX, context pointer present/absent, tool surface.
     **CHECKPOINT — suite green; natural handoff point.**

 5. **P7.4 — Scripts: bind/unbind subdomain form + refusals** — **DONE
    (352 tests, suite green)**
    - `_validate_domain_bind` runs in `role_bind` BEFORE any write: shape
      (domain or one-level subdomain path), content-not-subdomain (profile
      already owns the parent → "that's content — use scaffold"), duplicate
      ownership glob
    - `_append_agent_grant`: domain bind now also grants meta (the backstop
      grant); subdomain bind = write/config/meta on the subdomain + read
      over the parent (N-4), no shared-knowledge glob
    - `role_unbind --domain <d>/<s>`: revokes the subdomain globs AND the
      orphaned parent read (kept when a sibling subdomain remains)
    - `_is_manager_block` predicate — the meta backstop broke the
      exact-match manager regex; the manager is the agent holding root
      `"**"` meta, not only it (`_manager_profile` + `_roles_from_grants`
      fixed; transfer tests green)
    - roles.py argparse help + docstring (`--domain PATH`)

6. **P7.5 — Installer: conventions seeding + SOUL restatement** — **DONE
   (349 tests, suite green)**
   - `ensure_root_conventions` replaces `ensure_conventions_file` /
     `vault_conventions_name`: seeds `<vault>/.vault/conventions.md` from
     `templates/vault-conventions.md`, copy-if-missing (grows through
     interaction); `scaffold_vault` seeds it for BOTH presets
   - SOUL block restated: `### Convention maintenance` points at the
     in-tree file; `### Convention manifest` + `<!-- add:` marker RETIRED
   - `append_manifest_entry` / `remove_manifest_entries` deleted;
     role_bind / unbind / transfer no longer touch the SOUL for
     conventions; `uninstall_skills` prunes the engine-created empty
     conventions/ dir (copy-on-write content preserved)
   - Tests: retired-function tests replaced by ensure_root_conventions +
     scaffold-seeding tests; all SOUL/manifest pins updated
   - **Still to do in P7.7:** install_skills' empty conventions/ dir
     creation + SKILL.md:87 reference
     re-run. **Suite green.**

7. **P7.6 — Presets + E2E** — **DONE**
   - `examples/starter-vault/.vault/roles.yaml`: researcher = literal
     subdomain owner (enumerated `work/creative/knowledge/**` +
     `work/coding/knowledge/**`; wildcard write retired, survives as
     read-only); `creative`/`dev` gain `meta` on their domain (backstop)
   - `_role_grants` parity (questionnaire matches the preset); finalize
     neutralizes unassigned preset agents (one-agent ownership fix —
     found by the E2E probe, not the suite); `_ensure_agent_block`
     scan-bound bug fixed (IndexError with two missing grant kinds)
   - Preset READMEs restated to three tiers; subdomains read-only to the
     domain owner; researcher row added
   - E2E probe: nested-researcher grant probes, manager-config P7 check,
     one-agent semantic checks, conventions-seeded check — **ALL PASS** on
     a scratch machine. **Suite 349 green.**

8. **P7.7 — Skills + references (docs layer)** — **DONE**
   - Both role SKILL.mds restated: conventions in-tree +
     `obsidian_conventions`, subdomain triage routing, optimize directive,
     backstop grant in growth-protocol (bind grants verified against
     `_append_agent_grant`), `required` relax surface, issues delivery
     routing — every claim grep-verified against the engine
     (tool grants, glob shapes, field names, TTLs)
   - Engineering skill: P7 decision record
     (`references/p7-nested-ownership-shipped.md`), state doc superseded,
     trajectory + locked constraints updated (16 tools, relaxable
     `required`)
   - **Verification at phase:** stale-claim grep zero hits (manifest,
     `conventions/<vault>`, accumulate-only) **Suite green**

9. **P7.8 — Final verification + live rollout** — **DONE**
   - `--collect-only` 349; full suite green; entrypoint + portability pass
   - Docs/README verification: repo README test count fixed (302 → 349);
     preset READMEs verified (P7.6); live vault README restated
   - **Live rollout (approved, shipped):** `roles.yaml` restructured to the
     P7.6 shape (copied from the canonical preset — zero local drift),
     `.vault/conventions.md` seeded via `ensure_root_conventions`, all 5
     live SOULs restated (manifest retired, in-tree pointer), live README
     three-tier restate — verified by a live-vault probe (13/13: grants
     fire per the new model, no manifest remnants)
   - Fresh-machine E2E final run: **ALL PASS**. **Suite 349 green.**

10. **P7.9 — Commit prep** — layered commits (engine → scripts → installer →
    presets → docs), working tree clean, suite count in the tracker. Davide
    pushes via VS Code.

## Invariants enforced

- Ownership is derived from canonical globs only — capability globs never
  shadow (N-2).
- Shadowing touches `write`/`config` only; `read`/`meta` stay generous (N-3).
- `write.py` never gains an exception: conventions edits go through
  `obsidian_conventions` (sign-off B).
- `format`/`multi` immutability holds everywhere, subdomains included (sign-off C).
- Distribution and suggestion machinery are untouched — delivery/optimize are
  manager directives (N-8/N-9).
- The manager never writes prose — including conventions.
- Every doc edit is verified against the engine before it's called done
  (zero-hit grep is the completion criterion).
