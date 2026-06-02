"""Storage scopes for paradoc-serve.

Three tiers, each mapped to a stable URL/storage prefix:

* ``shared``                — any authenticated user can read; admin
  writes (admin role checked at the route level via :func:`require_admin`).
* ``projects/<project_id>`` — visible to members of the project.
* ``users/<user_id>``       — owner-only.

Derived blobs inherit their source's scope. The DocStore layer takes a
:class:`Scope` per call and builds the on-bucket prefix; this module
owns only the scope→prefix mapping, the URL-segment parser, and the
authorization predicate. DB queries live in :mod:`db.py`.

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
from dataclasses import dataclass
from typing import Literal, Optional

# Request must be resolvable as a module-global so FastAPI's
# get_type_hints() can evaluate the string-form annotations on the
# inner _dep below (forced into strings by ``from __future__ import
# annotations``).
from fastapi import Request

from .auth import User

ScopeKind = Literal["shared", "project", "user"]


@dataclass(frozen=True)
class Scope:
    kind: ScopeKind
    # project_id (uuid string) for ``project``, user_id (uuid string) for
    # ``user``, None for ``shared``. Stored as a plain string so it
    # round-trips cleanly through URL paths regardless of source.
    id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.kind == "shared":
            if self.id is not None:
                raise ValueError("shared scope has no id")
        else:
            if not self.id:
                raise ValueError(f"{self.kind} scope requires an id")

    def prefix(self) -> str:
        """Bucket-relative prefix this scope occupies. No leading slash."""
        if self.kind == "shared":
            return "shared"
        if self.kind == "project":
            return f"projects/{self.id}"
        if self.kind == "user":
            return f"users/{self.id}"
        raise AssertionError(f"unknown scope kind {self.kind!r}")

    @classmethod
    def shared(cls) -> "Scope":
        return cls(kind="shared")

    @classmethod
    def project(cls, project_id: str) -> "Scope":
        return cls(kind="project", id=project_id)

    @classmethod
    def user(cls, user_id: str) -> "Scope":
        return cls(kind="user", id=user_id)


class ScopeParseError(ValueError):
    """Raised when a scope URL segment is malformed. Translated to HTTP 400
    by the FastAPI dep that consumes :func:`parse_scope`."""


def parse_scope(raw: str, user: User) -> Scope:
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


async def can_access(user: User, scope: Scope, db_pool=None) -> bool:
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


# ── FastAPI dependency helper ────────────────────────────────────────


def scope_from_path():
    """Build a FastAPI dependency that resolves the ``{scope}`` path
    segment into a :class:`Scope`, slug-resolves it, and enforces
    :func:`can_access`. Routes hang off this dep:

        @app.get("/api/scopes/{scope}/things")
        async def list_things(s: Scope = Depends(scope_from_path())):
            ...

    The factory shape mirrors how FastAPI prefers dep wiring — the
    returned function reads the path parameter ``scope`` and the
    current user / request via FastAPI's own injection.
    """
    from fastapi import Depends, HTTPException

    from . import auth as auth_module

    async def _dep(
        scope: str,
        request: Request,
        user: User = Depends(auth_module.current_user),
    ) -> Scope:
        try:
            s = parse_scope(scope, user)
        except ScopeParseError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        pool = getattr(request.app.state, "db_pool", None)
        try:
            s = await resolve_project_slug(pool, s)
        except PermissionError:
            raise HTTPException(status_code=403, detail="forbidden")
        if not await can_access(user, s, pool):
            raise HTTPException(status_code=403, detail="forbidden")
        return s

    return _dep
