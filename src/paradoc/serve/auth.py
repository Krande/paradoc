"""Auth seam for the REST server.

The default policy trusts ingress headers (typical for k8s deployments
with oauth2-proxy / istio-style auth at the cluster edge). Real auth
plugs in by implementing `AuthPolicy` and passing it into `create_app`.

This is intentionally a minimal interface — the REST server is read-
only over already-built bundles, so auth choices reduce to:
  - is this request allowed to see this `doc_id`?
  - what user identifier do we log for it?
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class AuthDecision:
    """Either an allow with optional principal, or a deny with status/reason."""

    def __init__(
        self,
        *,
        allowed: bool,
        principal: Optional[str] = None,
        status_code: int = 403,
        reason: str = "forbidden",
    ) -> None:
        self.allowed = allowed
        self.principal = principal
        self.status_code = status_code
        self.reason = reason

    @classmethod
    def allow(cls, principal: Optional[str] = None) -> "AuthDecision":
        return cls(allowed=True, principal=principal)

    @classmethod
    def deny(cls, *, status_code: int = 403, reason: str = "forbidden") -> "AuthDecision":
        return cls(allowed=False, status_code=status_code, reason=reason)


class AuthPolicy(ABC):
    """Decide whether a request is allowed and who is making it."""

    @abstractmethod
    def authorize(self, *, doc_id: str, request: Any) -> AuthDecision:
        ...


class IngressTrustPolicy(AuthPolicy):
    """Trust headers set by an upstream ingress / proxy.

    Looks for `X-Auth-Request-User` (oauth2-proxy default) or `X-User-Id`.
    If neither is present, allows anonymous access — fine for an
    intra-cluster deployment behind an authenticating ingress, but you
    almost certainly want a stricter policy for a public-facing
    deployment.
    """

    def __init__(self, *, require_principal: bool = False) -> None:
        self.require_principal = require_principal

    def authorize(self, *, doc_id: str, request: Any) -> AuthDecision:
        headers = getattr(request, "headers", None)
        if headers is None:
            return (
                AuthDecision.deny(reason="no headers on request")
                if self.require_principal
                else AuthDecision.allow()
            )
        principal = headers.get("x-auth-request-user") or headers.get("x-user-id")
        if not principal and self.require_principal:
            return AuthDecision.deny(status_code=401, reason="unauthenticated")
        return AuthDecision.allow(principal=principal or None)
