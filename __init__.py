"""obsidian-vault plugin.

A schema-driven, permission-enforced vault engine. Filesystem-first — no
running Obsidian required, so maintenance can run headless from cron.

This module is wiring only: resolve arguments, dispatch, serialise errors.
All logic lives in ``vault/``.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict

_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

logger = logging.getLogger(__name__)

AGENT_ENV_VAR = "OBSIDIAN_VAULT_AGENT"
#: Fallback agent when none is passed and the env var is unset. `default` is
#: the Hermes default profile name, which the starter preset (D8) grants
#: `system/**` — an agent-less call must not fall through to a name that does
#: not exist in roles.yaml (deny-by-default would refuse everything).
DEFAULT_AGENT = "default"


def _resolve_agent(args: Dict[str, Any]) -> str:
    return (
        args.get("agent")
        or os.environ.get(AGENT_ENV_VAR, "").strip()
        or DEFAULT_AGENT
    )


def _dispatch(fn: Callable[..., Any], args: Dict[str, Any], needs_roles: bool) -> str:
    """Shared error handling: every failure becomes structured JSON.

    An agent should always receive an actionable object — never a stack trace,
    and never a silent success.
    """
    from vault.grants import PermissionDenied, RolesError, load_roles
    from vault.paths import VaultPathError, resolve_vault_root
    from vault.write import WriteRefused

    try:
        root = resolve_vault_root(args.get("vault"))
        kwargs: Dict[str, Any] = {"vault_root": root}
        if needs_roles:
            kwargs["agent"] = _resolve_agent(args)
            kwargs["roles"] = load_roles(root)
        return json.dumps(fn(args, **kwargs), default=str)

    except PermissionDenied as exc:
        return json.dumps({"ok": False, "error": "permission_denied",
                           "message": str(exc)})
    except WriteRefused as exc:
        return json.dumps({"ok": False, "error": "validation_failed",
                           "message": str(exc), **exc.result.to_dict()})
    except (VaultPathError, RolesError) as exc:
        return json.dumps({"ok": False, "error": type(exc).__name__,
                           "message": str(exc)})
    except Exception as exc:
        logger.exception("obsidian-vault tool failed")
        return json.dumps({"ok": False, "error": type(exc).__name__,
                           "message": str(exc)})


# --- handlers --------------------------------------------------------------

def _handle_context(args, **kw) -> str:
    def run(a, vault_root, agent, roles):
        from vault import build_context
        return build_context(vault_root, a.get("folder", "."),
                             agent=agent, roles=roles)
    return _dispatch(run, args, needs_roles=True)


def _handle_write(args, **kw) -> str:
    def run(a, vault_root, agent, roles):
        from vault.write import write_note
        return write_note(
            vault_root, agent, roles,
            path=a["path"],
            frontmatter=a.get("frontmatter") or {},
            body=a.get("body", ""),
            register=a.get("register"),
            overwrite=bool(a.get("overwrite")),
        ).to_dict()
    return _dispatch(run, args, needs_roles=True)


def _handle_edit_metadata(args, **kw) -> str:
    def run(a, vault_root, agent, roles):
        from vault.write import edit_metadata
        return edit_metadata(
            vault_root, agent, roles,
            path=a["path"],
            changes=a.get("changes") or {},
        ).to_dict()
    return _dispatch(run, args, needs_roles=True)


def _handle_delete(args, **kw) -> str:
    def run(a, vault_root, agent, roles):
        from vault.write import delete_note
        return delete_note(vault_root, agent, roles, path=a["path"])
    return _dispatch(run, args, needs_roles=True)


def _handle_scaffold(args, **kw) -> str:
    def run(a, vault_root, agent, roles):
        from vault.scaffold import scaffold_folder
        return scaffold_folder(
            vault_root, agent, roles,
            path=a["path"],
            intent=a.get("intent", ""),
            proposed=a.get("proposed"),
            confirm=bool(a.get("confirm")),
        )
    return _dispatch(run, args, needs_roles=True)


def _handle_edit_config(args, **kw) -> str:
    def run(a, vault_root, agent, roles):
        from vault.scaffold import edit_config
        return edit_config(
            vault_root, agent, roles,
            path=a["path"],
            proposed=a.get("proposed"),
            confirm=bool(a.get("confirm")),
        )
    return _dispatch(run, args, needs_roles=True)


def _handle_index(args, **kw) -> str:
    def run(a, vault_root, agent, roles):
        from vault.generate import regenerate_indexes, write_registry
        from vault.grants import PermissionDenied

        folder = a.get("folder", ".")
        scope_rel = "" if folder in (".", "", "/") else folder.strip("/")
        if not roles.any_grant(agent, scope_rel):
            raise PermissionDenied(
                f"{agent} may not reindex {folder or 'the vault'}: "
                f"holds no grant there"
            )

        out: Dict[str, Any] = {}
        if folder:
            out["indexed"] = regenerate_indexes(
                vault_root, folder if folder != "." else None)
        if a.get("registry_to"):
            reg = a["registry_to"].strip("/")
            if not roles.any_grant(agent, reg):
                raise PermissionDenied(
                    f"{agent} may not write the registry to {reg!r}: "
                    f"holds no grant there"
                )
            out["registry"] = write_registry(vault_root, a["registry_to"])
        return out or {"ok": True}
    return _dispatch(run, args, needs_roles=True)


def _handle_audit(args, **kw) -> str:
    def run(a, vault_root, agent, roles):
        from vault import audit
        entries = audit.read_entries(
            vault_root,
            limit=int(a.get("limit", 100)),
            agent=a.get("agent"),
            action=a.get("action"),
        )
        # read enforcement (D2): an agent sees only entries for paths it
        # can read — the audit trail is a read surface like any other.
        entries = [e for e in entries
                   if roles.allows(agent, "read", e.get("path", ""))]
        return {"entries": entries}
    return _dispatch(run, args, needs_roles=True)


def _handle_search(args, **kw) -> str:
    def run(a, vault_root):
        from vault.grants import load_roles
        from vault.query import search
        agent = a.get("agent") or _resolve_agent(a)
        roles = load_roles(vault_root) if agent else None
        return search(
            vault_root,
            query=a.get("query", ""),
            scope=a.get("scope"),
            fields=a.get("fields"),
            folder=a.get("folder"),
            group_by=a.get("group_by"),
            agent=agent,
            roles=roles,
            limit=int(a.get("limit", 50)),
        )
    return _dispatch(run, args, needs_roles=False)


def _handle_graph(args, **kw) -> str:
    def run(a, vault_root, agent, roles):
        from vault.graph import build_graph
        g = build_graph(vault_root)
        path = a["path"]
        # D2: an agent sees nothing from a note it cannot read — not even
        # the neighbours of one (the centre is supplied by the caller, but
        # the response must not leak anything beyond its own grants).
        if not roles.allows(agent, "read", path):
            return {"center": path, "neighbors": [], "hops": []}
        if a.get("dangling"):
            dangling = [{"from": f, "label": l} for f, l in g.dangling
                        if roles.allows(agent, "read", f)]
            return {"dangling": dangling}
        neighbors = [e for e in g.linked(path, a.get("direction", "both"))
                     if e.get("to") and roles.allows(agent, "read", e["to"])]
        hops = [p for p in g.traverse(path, hops=int(a.get("hops", 1)),
                                      direction=a.get("direction", "both"))
                if roles.allows(agent, "read", p)]
        return {"center": path, "neighbors": neighbors, "hops": hops}
    return _dispatch(run, args, needs_roles=True)


def _derive_issue_key(subject: str, target: str) -> str:
    """Default dedupe key: normalised subject + target."""
    import hashlib
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")[:60] or "issue"
    digest = hashlib.sha256(f"{subject}|{target}".encode()).hexdigest()[:8]
    return f"{slug}|{target}|{digest}"


def _handle_issue(args, **kw) -> str:
    def run(a, vault_root, agent, roles):
        from vault import issues
        from vault.grants import RolesError

        # Raise is the escalation valve: any *registered* agent may raise.
        # Unregistered identities are refused (deny-by-default floor).
        try:
            roles.get(agent)
        except RolesError:
            raise

        results = []
        for item in a["items"]:
            target = item["target"].strip("/")
            key = item.get("key") or _derive_issue_key(item["subject"], target)
            out = issues.create_issue(
                vault_root, agent,
                key=key,
                subject=item["subject"],
                detail=item["detail"],
                target=target,
                priority=item.get("priority", "medium"),
                tags=item.get("tags"),
            )
            results.append(out)
        return {"issues": results}
    return _dispatch(run, args, needs_roles=True)


def _handle_issue_resolve(args, **kw) -> str:
    def run(a, vault_root, agent, roles):
        from vault import issues

        record = issues.read_issue(vault_root, a["key"])
        if record is None:
            return {"ok": False, "error": "not_found", "key": a["key"]}
        target = record.get("target", "")
        # Resolve requires write or meta over the target — you close issues
        # about notes you own. Grant-kind check: write/meta are grant kinds,
        # not operations.
        grants = roles.get(agent)
        if not (grants.matches("write", target) or grants.matches("meta", target)):
            from vault.grants import PermissionDenied
            raise PermissionDenied(
                f"{agent} may not resolve {a['key']!r}: requires 'write' or "
                f"'meta' over its target {target!r}"
            )
        return issues.resolve_issue(
            vault_root, agent, a["key"],
            state=a.get("state", "resolved"),
            reason=a.get("reason"),
        )
    return _dispatch(run, args, needs_roles=True)


def _handle_issue_list(args, **kw) -> str:
    def run(a, vault_root, agent, roles):
        from vault import issues
        from vault.grants import path_matches

        entries = issues.list_issues(
            vault_root,
            state=a.get("state"),
            priority=a.get("priority"),
            tags=a.get("tags"),
            target=a.get("target"),
            raised_by=a.get("raised_by"),
        )
        # Grant intersection at call time: an agent sees only issues whose
        # target it can read. A scope-glob target like "system/**" is visible
        # to anyone whose read grants match that scope.
        visible = [
            e for e in entries
            if roles.allows(agent, "read", e.get("target", ""))
            or _scope_readable(roles, agent, e.get("target", ""))
        ]
        limit = int(a.get("limit", 50))
        return {"issues": visible[:limit], "count": len(visible[:limit])}
    return _dispatch(run, args, needs_roles=True)


def _scope_readable(roles, agent: str, target: str) -> bool:
    """Can ``agent`` read at least one grant scope matching glob ``target``?"""
    from vault.grants import path_matches

    grants = roles.get(agent)
    if "/" not in target or not target.endswith("**"):
        return False
    for scope in grants.globs("read"):
        if path_matches(scope, target) or path_matches(target, scope):
            return True
    return False


def _handle_maintain(args, **kw) -> str:
    def run(a, vault_root, agent, roles):
        from vault.maintain import run_maintenance
        return run_maintenance(
            vault_root, agent, roles,
            mode=a.get("mode", "maintain"),
            distribute_issues=bool(a.get("distribute", True)),
            dry_run=bool(a.get("dry_run", False)),
        )
    return _dispatch(run, args, needs_roles=True)


def _handle_reference(args, **kw) -> str:
    from vault.reference import describe
    return json.dumps(describe(), default=str)


def _available() -> bool:
    try:
        import frontmatter  # noqa: F401
        import yaml  # noqa: F401
    except ImportError:
        return False
    from vault.constants import CONFIG_DIRNAME, CONFIG_FILENAME
    from vault.paths import vault_root_or_none
    root = vault_root_or_none()
    # The engine operates on schema-configured vaults only. A root without
    # .vault/config.yaml is either a v1 vault or not a vault at all —
    # refuse to light up tools against it, or they would happily write
    # generated INDEX/registry files into an unconfigured tree.
    return root is not None and (root / CONFIG_DIRNAME / CONFIG_FILENAME).is_file()


def register(ctx) -> None:
    from vault import schemas

    # The bundled skill: immutable source for the `obsidian-vault` skill
    # (tool routing + cascade + references). Install (scripts/setup.py)
    # composes a profile-tailored copy into each profile's skills/; this
    # registration is the pre-install fallback and the immutable upstream.
    bundled_skill = _PLUGIN_DIR / "skills" / "obsidian-vault"
    if bundled_skill.is_dir():
        ctx.register_skill(name="obsidian-vault", path=str(bundled_skill))

    handlers = {
        "obsidian_context":       (schemas.OBSIDIAN_CONTEXT, _handle_context, "🗂️"),
        "obsidian_write":         (schemas.OBSIDIAN_WRITE, _handle_write, "📝"),
        "obsidian_edit_metadata": (schemas.OBSIDIAN_EDIT_METADATA,
                                   _handle_edit_metadata, "🏷️"),
        "obsidian_delete":        (schemas.OBSIDIAN_DELETE, _handle_delete, "🗑️"),
        "obsidian_scaffold":      (schemas.OBSIDIAN_SCAFFOLD, _handle_scaffold, "🌱"),
        "obsidian_edit_config":   (schemas.OBSIDIAN_EDIT_CONFIG,
                                   _handle_edit_config, "⚙️"),
        "obsidian_index":         (schemas.OBSIDIAN_INDEX, _handle_index, "📑"),
        "obsidian_audit":         (schemas.OBSIDIAN_AUDIT, _handle_audit, "📜"),
        "obsidian_reference":     (schemas.OBSIDIAN_REFERENCE, _handle_reference, "📖"),
        "obsidian_search":        (schemas.OBSIDIAN_SEARCH, _handle_search, "🔎"),
        "obsidian_graph":         (schemas.OBSIDIAN_GRAPH, _handle_graph, "🕸️"),
        "obsidian_issue":         (schemas.OBSIDIAN_ISSUE, _handle_issue, "📌"),
        "obsidian_issue_resolve": (schemas.OBSIDIAN_ISSUE_RESOLVE,
                                   _handle_issue_resolve, "✅"),
        "obsidian_issue_list":    (schemas.OBSIDIAN_ISSUE_LIST,
                                   _handle_issue_list, "🗒️"),
        "obsidian_maintain":      (schemas.OBSIDIAN_MAINTAIN, _handle_maintain, "🧹"),
    }

    for name, (schema, handler, emoji) in handlers.items():
        ctx.register_tool(
            name=name,
            toolset="obsidian_vault",
            schema=schema,
            handler=handler,
            check_fn=_available,
            emoji=emoji,
        )
