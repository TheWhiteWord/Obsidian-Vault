# Growth protocol — reference

How a vault grows after installation: adding contributors, domains, and
subdomains. Every flow splits into **LLM steps** (suggest fields, draft a
SOUL, interpret the topic — agent judgment) and **mechanical steps**
(filesystem + config + manifest writes — `setup.py` subcommands, tested).
The agent is *aided through the process*: it knows the options at each
stage, presents them, and executes mechanically — it never improvises
filesystem surgery.

Companion design spec: `DESK/specs/06-growth-design.md` §4.

---

## 1. Who may do what (role constraints)

| Action | Role | Grant basis |
|---|---|---|
| `--add-contributor` | manager | holds `config`/`meta`/`read` on `**` |
| `--add-domain` | manager | holds `config`/`meta`/`read` on `**` |
| `--add-subdomain` | domain owner | holds `write` on the parent tree (D-2; scaffold is write-gated) |
| scaffold / edit_config inside own tree | contributor | `write` + `config` on `work/<domain>/**` |

A manager is **not** a contributor: it creates contributors and domains,
but never authors content. A contributor creates subdomains inside its own
domain without manager involvement.

---

## 2. Subdomain by contributor (Eg1 — "recipes")

*Who:* domain owner + user, mid-conversation. *Grant basis:* D-2
(scaffold is write-gated).

1. **LLM step:** contributor proposes
   `obsidian_scaffold(path, intent, proposed, confirm=false)` → a delta is
   shown (e.g. `type.allowed_only: [Recipe]`, `source.required`,
   `retrieved.required`). Field suggestions come from
   `references/config-authoring.md` patterns.
2. **User decision:** name + fields confirmed; the contributor may refine
   the field setup.
3. **Mechanical (tool):** scaffold creates the directory + `.vault/config.yaml`
   delta + regenerates the parent INDEX.
4. **Mechanical (subcommand):** record the subdomain in the owner's SOUL
   Convention manifest:

   ```bash
   python3 scripts/setup.py --vault /path/to/vault \
       --add-subdomain work/creative/recipes --owner creative
   ```

   Refused when the directory does not exist (run scaffold first) or the
   owner holds no `write` there.

5. **Report:** directory live, schema applied, what changed.

The new directory is part of the contributor's own domain by default — no
grant change, no manager involvement.

---

## 3. Full domain by manager (Eg3 — "RECIPES" + profile BOB)

*Who:* manager. *Grant basis:* manager holds `config`/`meta`/`read` on `**`.

1. **LLM step:** manager asks: domain name; existing profile or new? If
   new, profile name.
2. **LLM step:** manager proposes the field base + domain-specific
   suggestion; user describes the topic/domain.
