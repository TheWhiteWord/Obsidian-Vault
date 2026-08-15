"""Tool schemas — the agent-facing surface.

Kept apart from dispatch so the entrypoint stays a thin wiring layer, and so
the surface can be reviewed as a whole.
"""

from __future__ import annotations

from typing import Any, Dict, List

_VAULT_ARG = {
    "type": "string",
    "description": "Optional vault root override. Defaults to $OBSIDIAN_VAULT_PATH.",
}

_AGENT_ARG = {
    "type": "string",
    "description": (
        "Which agent is acting, as named in .vault/roles.yaml. Determines what "
        "is permitted. Defaults to $OBSIDIAN_VAULT_AGENT."
    ),
}

#: One-line reminder appended to mutating tools (Decision B, P3.7): the tool
#: never verifies the agent read the conventions — the writing loop is
#: assumed to have worked at skill level. It points back at the skill's
#: writing rules, not at any tool payload.
_CONVENTIONS_REMINDER = (
    " Verify the note against the vault's writing conventions (this "
    "skill's writing loop) before finalizing."
)


OBSIDIAN_CONTEXT: Dict[str, Any] = {
    "name": "obsidian_context",
    "description": (
        "Get everything needed to write a conforming note in one vault folder: "
        "the merged frontmatter schema, the vocabulary actually in use there "
        "(declared vs observed), the folder's tag cloud, sibling notes to link "
        "to, and a ready-to-fill template. Call this BEFORE writing any vault "
        "note — it replaces reading schema and taxonomy documents."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "folder": {
                "type": "string",
                "description": "Vault-relative folder path, e.g. 'Projects/Alpha'. "
                               "Use '.' for the vault root.",
            },
            "vault": _VAULT_ARG,
        },
        "required": ["folder"],
    },
}


OBSIDIAN_WRITE: Dict[str, Any] = {
    "name": "obsidian_write",
    "description": (
        "Create or update a vault note. Frontmatter is validated against the "
        "folder's schema before anything is written — a non-conforming note is "
        "refused with the specific problems listed, not silently accepted. "
        "Call obsidian_context first to learn the schema. Writes outside your "
        "granted domain are refused." + _CONVENTIONS_REMINDER
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Vault-relative note path ending in .md, e.g. "
                               "'Projects/Alpha/kickoff.md'.",
            },
            "frontmatter": {
                "type": "object",
                "description": "YAML frontmatter as a mapping. Missing fields with "
                               "configured defaults are filled automatically.",
            },
            "body": {
                "type": "string",
                "description": "Markdown body, without the frontmatter block.",
            },
            "register": {
                "type": "object",
                "description": (
                    "Optionally register a NEW vocabulary value, e.g. "
                    "{\"kind\": \"aphorism\"}. Requires the 'config' grant. Prefer "
                    "reusing an existing value — check obsidian_context first."
                ),
            },
            "overwrite": {
                "type": "boolean",
                "description": "Required to replace an existing note. Default false.",
            },
            "agent": _AGENT_ARG,
            "vault": _VAULT_ARG,
        },
        "required": ["path", "frontmatter"],
    },
}


OBSIDIAN_EDIT_METADATA: Dict[str, Any] = {
    "name": "obsidian_edit_metadata",
    "description": (
        "Change a note's frontmatter without touching its body. Body prose is "
        "left byte-identical. Use for status changes, tag fixes, and link "
        "repair. Requires the 'meta' grant. Pass null as a value to remove a field."
        + _CONVENTIONS_REMINDER
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Vault-relative note path."},
            "changes": {
                "type": "object",
                "description": "Frontmatter keys to set. null removes a key.",
            },
            "agent": _AGENT_ARG,
            "vault": _VAULT_ARG,
        },
        "required": ["path", "changes"],
    },
}


OBSIDIAN_DELETE: Dict[str, Any] = {
    "name": "obsidian_delete",
    "description": (
        "Delete a vault note. Requires the 'write' grant for that path — an "
        "'append' grant is not sufficient, so agents that may raise issues "
        "cannot remove them." + _CONVENTIONS_REMINDER
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Vault-relative note path."},
            "agent": _AGENT_ARG,
            "vault": _VAULT_ARG,
        },
        "required": ["path"],
    },
}


