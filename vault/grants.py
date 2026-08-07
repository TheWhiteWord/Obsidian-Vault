"""Grant resolution and enforcement — see docs/concepts/grants.md.

**Mechanism only.** The grant *kinds* are universal; which paths each agent
holds is policy read from ``.vault/roles.yaml`` (principle 7).

Deny by default: an operation with no matching grant is refused. There is no
"warn and proceed" path — that would make the boundary advisory, which is
exactly what the plugin exists to replace.
"""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from .constants import CONFIG_DIRNAME, ROLES_FILENAME
from .ownership import owner_of
from .paths import VaultPathError

logger = logging.getLogger(__name__)


class PermissionDenied(Exception):
    """Raised when an agent attempts an operation it holds no grant for."""


class RolesError(Exception):
    """Raised when roles.yaml is missing, malformed, or self-contradictory."""


#: The five grant kinds. Universal — a vault may not invent new ones, because
#: each is enforced by specific code below.
GRANT_KINDS = ("read", "write", "append", "meta", "config")

#: What each operation requires. Single source of truth for the mapping from
#: "what the agent is trying to do" to "which grant permits it".
OPERATION_GRANTS: Dict[str, str] = {
    "read":        "read",
    "context":     "read",
    "search":      "read",
    "create":      "write",     # also satisfiable by `append` — see below
    "edit":        "write",
    "delete":      "write",
    "move":        "write",
    "edit_meta":   "meta",      # frontmatter / links / tags only
    "edit_config": "config",    # vocabulary sections only
}

#: Operations an `append` grant permits. Creating is allowed; touching
#: anything that already exists is not.
APPEND_ALLOWS: Set[str] = {"create"}


def _normalise_patterns(value: Any, agent: str, kind: str) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        raise RolesError(
            f"agent {agent!r}, grant {kind!r}: expected a list of path globs, "
            f"got {type(value).__name__}"
        )
    return [str(p).strip().strip("/") for p in value if str(p).strip()]


@dataclass
class Grants:
    """One agent's grants: grant kind → list of path globs."""

    agent: str
    patterns: Dict[str, List[str]] = dc_field(default_factory=dict)

    def globs(self, kind: str) -> List[str]:
        return self.patterns.get(kind, [])

    def matches(self, kind: str, rel_path: str) -> bool:
        """Does this agent hold ``kind`` over ``rel_path``?

        ``**`` matches across separators; ``*`` does not. So a pattern like
        ``*/FOLDER/**`` means "that folder directly under any top-level tree"
        rather than "anything anywhere with that name".
        """
        target = rel_path.strip("/")
        for pattern in self.globs(kind):
            if path_matches(pattern, target):
                return True
        return False

    def readable_scopes(self) -> List[str]:
        return self.globs("read")


def path_matches(pattern: str, path: str) -> bool:
    """Glob match where ``**`` crosses separators and ``*`` does not.

    The single glob language for the engine: grant patterns (this module)
    and search ``scope`` patterns (``vault/query.py``) mean the same thing.

    Matching is **case-insensitive** (casefold): folder casing is cosmetic,
    so a grant written for ``work/creative/**`` still covers a folder the
    user renamed to ``Creative`` — and ``safe_join`` resolves writes to the
    real on-disk name.

    ``pattern`` is a single glob with no negation. Search scopes compose
    several of them — positives plus ``!``-prefixed exclusions — via
    :func:`scope_matches`; grants are positive-only by design, so grant
    callers never pass a ``!`` pattern here.
    """
    if pattern in ("**", "*"):
        return True

    # A trailing /** should also match the folder itself.
    if pattern.endswith("/**") and path == pattern[:-3]:
        return True

    p_parts = pattern.split("/")
    t_parts = path.split("/")
    return _match_parts(p_parts, t_parts)


def scope_matches(patterns: Iterable[str], path: str) -> bool:
    """Match ``path`` against a list of globs that may include negations.

    The search-scope language (§2.2.1, D9): a ``!``-prefixed entry is an
    *exclusion*, everything else is an *inclusion*. A path is in scope
    when at least one inclusion matches **and** no exclusion matches.
    The scope is always a list, so ``[]`` matches nothing and a list of
    only exclusions matches nothing — absence of an inclusion never
    widens a query.

    Deny-by-default is untouched: grants are resolved with
    :func:`path_matches` alone (positive patterns only), and scope
    negation is applied *after* the read-grant intersection, so a
    ``!`` pattern can never grant visibility.
    """
    includes: List[str] = []
    excludes: List[str] = []
    for pattern in patterns:
        (excludes if pattern.startswith("!") else includes).append(
            pattern[1:] if pattern.startswith("!") else pattern
        )
    if not includes:
        return False
    if not any(path_matches(p, path) for p in includes):
        return False
    if any(path_matches(p, path) for p in excludes):
        return False
    return True