3. **LLM step (optional):** for a new profile, draft a **tailored SOUL**
   (the profile's personality/scope) or use the standard contributor
   variant.
4. **Mechanical (subcommand):** bind the profile:

   ```bash
   python3 scripts/setup.py --vault /path/to/vault \
       --add-contributor BOB
   ```

   Creates the profile (if missing), installs the skill overlay
   (contributor role), writes the SOUL sections, seeds the profile config,
   enables the plugin, writes the `.env` bindings.

5. **Mechanical (subcommand):** create the domain:

   ```bash
   python3 scripts/setup.py --vault /path/to/vault \
       --add-domain RECIPES --owner BOB [--config /path/to/recipes.yaml]
   ```

   Creates `work/RECIPES/` + `.vault/config.yaml` (from `--config`, or a
   minimal stub), appends BOB's grant block to `roles.yaml`
   (`write`/`config` on `work/RECIPES/**`, `read` + the shared
   `work/*/knowledge/**`), seeds BOB's maintained conventions file
   `conventions/<vault>-conventions.md` from the template, and appends the
   manifest entry to BOB's SOUL.

   Refused when: the vault is not scaffolded, BOB does not exist
   (run `--add-contributor` first), the owner already has grants (extend
   by hand — manager-only policy edit), or `--config` is broken YAML.

6. **Report:** domain + profile + grants + SOUL, and what to do next.

Order matters: `--add-contributor` before `--add-domain` (the domain needs
its owner to exist).

---

## 4. Custom install (Eg2 — "LIBRARY" vault, manager Billy)

*Who:* agent driving a fresh install. *Grant basis:* D-4 (neutral preset).

1. **LLM step:** ask custom or standard default? (Standard recreates the
   five-agent starter; custom is a bare vault.)
2. **LLM + mechanical:** vault location + name; manager profile (new
   "Billy" or existing).
3. **LLM step:** SOUL tailoring choice — full tailored manager SOUL vs
   basic editable default.
4. **Mechanical:** vault scaffolded (neutral preset, no domains), manager
   profile created, overlay installed, SOUL written.
5. **Report:** vault created, manager = Billy, no domains yet — "to start
   using the vault, ask Billy to create a domain" (§3).

---

## 5. LLM-step vs mechanical-step split (summary)

| Step | Kind | Where |
|---|---|---|
| Field suggestion, SOUL drafting, topic interpretation | LLM | agent, guided by references |
| fs + config writes, grant lines, profile creation, manifest append | mechanical | `setup.py` subcommands (`--add-domain`, `--add-contributor`, `--add-subdomain`) |
| Everything auditable | mechanical | audit log + SOUL manifest |

---

## 6. The SOUL Convention manifest

Each contributor profile's SOUL ends with a **Convention manifest** — a
strict, parseable markdown list of convention files relevant to that
profile and the directories they govern:

```markdown
### Convention manifest
<!-- maintained by the growth protocol; one line per convention file -->
- `conventions/contributor.md` — role directive (immutable)
- `conventions/<vault>-conventions.md` — recipes domain conventions (work/recipes/**)
<!-- add: - `conventions/<vault>-conventions.md` — description (domain) -->
```

- Real entries accumulate **above** the `<!-- add:` marker; the marker
  stays as the directed placeholder.
- Appends are idempotent — the same line is never duplicated.
- A **manager** SOUL has no add-marker: conventions are
  contributor-maintained, so growth subcommands refuse to touch it.
- The maintained conventions file (`conventions/<vault>-conventions.md`)
  is created **copy-if-missing** from `templates/vault-conventions.md`
  with the vault name substituted. It grows through interaction — when a
  session reveals a rule worth keeping, it lands there. The installer
  never overwrites it (the survival guarantee).

---

## 7. Copy-on-write escape hatch (06-growth-design §2.3)

The skill base (`SKILL.md`, `references/`, `templates/`) is symlinked to
the bundle in every profile — shared, immutable, update-propagating. If a
single profile must customise one reference (e.g. a profile-specific tool
protocol), the escape hatch is **copy-on-write**:

1. Break the symlink for that one file/dir:
   `rm <profile>/skills/obsidian-vault/references/tool-protocol.md`
2. Copy the bundle version into place and edit the copy.
3. The installer's `_ensure_symlink` preserves a *modified* real file and
   only replaces *content-identical* stale copies — so the customised
   reference survives re-runs, while the rest of the base stays linked.

This is a deliberate, rare act — the default is shared immutable
references. Document the divergence in the profile's maintained
conventions file so the next session knows why.

---

## 8. Pitfalls

- **Order:** `--add-contributor` before `--add-domain`; scaffold (tool)
  before `--add-subdomain`.
- **Dry-run first:** every subcommand supports `--dry-run` — it prints the
  actions without touching the filesystem.
- **`--vault` is required** with growth subcommands.
- **Roles.yaml is policy with comments:** grants are appended at the end of
  the `agents:` section, never round-tripped (comments would die). If the
  owner already has grants, extend by hand — the subcommand refuses.
- **Broken YAML is refused** before any write (`--config` and the appended
  grant block are re-parsed).
- **Manager SOULs refuse manifest appends** — that is the guard that keeps
  conventions contributor-owned.