OBSIDIAN_SCAFFOLD: Dict[str, Any] = {
    "name": "obsidian_scaffold",
    "description": (
        "Create a vault folder — cheaply. Given a path and a plain-language "
        "intent, it returns a proposal of only what this folder needs BEYOND "
        "what it inherits, and writes nothing unless confirm=true. If the folder "
        "needs no special config, that is the correct answer and it says so. "
        "Structural config (new required fields) needs user confirmation; "
        "vocabulary values do not. Scaffolding is a write operation."
        + _CONVENTIONS_REMINDER
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string",
                     "description": "Vault-relative folder to create, e.g. 'Projects/Alpha'."},
            "intent": {"type": "string",
                       "description": "Plain-language reason for the folder — recorded in the audit trail."},
            "proposed": {"type": "object",
                         "description": "Optional config delta this folder needs beyond inheritance."},
            "confirm": {"type": "boolean",
                        "description": "Write the folder and any config. Default false (propose only)."},
            "agent": _AGENT_ARG,
            "vault": _VAULT_ARG,
        },
        "required": ["path"],
    },
}


OBSIDIAN_INDEX: Dict[str, Any] = {
    "name": "obsidian_index",
    "description": (
        "Regenerate derived artifacts: a folder's INDEX and/or the vault "
        "registry. Use after bulk changes, or to produce a human-readable view "
        "of the effective schema. INDEX files are generated and overwritten."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "folder": {"type": "string",
                       "description": "Folder to reindex, or '.' for the whole vault."},
            "registry_to": {"type": "string",
                            "description": "Vault-relative folder to write the registry into."},
            "agent": _AGENT_ARG,
            "vault": _VAULT_ARG,
        },
        "required": [],
    },
}


OBSIDIAN_AUDIT: Dict[str, Any] = {
    "name": "obsidian_audit",
    "description": (
        "Read the append-only audit trail: every vault mutation the plugin "
        "performed, with agent, action, path, and timestamp."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Max entries (most recent first).", "default": 100},
            "agent": {"type": "string", "description": "Filter by agent name."},
            "action": {"type": "string", "description": "Filter by action (create/edit/delete/scaffold)."},
            "vault": _VAULT_ARG,
        },
        "required": [],
    },
}


OBSIDIAN_REFERENCE: Dict[str, Any] = {
    "name": "obsidian_reference",
    "description": (
        "Discover what the vault engine supports. Returns the engine's own "
        "configuration reference: every config option (e.g. summary_field, "
        "vocabulary flags, paths.state) and the five grant kinds, with where "
        "each lives and what it does. Use this when setting up a new vault, or "
        "when you are unsure whether a capability exists. Self-describing, so it "
        "never drifts from the code."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
}


OBSIDIAN_SEARCH: Dict[str, Any] = {
    "name": "obsidian_search",
    "description": (
        "Find notes by term match across titles, tags, bodies, links, and "
        "frontmatter. Deterministic (no embeddings). Supports a `scope` glob to "
        "limit the scan, `group_by` (folder/any-field/tag) to bucket results, and "
        "silent grant intersection — an agent searching '**' simply receives "
        "nothing from where it cannot read. Use this instead of reading folders "
        "blind."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string",
                      "description": "Space-separated terms; a note must contain all of them."},
            "scope": {"type": ["string", "array"],
                      "items": {"type": "string"},
                      "description": "Glob or list of globs over vault-relative paths, e.g. 'CREATIVE/**' or ['work/creative/**', '!work/creative/knowledge/**']. A '!' prefix excludes matching paths — it can only remove results, never add them. Independent of read grants; results are intersected with both."},
            "folder": {"type": "string",
                       "description": "Convenience: search only this subtree (equivalent to scope='<folder>/**')."},
            "fields": {"type": "array", "items": {"type": "string"},
                       "description": "Surfaces to match: title|body|tags|links|frontmatter. Default all."},
            "group_by": {"type": "string",
                         "description": "Bucket results by 'folder', 'tag', or any frontmatter field name."},
            "limit": {"type": "integer", "description": "Max results (or per bucket).", "default": 50},
            "agent": _AGENT_ARG,
            "vault": _VAULT_ARG,
        },
        "required": [],
    },
}