def _match_parts(pattern: List[str], target: List[str]) -> bool:
    if not pattern:
        return not target
    head, rest = pattern[0], pattern[1:]

    if head == "**":
        if not rest:
            return True
        for i in range(len(target) + 1):
            if _match_parts(rest, target[i:]):
                return True
        return False

    if not target:
        return False
    if not fnmatch.fnmatchcase(target[0].casefold(), head.casefold()):
        return False
    return _match_parts(rest, target[1:])


@dataclass
class RoleRegistry:
    """All agents' grants, loaded from ``.vault/roles.yaml``."""

    agents: Dict[str, Grants] = dc_field(default_factory=dict)
    source: Optional[Path] = None

    def get(self, agent: str) -> Grants:
        if agent not in self.agents:
            raise RolesError(
                f"unknown agent {agent!r}; known: {sorted(self.agents) or '(none)'}"
            )
        return self.agents[agent]

    def check(self, agent: str, operation: str, rel_path: str) -> None:
        """Raise :class:`PermissionDenied` unless the operation is permitted.

        The single enforcement point. Every write path in the plugin calls
        this before touching the filesystem.
        """
        if operation not in OPERATION_GRANTS:
            raise RolesError(f"unknown operation {operation!r}")

        grants = self.get(agent)
        required = OPERATION_GRANTS[operation]

        # P7 shadowing: inside an owned scope,
        # write/config/append resolve only for the derived owner. A
        # capability glob held by a non-owner grants nothing there. read
        # and meta stay generous (the parent owner's meta backstop, the
        # manager's meta over ** — untouched).
        if required in ("write", "config") or operation in APPEND_ALLOWS:
            owner = owner_of(self._write_globs, rel_path)
            if owner is not None and owner != agent:
                raise PermissionDenied(
                    f"{agent} may not {operation} at {rel_path!r}: "
                    f"the scope is owned by {owner} (write/config resolve "
                    f"only for the derived owner)"
                )

        if grants.matches(required, rel_path):
            return

        # `append` is a narrower substitute for `write` on creation only.
        if operation in APPEND_ALLOWS and grants.matches("append", rel_path):
            return

        held = sorted(k for k in GRANT_KINDS if grants.matches(k, rel_path))
        raise PermissionDenied(
            f"{agent} may not {operation} at {rel_path!r}: "
            f"requires '{required}' grant, holds {held or 'none'} here"
        )

    def allows(self, agent: str, operation: str, rel_path: str) -> bool:
        """Non-raising variant, for filtering."""
        try:
            self.check(agent, operation, rel_path)
            return True
        except (PermissionDenied, RolesError):
            return False

    def filter_readable(self, agent: str, paths: List[str]) -> List[str]:
        """Intersect a result set with the agent's read grants (§2.2.1).

        Silent filtering, not an error — an agent may query ``**`` and simply
        receive nothing from where it cannot read.
        """
        grants = self.get(agent)
        return [p for p in paths if grants.matches("read", p)]

    @property
    def _write_globs(self) -> Dict[str, List[str]]:
        """Agent → write globs: the ownership resolver's input.

        Only write globs can establish ownership. Computed on
        demand — vaults are small and this is a per-call scan.
        """
        return {name: g.globs("write") for name, g in self.agents.items()}

    def any_grant(self, agent: str, rel_path: str) -> bool:
        """True if the agent holds *any* grant kind over ``rel_path``.

        Used for gating derived-bookkeeping operations (e.g. INDEX
        regeneration): the agent needs some standing in the folder, but
        the operation is harmless enough that any grant suffices.
        """
        grants = self.get(agent)
        return any(grants.matches(kind, rel_path) for kind in GRANT_KINDS)


def load_roles(vault_root: Path) -> RoleRegistry:
    """Load ``.vault/roles.yaml``.

    A vault with no roles file has no agents, so every operation is denied.
    That is the correct default for a permission system: absence of policy
    means absence of permission, never permission by omission.
    """
    import yaml

    root = Path(vault_root).resolve()
    path = root / CONFIG_DIRNAME / ROLES_FILENAME

    if not path.exists():
        logger.warning("no roles.yaml at %s — all operations denied", path)
        return RoleRegistry(agents={}, source=None)

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise RolesError(f"{path}: invalid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise RolesError(f"{path}: expected a mapping at top level")

    section = raw.get("agents")
    if section is None:
        raise RolesError(f"{path}: missing 'agents:' section")
    if not isinstance(section, dict):
        raise RolesError(f"{path}: 'agents:' must be a mapping of name → grants")

    agents: Dict[str, Grants] = {}
    for name, spec in section.items():
        if not isinstance(spec, dict):
            raise RolesError(f"{path}: agent {name!r} must be a mapping of grants")

        unknown = set(spec) - set(GRANT_KINDS)
        if unknown:
            raise RolesError(
                f"{path}: agent {name!r} has unknown grant kind(s) "
                f"{sorted(unknown)}; valid: {list(GRANT_KINDS)}"
            )

        agents[str(name)] = Grants(
            agent=str(name),
            patterns={
                kind: _normalise_patterns(spec.get(kind), str(name), kind)
                for kind in GRANT_KINDS
                if spec.get(kind)
            },
        )

    return RoleRegistry(agents=agents, source=path)
