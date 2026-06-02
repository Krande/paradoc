"""Scope authorization + URL parsing for paradoc-serve.

The :class:`Scope` value type itself lives in
:mod:`paradoc.docstore.scope` (fastapi-free, so the docstore layer can
depend on it); it is re-exported here for convenience. This module adds
the serve-layer concerns that the docstore does not need: parsing a URL
scope segment, slug→uuid resolution against the DB, and the
authorization predicate.

The FastAPI dependency that wires these into routes (`scope_from_path`)
lives in the app factory (:mod:`paradoc.serve.app`), where the hard
fastapi import belongs — keeping this module importable without the
serve extras.

URL convention for routes that operate on a scope:

    /api/scopes/{scope}/...   where scope ∈ {
        "shared",
        "user:me",
        "project:<uuid-or-slug>",
    }

The path parser does **not** allow naming another user explicitly —
that's reserved for the (future) cross-tenant admin endpoints, which
audit separately.
"""

from __future__ import annotations

import uuid as _uuid
from typing import TYPE_CHECKING

from ..docstore.scope import Scope, ScopeKind

if TYPE_CHECKING:
    from .auth import User

__all__ = [
    "Scope",
    "ScopeKind",
    "ScopeParseError",
    "parse_scope",
    "resolve_project_slug",
    "can_access",
]


class ScopeParseError(ValueError):
    """Raised when a scope URL segment is malformed. Translated to HTTP 400
    by the FastAPI dep that consumes :func:`parse_scope`."""


def parse_scope(raw: str, user: "User") -> Scope:
    """Parse a URL scope segment into a :class:`Scope`.

    Accepted forms:
      * ``shared``
      * ``user:me``   — resolves to ``user:<user.id>`` server-side
      * ``project:<id-or-slug>`` — id can be UUID or slug;
        slug→UUID resolution happens later, against the DB.

    Naming another user explicitly (``user:<other-id>``) is rejected
    here — admins use cross-tenant endpoints instead.
    """
    if raw == "shared":
        return Scope.shared()
    if raw == "user:me":
        return Scope.user(user.id)
    if raw.startswith("user:"):
        raise ScopeParseError("use 'user:me' for personal scope")
    if raw.startswith("project:"):
        pid = raw[len("project:") :].strip()
        if not pid:
            raise ScopeParseError("missing project id")
        return Scope.project(pid)
    raise ScopeParseError(f"invalid scope {raw!r}")


async def resolve_project_slug(pool, scope: Scope) -> Scope:
    """Translate ``project:<slug>`` to ``project:<uuid>`` against the DB.

    UUID-shaped scope ids pass through unchanged. Non-UUID ids are looked
    up against ``projects.slug``. Without a DB pool, slug lookup is
    impossible and the original scope is returned — :func:`can_access`
    will then reject it categorically.
    """
    if scope.kind != "project" or scope.id is None or pool is None:
        return scope
    try:
        _uuid.UUID(scope.id)
        return scope
    except (ValueError, AttributeError, TypeError):
        pass
    from . import db as db_module

    resolved = await db_module.project_id_from_slug(pool, scope.id)
    if resolved is None:
        # Don't leak project existence: signal forbidden, not 404.
        # Caller (the FastAPI dep) translates this into HTTP 403.
        raise PermissionError("forbidden")
    return Scope.project(resolved)


async def can_access(user: "User", scope: Scope, db_pool=None) -> bool:
    """Authorization predicate.

    * ``shared`` — any authenticated user (read).
    * ``user``  — the owning user only (``scope.id == user.id``).
    * ``project`` — members listed in ``project_members``. Requires a
      DB pool; without one (shared-only deployments) project scopes
      are categorically inaccessible.

    Admin role does **not** grant cross-tenant access automatically —
    that's an explicit, audited admin endpoint (future).
    """
    if scope.kind == "shared":
        return True
    if scope.kind == "user":
        return scope.id == user.id
    if scope.kind == "project":
        if db_pool is None:
            return False
        from . import db as db_module

        return await db_module.is_project_member(db_pool, project_id=scope.id or "", user_id=user.id)
    return False