OBSIDIAN_GRAPH: Dict[str, Any] = {
    "name": "obsidian_graph",
    "description": (
        "Navigate the wikilink graph. Given a note, return its linked neighbors "
        "(in/out/both) or walk N hops. Dangling links (pointing at missing notes) "
        "are reported so they can be fixed. The graph is derived from note bodies, "
        "never cached, so it cannot drift."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Vault-relative note to centre on."},
            "hops": {"type": "integer", "description": "Breadth-first depth. Default 1.", "default": 1},
            "direction": {"type": "string", "enum": ["both", "out", "in"], "default": "both"},
            "dangling": {"type": "boolean", "description": "Return only links to missing notes.", "default": False},
            "agent": _AGENT_ARG,
            "vault": _VAULT_ARG,
        },
        "required": ["path"],
    },
}


OBSIDIAN_ISSUE: Dict[str, Any] = {
    "name": "obsidian_issue",
    "description": (
        "Raise one or more issues on the vault's issue ledger. Issues are "
        "structured records (not notes): they are invisible to search and the "
        "graph, and are seen only through the issue tools or the manager's "
        "report. This is the escalation valve — any agent may raise an issue "
        "about anything it found; the audit trail records who. Use for "
        "vault problems you cannot fix yourself, or requests to a domain "
        "owner. Duplicate keys are skipped; a closed issue with the same key "
        "is re-opened."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string",
                                    "description": "Short one-line title."},
                        "detail": {"type": "string",
                                   "description": "What is wrong, with enough "
                                                  "context to act on it."},
                        "target": {"type": "string",
                                   "description": "Vault-relative path of the "
                                                  "affected note, or a scope "
                                                  "glob like 'system/**' for "
                                                  "tool/system-wide issues."},
                        "priority": {"type": "string",
                                     "enum": ["low", "medium", "high", "critical"],
                                     "description": "Default medium."},
                        "tags": {"type": "array", "items": {"type": "string"},
                                 "description": "Optional tags, e.g. "
                                                "['plugin', 'research']."},
                        "assignee": {"type": "string",
                                     "description": "Optional profile name of "
                                                    "who SHOULD resolve this. "
                                                    "A SHOULD signal, never a "
                                                    "grant override — pick the "
                                                    "agent whose write/meta "
                                                    "covers the target (see "
                                                    "issues.md directive)."},
                        "key": {"type": "string",
                                "description": "Optional dedupe key. Omit to "
                                               "derive one from subject+target."},
                    },
                    "required": ["subject", "detail", "target"],
                },
                "description": "One or more issues to raise (the manager's batch).",
            },
            "agent": _AGENT_ARG,
            "vault": _VAULT_ARG,
        },
        "required": ["items"],
    },
}


OBSIDIAN_ISSUE_RESOLVE: Dict[str, Any] = {
    "name": "obsidian_issue_resolve",
    "description": (
        "Move an issue on the ledger: route it (assignee — sets who should "
        "resolve), claim it (in_progress — records you as the holder), or "
        "close it (resolved — the problem is fixed; declined — won't fix / "
        "not a problem). Requires the 'write' or 'meta' grant over the "
        "issue's target — you can act on issues about notes you own. "
        "Optionally record why."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "key": {"type": "string",
                    "description": "The issue's dedupe key, as returned by "
                                   "obsidian_issue_list."},
            "assignee": {"type": "string",
                         "description": "Profile to route the issue to (who "
                                        "SHOULD resolve it). Pass this to "
                                        "assign an open issue without "
                                        "changing its state; leave the "
                                        "owning agent to claim/resolve. "
                                        "Grant-gated: write or meta over "
                                        "the target."},
            "state": {"type": "string",
                      "enum": ["in_progress", "resolved", "declined"],
                      "description": "in_progress claims the issue (sets "
                                     "claimed_by); resolved/declined close it. "
                                     "Omit when only assigning."},
            "reason": {"type": "string",
                       "description": "Optional closure reason."},
            "agent": _AGENT_ARG,
            "vault": _VAULT_ARG,
        },
        "required": ["key"],
    },
}


