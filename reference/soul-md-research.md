# SOUL.md — Research Findings (Hermes)

Source-verified against the Hermes agent repo (local checkout
`~/.hermes/hermes-agent/`) and the official docs
(`hermes-agent.nousresearch.com/docs`), 2026-08-06. This is the raw
material the full-SOUL design (`specs/08-soul-design.md`) is built on —
when the two disagree, the spec wins; when either disagrees with the
engine, the engine wins.

## What SOUL.md is

- **Primary identity — slot #1 of the system prompt.** Loaded verbatim from
  `$HERMES_HOME/SOUL.md` (the `default` profile IS the home root; named
  profiles live at `profiles/<name>/SOUL.md`). It **completely replaces**
  the hardcoded default identity (`DEFAULT_AGENT_IDENTITY`). No wrapper
  language is added around the file — the content itself is the identity.
- Loaded through: prompt-injection scanning → truncation (cap scales with
  model context window; floor 20K chars, `config.context_file_max_chars`
  overrides) → injected as-is.
- Missing, empty, whitespace-only, or unreadable → falls back to the
  built-in default identity. `skip_context_files` (subagent delegation)
  also skips it.
- Never loaded from the working directory — only from `HERMES_HOME`.
  Personality is per-instance, not per-project.

## What belongs in it (and what does not)

| ✅ SOUL.md (identity/voice) | ❌ SOUL.md (→ AGENTS.md) |
|---|---|
| tone, personality, communication style | repo-specific coding conventions |
| how direct / how warm | file paths |
| stylistic avoids | commands |
| how to handle uncertainty, disagreement, ambiguity | service ports |
|  | architecture notes |
|  | project workflow instructions |

The docs' test: *"if it should apply everywhere → SOUL.md; if it only
belongs to one project → AGENTS.md."*

Troubleshooting guidance is blunt: *"My SOUL.md became too
project-specific → Move project instructions into AGENTS.md and keep
SOUL.md focused on identity and style."*

## Strong vs weak

**Strong** SOUL.md is:

- stable (survives across contexts/sessions)
- broadly applicable (applies to many conversations)
- specific in voice (materially shapes how the agent speaks)
- not overloaded with temporary instructions

**Weak** SOUL.md is:

- full of project details
- contradictory
- micro-managing every response shape
- mostly generic filler ("be helpful", "be clear" — Hermes already tries
  those by default; restating them is dead weight)

## Suggested structure

Headings are optional but help. The docs' recommended shape:

```
# Identity   — who the agent is
# Style      — how the agent sounds
# Avoid      — what the agent should not do
# Defaults   — how the agent behaves when ambiguity appears
```

The practical workflow the docs recommend: start from the seeded default,
trim anything that doesn't feel like the wanted voice, add 4–8 lines of
real tone/defaults, iterate from real conversations. Don't design the
perfect personality in one shot.

## Voice exemplars (from the docs)

Four shipped example styles — pragmatic engineer, research partner,
teacher/explainer, tough reviewer. Common shape: `You are …` opener + a
`## Style` bullet list of imperative voice rules + optional `## Avoid`.
No filler, no project details, no tool grammar.

## Seeding / overwrite semantics (engine-verified)

- `hermes profile create <name>` seeds `DEFAULT_SOUL_MD` (the single
  "You are Hermes Agent…" paragraph) **only when no SOUL.md exists**;
  clones (`--clone` / `--clone-all`) copy the source's SOUL.md wholesale.
- Hermes **never overwrites an existing SOUL.md**.
- SOUL.md presence is the "real profile" marker (`container_boot.py`).

### The "safe to overwrite" precedent — `default_soul.py`

Hermes itself ships the concept the plugin's replace-vs-append rule is
built on. `is_legacy_template_soul(text)` returns True when the file
content matches a known installer template (comment-only scaffolding).
The module docstring states the safety guarantee:

> "these strings carry zero user intent … safe to upgrade in place. …
> **Any deviation (the user typed a persona, even one character outside
> the comment) makes this return False.**"

A SOUL.md whose content is *exactly* a known shipped template is
provably untouched by the user → safe to replace. Anything else → the
user has intent in it → never touch. `_ensure_default_soul_md`
(`config.py`) uses exactly this to upgrade legacy templates in place.

## Interaction with the rest of the prompt

System prompt layers (stable → context → volatile): SOUL.md is the first
stable layer; skills index, memory, and user profile are separate layers
injected elsewhere. Consequences:

- SOUL.md does **not** need to enumerate skills — the skills index
  already lists them with descriptions.
- SOUL.md does **not** need memory facts — memory/USER are separate
  volatile snapshots.
- The plugin's `## Vault` block naming tools + references is a deliberate
  deviation from the "no commands in SOUL.md" rule: it is the only
  profile-scoped injection point (profiles have no AGENTS.md), and it is
  kept to pointers (tools + references), never prose instruction — the
  discipline that keeps it from becoming the "too project-specific" SOUL
  the docs warn about.

## Relevant facts for the plugin design

- The full-SOUL templates ship identity + style prose; the anchored
  `## Vault` block stays untouched (anchor comment
  `<!-- vault-soul: managed by the installer; do not edit -->` is the
  managed boundary; `remove_soul_sections` spans anchor → next level-1
  heading or EOF).
- A full SOUL must stay compact — it is injected into every system
  prompt; the truncation cap applies per file.
- Prompt-injection scan runs on load: keep SOUL content as plain
  persona/voice prose, not meta-instructions.
- `default` is the user's primary profile; the plugin claims only the
  vault section there, never an identity (Davide's decision, 2026-08-06).
