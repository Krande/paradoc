"""Storage scope value type.

Three tiers, each mapped to a stable URL/storage prefix:

* ``shared``                — any authenticated user can read; admin
  writes (admin role checked at the route level via :func:`require_admin`).
* ``projects/<project_id>`` — visible to members of the project.
* ``users/<user_id>``       — owner-only.

This is the low-level home of the :class:`Scope` value type and its
prefix mapping, deliberately free of FastAPI / auth / DB imports so the
docstore layer can take a scope per call without dragging the serve
extras in. The URL-segment parser and the authorization predicate live
in :mod:`paradoc.serve.scope`; the FastAPI dependency that wires them
into routes lives in the app factory — both up in the serve layer, where
the web/auth dependencies belong.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

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