OBSIDIAN_ISSUE_LIST: Dict[str, Any] = {
    "name": "obsidian_issue_list",
    "description": (
        "List issues on the ledger, filtered and grant-intersected: you see "
        "only issues whose target you can read. 'My issues' is a query, not a "
        "folder — the ledger has no per-domain inboxes. Use this to check for "
        "issues raised to you (e.g. tags: ['maintenance'] from the manager), "
        "or before raising one, to avoid duplicates."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "state": {"type": "string",
                      "enum": ["open", "in_progress", "resolved", "declined"]},
            "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
            "tags": {"type": "array", "items": {"type": "string"}},
            "target": {"type": "string",
                       "description": "Only issues whose target falls under "
                                      "this glob, e.g. 'work/creative/**'."},
            "raised_by": {"type": "string", "description": "Filter by raiser agent."},
            "assigned_to": {"type": "string",
                            "description": "Filter by assignee profile name; "
                                           "'me' resolves to the calling "
                                           "agent."},
            "limit": {"type": "integer", "description": "Max entries.", "default": 50},
            "agent": _AGENT_ARG,
            "vault": _VAULT_ARG,
        },
        "required": [],
    },
}


OBSIDIAN_MAINTAIN: Dict[str, Any] = {
    "name": "obsidian_maintain",
    "description": (
        "Run the vault maintenance sweep: detect broken links, orphans, "
        "malformed frontmatter, empty notes, and (in optimize mode) quality "
        "suggestions; regenerate INDEXes; promote vocabulary; and distribute "
        "findings as ledger issues (dedupe by key). Three depths — cron "
        "drives the mode: 'delta' (check only what changed since the last "
        "sweep), 'maintain' (full correctness census), 'optimize' (add "
        "suggestions). dry_run rehearses with zero writes. The manager never "
        "edits content; findings are for the owning domain agent."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["delta", "maintain", "optimize"],
                     "description": "Sweep depth. Default maintain."},
            "distribute": {"type": "boolean",
                           "description": "Create ledger issues from findings. "
                                          "Default true."},
            "dry_run": {"type": "boolean",
                        "description": "Report only, write nothing, advance "
                                       "nothing. Default false."},
            "agent": _AGENT_ARG,
            "vault": _VAULT_ARG,
        },
        "required": [],
    },
}


OBSIDIAN_EDIT_CONFIG: Dict[str, Any] = {
    "name": "obsidian_edit_config",
    "description": (
        "Edit an existing .vault/config.yaml — the config-gated sibling of "
        "obsidian_scaffold, for files that already exist (scaffold refuses "
        "those). Same delta semantics: propose what should change, get back "
        "only the real delta beyond what the folder already inherits, and "
        "nothing is written unless confirm=true. Any change to fields or "
        "validation needs proposed.user_confirmed=true (mirroring "
        "obsidian_scaffold); defaults/tags flow freely. Requires the "
        "`config` grant over the target — a domain owner "
        "holds it on its own tree (D-5); root config and roles.yaml stay "
        "manager-only. Never edits roles.yaml. Edits that would break the "
        "uniformity contract (redefining format/multi) are refused — "
        "dropping an inherited required is legal since P7 (nearest wins)."
        + _CONVENTIONS_REMINDER
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string",
                     "description": "Vault-relative path to an existing config "
                                    "file, e.g. 'work/creative/recipes/.vault/config.yaml'."},
            "proposed": {"type": "object",
                         "description": "Desired changes, same shape as "
                                        "obsidian_scaffold's proposed: "
                                        "fields/defaults/tags/validation. "
                                        "Structural keys need "
                                        "user_confirmed: true."},
            "confirm": {"type": "boolean",
                        "description": "Apply the delta. Default false "
                                       "(propose only)."},
            "agent": _AGENT_ARG,
            "vault": _VAULT_ARG,
        },
        "required": ["path", "proposed"],
    },
}


