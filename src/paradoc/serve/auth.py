"""Auth for paradoc-serve — OIDC bearer-token verification.

Verifies tokens against one of N configured OIDC providers (Authentik
+ Azure AD), upserts the user into the Postgres control plane, and
exposes :class:`User` via the :func:`current_user` FastAPI dependency.

Multi-provider design: configuration is a JSON list of provider blocks
in ``PARADOC_OIDC_PROVIDERS_JSON``. Tokens are routed to the right
provider by ``iss`` claim. Each provider declares its own
``subject_claim`` so we read ``sub`` from Authentik and ``oid`` from
Azure AD — Azure's ``sub`` is per-application pairwise and would give
a different user-handle per registered app, breaking the cross-app
identity contract.

When the JSON env is empty or auth is disabled, :func:`current_user`
returns a synthetic ``local-dev`` user with admin rights. That keeps
local dev and the desktop CLI path completely untouched.

Header-trust auth (``X-Auth-Request-User`` / ``X-User-Id``) was the
previous implementation; it was removed when this OIDC layer landed.
Deployments must now forward an OIDC bearer token from the trusted
IdP set instead of relying on ingress-injected headers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

# FastAPI is a hard requirement for any paradoc.serve usage. The
# Request type lands in module globals so FastAPI's dep-resolver can
# evaluate the `request: Request` string annotations on current_user /
# require_admin (forced into strings by ``from __future__ import
# annotations``).
from fastapi import Request

logger = logging.getLogger(__name__)


# ── OIDC verification ────────────────────────────────────────────────


# Discovery + JWKS cache TTL. Authentik / Azure rotate keys infrequently;
# 10 minutes is a sweet spot between freshness and request volume.
_DISCOVERY_TTL = 600
_JWKS_TTL = 600

_CLAIM_GROUPS = "groups"


@dataclass(frozen=True)
class ProviderConfig:
    """One OIDC provider in the trust set.

    ``subject_claim`` decides which token claim becomes the durable
    cross-app handle for this provider. Authentik issues a stable
    global ``sub``; Azure AD's ``sub`` is per-application pairwise,
    so we read ``oid`` (tenant-stable across apps) instead.
    """

    name: str
    issuer: str
    client_id: str
    audience: str
    subject_claim: str = "sub"


@dataclass(frozen=True)
class AuthConfig:
    """Paradoc's OIDC settings.

    ``enabled`` mirrors adapy's gate — when False, :func:`current_user`
    returns a synthetic local-dev principal so dev + desktop paths
    stay untouched.

    ``admin_group`` matches token's ``groups`` claim by exact string;
    use a group name for Authentik, a group object id for Azure AD.
    """

    enabled: bool
    providers: tuple[ProviderConfig, ...] = field(default_factory=tuple)
    admin_group: str = ""


def load_config_from_env() -> AuthConfig:
    """Build :class:`AuthConfig` from environment variables.

    Env vars:
      - ``PARADOC_AUTH_ENABLED`` (default ``false``)
      - ``PARADOC_OIDC_PROVIDERS_JSON`` — JSON list of provider blocks,
        each with at minimum ``name``, ``issuer``, ``client_id``;
        ``audience`` defaults to ``client_id`` if absent;
        ``subject_claim`` defaults to ``"sub"``.
      - ``PARADOC_AUTH_ADMIN_GROUP`` — group name (Authentik) or object
        id (Azure AD) granting admin role.
    """
    enabled_raw = os.environ.get("PARADOC_AUTH_ENABLED", "false").strip().lower()
    enabled = enabled_raw in ("1", "true", "yes", "on")
    providers_raw = os.environ.get("PARADOC_OIDC_PROVIDERS_JSON", "").strip()
    providers: tuple[ProviderConfig, ...] = ()
    if providers_raw:
        try:
            data = json.loads(providers_raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"PARADOC_OIDC_PROVIDERS_JSON is not valid JSON: {exc}"
            ) from exc
        if not isinstance(data, list):
            raise RuntimeError(
                "PARADOC_OIDC_PROVIDERS_JSON must be a JSON array of provider blocks"
            )
        parsed: list[ProviderConfig] = []
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                raise RuntimeError(
                    f"PARADOC_OIDC_PROVIDERS_JSON[{i}] is not an object"
                )
            try:
                client_id = str(item["client_id"])
                parsed.append(
                    ProviderConfig(
                        name=str(item["name"]),
                        issuer=str(item["issuer"]).rstrip("/"),
                        client_id=client_id,
                        audience=str(item.get("audience") or client_id),
                        subject_claim=str(item.get("subject_claim") or "sub"),
                    )
                )
            except KeyError as exc:
                raise RuntimeError(
                    f"PARADOC_OIDC_PROVIDERS_JSON[{i}] missing required field: {exc}"
                ) from exc
        providers = tuple(parsed)
    admin_group = os.environ.get("PARADOC_AUTH_ADMIN_GROUP", "").strip()
    if enabled and not providers:
        raise RuntimeError(
            "PARADOC_AUTH_ENABLED=true but PARADOC_OIDC_PROVIDERS_JSON is empty"
        )
    return AuthConfig(enabled=enabled, providers=providers, admin_group=admin_group)


@dataclass(frozen=True)
class User:
    """Authenticated principal — what the rest of the app passes around.

    ``id`` is paradoc's internal UUID (string form). ``iss`` and
    ``subject`` are the cross-app OIDC handle — same tuple identifies
    this user in adapy / shelf when integrations cross app boundaries.
    """

    id: str
    iss: str
    subject: str
    email: str
    display_name: str
    groups: frozenset[str]
    is_admin: bool

    @classmethod
    def local_dev(cls) -> "User":
        return cls(
            id="00000000-0000-0000-0000-000000000000",
            iss="local-dev",
            subject="local-dev",
            email="local@dev.invalid",
            display_name="Local Dev",
            groups=frozenset(),
            is_admin=True,
        )


class TokenError(Exception):
    """Raised when a bearer token fails verification. Translated to
    HTTP 401 by :func:`current_user` so the abc layer stays free of
    FastAPI imports.
    """


class _JWKSVerifier:
    """Per-provider JWKS verifier with discovery+key caching.

    One instance per :class:`ProviderConfig`. Held on the app's
    multi-provider verifier and closed on shutdown. Concurrency-safe:
    a single asyncio.Lock guards discovery + JWKS refresh, so a
    rotation event doesn't fan out N parallel JWKS fetches.
    """

    def __init__(self, provider: ProviderConfig) -> None:
        import httpx  # local import — auth is optional in dev

        self._provider = provider
        self._http = httpx.AsyncClient(timeout=10.0)
        self._discovery: Optional[dict[str, Any]] = None
        self._discovery_at = 0.0
        self._jwks_client: Any = None  # PyJWKClient
        self._jwks_at = 0.0
        self._lock = asyncio.Lock()

    @property
    def provider(self) -> ProviderConfig:
        return self._provider

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _discovery_doc(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._discovery and now - self._discovery_at < _DISCOVERY_TTL:
            return self._discovery
        url = f"{self._provider.issuer}/.well-known/openid-configuration"
        r = await self._http.get(url)
        r.raise_for_status()
        self._discovery = r.json()
        self._discovery_at = now
        return self._discovery

    async def _jwks(self, force_refresh: bool = False):
        from jwt import PyJWKClient

        now = time.monotonic()
        if (
            not force_refresh
            and self._jwks_client is not None
            and now - self._jwks_at < _JWKS_TTL
        ):
            return self._jwks_client
        async with self._lock:
            if (
                not force_refresh
                and self._jwks_client is not None
                and time.monotonic() - self._jwks_at < _JWKS_TTL
            ):
                return self._jwks_client
            doc = await self._discovery_doc()
            jwks_uri = doc["jwks_uri"]
            self._jwks_client = PyJWKClient(jwks_uri)
            self._jwks_at = time.monotonic()
            return self._jwks_client

    async def verify(self, token: str) -> dict[str, Any]:
        """Validate signature + iss/aud/exp; return the claims dict."""
        import jwt

        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise TokenError(f"malformed token: {exc}") from exc

        signing_key = None
        for force in (False, True):
            jwks_client = await self._jwks(force_refresh=force)
            try:
                signing_key = jwks_client.get_signing_key_from_jwt(token).key
            except jwt.PyJWKClientError:
                if not force:
                    continue
                raise TokenError("signing key not found in JWKS")
            break
        assert signing_key is not None

        # Accept the issuer with or without a trailing slash. The config
        # is normalized (stripped) when loaded, but Authentik (and some
        # other IdPs) emit the token's `iss` claim *with* the slash, so
        # passing a single string to pyjwt does exact-match and fails
        # "issuer mismatch" even when the strings are equivalent.
        accepted_iss = [self._provider.issuer, self._provider.issuer + "/"]
        try:
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=[unverified_header.get("alg", "RS256")],
                audience=self._provider.audience or self._provider.client_id,
                issuer=accepted_iss,
                options={"require": ["exp", "iat", "iss", "sub"]},
            )
        except jwt.ExpiredSignatureError:
            raise TokenError("token expired")
        except jwt.InvalidAudienceError:
            raise TokenError("audience mismatch")
        except jwt.InvalidIssuerError:
            raise TokenError("issuer mismatch")
        except jwt.InvalidTokenError as exc:
            raise TokenError(f"invalid token: {exc}") from exc
        return claims


class _MultiProviderVerifier:
    """Routes incoming tokens to the right per-provider verifier by ``iss``."""

    def __init__(self, config: AuthConfig) -> None:
        self._config = config
        # Normalize the key the same way the token's iss claim is
        # normalized below — Authentik emits the issuer with a trailing
        # slash; config files often carry it the same way. Without
        # rstrip on the key side, every token gets rejected as
        # "issuer not trusted" even though the strings match.
        self._by_issuer: dict[str, _JWKSVerifier] = {
            p.issuer.rstrip("/"): _JWKSVerifier(p) for p in config.providers
        }

    async def aclose(self) -> None:
        for v in self._by_issuer.values():
            await v.aclose()

    async def verify(self, token: str) -> tuple[dict[str, Any], ProviderConfig]:
        """Pick the provider matching the token's ``iss`` and verify.

        Peeking the unverified ``iss`` is safe — the verifier then
        signature-checks the token against that provider's JWKS, so a
        forged ``iss`` would fail signature verification.
        """
        import jwt

        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
        except jwt.InvalidTokenError as exc:
            raise TokenError(f"malformed token: {exc}") from exc
        iss = str(unverified.get("iss", "")).rstrip("/")
        verifier = self._by_issuer.get(iss)
        if verifier is None:
            raise TokenError(f"issuer not trusted: {iss}")
        claims = await verifier.verify(token)
        return claims, verifier.provider


# ── FastAPI integration ──────────────────────────────────────────────


def install(app, config: Optional[AuthConfig] = None) -> None:
    """Attach the verifier + config to FastAPI app state.

    Called from :func:`create_app`. When auth is disabled or no
    providers configured, the verifier stays None — :func:`current_user`
    short-circuits to the synthetic local-dev user.
    """
    cfg = config if config is not None else load_config_from_env()
    app.state.auth_config = cfg
    if cfg.enabled and cfg.providers:
        app.state.auth_verifier = _MultiProviderVerifier(cfg)
        names = ", ".join(p.name for p in cfg.providers)
        logger.info("auth: OIDC enabled with providers: %s", names)
    else:
        app.state.auth_verifier = None
        if cfg.enabled:
            logger.warning("auth: enabled but no providers — disabling")
        else:
            logger.info("auth: disabled (PARADOC_AUTH_ENABLED=false)")


async def aclose(app) -> None:
    verifier = getattr(app.state, "auth_verifier", None)
    if verifier is not None:
        await verifier.aclose()


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise TokenError("missing bearer token")
    return token


def _claims_to_partial_user(
    claims: dict[str, Any], provider: ProviderConfig, admin_group: str
) -> tuple[str, str, str, frozenset[str], bool]:
    """Pull display fields + admin flag from the verified claims.

    Returns ``(subject, email, display_name, groups, is_admin)``.
    Subject uses ``provider.subject_claim`` (``oid`` for AAD, ``sub``
    for Authentik) — this is the durable cross-app handle.
    """
    subject = str(claims.get(provider.subject_claim) or claims["sub"])
    email = str(claims.get("email") or claims.get("preferred_username") or "")
    display_name = str(
        claims.get("name")
        or claims.get("preferred_username")
        or claims.get("email")
        or subject
    )
    raw_groups = claims.get(_CLAIM_GROUPS) or []
    if not isinstance(raw_groups, (list, tuple, set, frozenset)):
        raw_groups = [raw_groups]
    groups = frozenset(str(g) for g in raw_groups)
    is_admin = bool(admin_group) and admin_group in groups
    return subject, email, display_name, groups, is_admin


async def current_user(request: Request) -> User:
    """FastAPI dep: returns the verified User or raises 401.

    When auth is disabled, returns the synthetic local-dev user with
    admin rights. When enabled, verifies the bearer token, upserts
    the user into the Postgres control plane, and returns a User
    carrying paradoc's internal UUID alongside the cross-app handle.
    """
    from fastapi import HTTPException

    config: AuthConfig = request.app.state.auth_config
    if not config.enabled:
        # Local-dev mode: upsert the synthetic user into the control
        # plane so DB-backed admin operations (auto-add-as-owner,
        # member lookups) work. Without this any
        # ``project_members(user_id=local-dev-uuid)`` insert fails the
        # FK to ``users``. Skipped when no pool is configured.
        pool = getattr(request.app.state, "db_pool", None)
        if pool is not None:
            from . import db as db_module

            await pool.execute(
                """
                INSERT INTO users (id, oidc_iss, oidc_sub, display_name, email)
                VALUES ($1::uuid, $2, $3, $4, $5)
                ON CONFLICT (oidc_iss, oidc_sub) DO UPDATE SET
                    last_seen_at = NOW()
                """,
                "00000000-0000-0000-0000-000000000000",
                "local-dev",
                "local-dev",
                "Local Dev",
                "local@dev.invalid",
            )
        return User.local_dev()
    try:
        token = _bearer_token(request)
        verifier: _MultiProviderVerifier = request.app.state.auth_verifier
        claims, provider = await verifier.verify(token)
    except TokenError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject, email, display_name, groups, is_admin = _claims_to_partial_user(
        claims, provider, config.admin_group
    )

    # Upsert into the control plane. If no DB pool, we still return a
    # User but with id == subject — shared-only mode where nothing
    # queries the DB anyway.
    pool = getattr(request.app.state, "db_pool", None)
    if pool is not None:
        from . import db as db_module

        user_id = await db_module.upsert_user(
            pool,
            oidc_iss=provider.issuer,
            oidc_sub=subject,
            display_name=display_name,
            email=email,
        )
    else:
        user_id = subject

    return User(
        id=user_id,
        iss=provider.issuer,
        subject=subject,
        email=email,
        display_name=display_name,
        groups=groups,
        is_admin=is_admin,
    )


async def require_admin(request: Request) -> User:
    """Compose with :func:`current_user` for admin-only routes."""
    from fastapi import HTTPException

    user = await current_user(request)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="admin only")
    return user