OBSIDIAN_CONVENTIONS: Dict[str, Any] = {
    "name": "obsidian_conventions",
    "description": (
        "Read or edit the vault's per-scope conventions — the writing "
        "directives that live in-tree at <scope>/.vault/conventions.md. "
        "Nearest scope wins; absent rules fall back up the chain. Read "
        "mode (pass a folder): returns the resolved chain — nearest file "
        "plus every fallback, with content. Edit mode (pass a path ending "
        "in .vault/conventions.md plus content): only the derived owner of "
        "the scope may write — the manager never writes conventions. "
        "Conventions are policy prose, not notes: no frontmatter "
        "validation, no INDEX regeneration, invisible to search."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "folder": {"type": "string",
                       "description": "Read mode: vault-relative folder "
                                      "whose resolved conventions chain to "
                                      "return."},
            "path": {"type": "string",
                     "description": "Edit mode: vault-relative path to a "
                                    ".vault/conventions.md file."},
            "content": {"type": "string",
                        "description": "Edit mode: the new file content."},
            "agent": _AGENT_ARG,
            "vault": _VAULT_ARG,
        },
        "required": [],
    },
}


OBSIDIAN_PROTOCOL_LIST: Dict[str, Any] = {
    "name": "obsidian_protocol_list",
    "description": (
        "List the inter-agent handoffs registered in the vault's protocol "
        "registry where you are a party (requester or responder). Optional "
        "peer=<profile> narrows to the handoffs you have with that specific "
        "agent. Registry records live in .state/protocols/ — structured "
        "records, not notes: no frontmatter validation, no INDEX "
        "regeneration, invisible to search. Read is grant-free for any "
        "registered agent; list results are party-filtered by construction."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "peer": {
                "type": "string",
                "description": "Narrow to handoffs between you and this profile (either direction).",
            },
            "agent": _AGENT_ARG,
            "vault": _VAULT_ARG,
        },
        "required": [],
    },
}


OBSIDIAN_PROTOCOL: Dict[str, Any] = {
    "name": "obsidian_protocol",
    "description": (
        "Read, register, or update one inter-agent handoff in the vault's "
        "protocol registry. Read mode (pass name): the full record — both "
        "sides' instructions. Register mode (pass register with a record): "
        "create a new handoff; you must be one of the sides. Update mode "
        "(pass name + update with a record): replace an existing handoff; "
        "you must be a party of the existing record. Records carry "
        "requester/responder profiles + domains, request/response formats, "
        "and instructions. Pass confirm=true to apply; without it the call "
        "validates and gates and returns the would-be record (propose mode)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Read mode: the handoff's name to load. Update mode: the existing handoff's name.",
            },
            "register": {
                "type": "object",
                "description": "Register mode: the new handoff record {name, requester: {profiles, domains?}, responder: {profiles, domains?}, request_format, response_format, instructions}.",
            },
            "update": {
                "type": "object",
                "description": "Update mode: the replacement record (same shape as register).",
            },
            "confirm": {
                "type": "boolean",
                "description": "Apply the write. Default false (propose only).",
                "default": False,
            },
            "agent": _AGENT_ARG,
            "vault": _VAULT_ARG,
        },
        "required": [],
    },
}


ALL_SCHEMAS: List[Dict[str, Any]] = [
    OBSIDIAN_CONTEXT,
    OBSIDIAN_WRITE,
    OBSIDIAN_EDIT_METADATA,
    OBSIDIAN_DELETE,
    OBSIDIAN_SCAFFOLD,
    OBSIDIAN_EDIT_CONFIG,
    OBSIDIAN_CONVENTIONS,
    OBSIDIAN_INDEX,
    OBSIDIAN_AUDIT,
    OBSIDIAN_REFERENCE,
    OBSIDIAN_SEARCH,
    OBSIDIAN_GRAPH,
    OBSIDIAN_ISSUE,
    OBSIDIAN_ISSUE_RESOLVE,
    OBSIDIAN_ISSUE_LIST,
    OBSIDIAN_PROTOCOL_LIST,
    OBSIDIAN_PROTOCOL,
    OBSIDIAN_MAINTAIN,
]
