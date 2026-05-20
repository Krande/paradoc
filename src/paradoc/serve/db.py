"""Postgres control plane for paradoc-serve.

Optional. When ``PARADOC_DATABASE_URL`` is empty the pool stays ``None``
and the API serves in shared-only mode: every authenticated user lands
in the same shared bundle space, no projects, no admin panel. This
keeps small deployments runnable without a Postgres dependency.

Migrations are bundled SQL files under ``migrations/`` and applied at
boot inside an advisory lock so a multi-replica rollout doesn't race.
A row in ``schema_version`` records each applied file by stem name.

Bundle content (tables, plots, 3d assets) remains in per-bundle sqlite
files — see ``paradoc/db/manager.py``. The Postgres pool here only
holds users, projects, and project memberships.
"""

from __future__ import annotations

import asyncio
import importlib.resources
import logging
from dataclasses import dataclass
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

# Postgres advisory-lock id for the migration runner. Distinct from
# adapy's so the two systems can share a Postgres server without
# colliding. asyncpg / PG treat advisory keys as int8 (signed 64-bit).
_MIGRATION_LOCK_ID = 0x0DAA0001_DAA00001


@dataclass(frozen=True)
class Project:
    id: str
    slug: str
    name: str
    shelf_base_url: Optional[str]
    role: str  # caller's role within this project


async def init_pool(database_url: str) -> Optional[asyncpg.Pool]:
    """Build a connection pool and apply pending migrations.

    Returns ``None`` when ``database_url`` is empty so callers can
    branch into shared-only mode without a try/except.

    Retries connection failures with exponential backoff. The pod can
    come up before kube-dns or before Postgres has finished accepting
    connections; a one-shot init that gives up on the first
    ``socket.gaierror`` would leave paradoc-serve permanently in
    shared-only mode until someone rolled the pod. Total budget ~60s.
    """
    if not database_url:
        logger.info("db: PARADOC_DATABASE_URL not set — running in shared-only mode")
        return None
    last_exc: Optional[Exception] = None
    delay = 1.0
    deadline = 60.0
    waited = 0.0
    while True:
        try:
            pool = await asyncpg.create_pool(
                dsn=database_url,
                min_size=1,
                max_size=10,
                max_inactive_connection_lifetime=600.0,
            )
            break
        except (OSError, asyncpg.exceptions.PostgresError) as exc:
            last_exc = exc
            if waited >= deadline:
                logger.error(
                    "db: pool init still failing after %.0fs — giving up: %s",
                    waited, exc,
                )
                raise
            logger.warning(
                "db: pool init failed (%s); retry in %.1fs (waited %.1fs/%.0fs)",
                exc, delay, waited, deadline,
            )
            await asyncio.sleep(delay)
            waited += delay
            delay = min(delay * 1.6, 8.0)
    try:
        await _apply_migrations(pool)
    except Exception:
        await pool.close()
        raise
    logger.info("db: pool ready, migrations up-to-date")
    return pool


async def close_pool(pool: Optional[asyncpg.Pool]) -> None:
    if pool is not None:
        await pool.close()


async def _apply_migrations(pool: asyncpg.Pool) -> None:
    """Run any unapplied migrations under a Postgres advisory lock.

    The lock is held only during apply; competing replicas wait, then
    discover the migrations are already applied and become a no-op.
    """
    files = sorted(
        p
        for p in importlib.resources.files("paradoc.serve.migrations").iterdir()
        if p.name.endswith(".sql")
    )

    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_advisory_lock($1)", _MIGRATION_LOCK_ID)
        try:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version    TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            applied = {
                r["version"]
                for r in await conn.fetch("SELECT version FROM schema_version")
            }
            for path in files:
                version = path.stem
                if version in applied:
                    continue
                logger.info("db: applying migration %s", version)
                sql = path.read_text(encoding="utf-8")
                async with conn.transaction():
                    await conn.execute(sql)
                    await conn.execute(
                        "INSERT INTO schema_version(version) VALUES ($1)", version
                    )
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", _MIGRATION_LOCK_ID)


# ── Repository helpers ────────────────────────────────────────────────


async def upsert_user(
    pool: asyncpg.Pool,
    *,
    oidc_iss: str,
    oidc_sub: str,
    display_name: Optional[str],
    email: Optional[str],
) -> str:
    """Lazy user upsert on first authenticated request. Bumps last_seen_at.

    Returns the user's internal UUID as a string. The (oidc_iss, oidc_sub)
    tuple is the durable cross-app handle; the UUID is paradoc's internal
    PK used by project_members.
    """
    row = await pool.fetchrow(
        """
        INSERT INTO users (oidc_iss, oidc_sub, display_name, email)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (oidc_iss, oidc_sub) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            email = EXCLUDED.email,
            last_seen_at = NOW()
        RETURNING id
        """,
        oidc_iss,
        oidc_sub,
        display_name or None,
        email or None,
    )
    return str(row["id"])


async def list_user_projects(pool: asyncpg.Pool, user_id: str) -> list[Project]:
    """Projects the user is a member of, excluding archived."""
    rows = await pool.fetch(
        """
        SELECT p.id, p.slug, p.name, p.shelf_base_url, m.role
        FROM projects p
        JOIN project_members m ON m.project_id = p.id
        WHERE m.user_id = $1::uuid AND p.archived_at IS NULL
        ORDER BY p.name
        """,
        user_id,
    )
    return [
        Project(
            id=str(r["id"]),
            slug=r["slug"],
            name=r["name"],
            shelf_base_url=r["shelf_base_url"],
            role=r["role"],
        )
        for r in rows
    ]


async def is_project_member(
    pool: asyncpg.Pool, *, project_id: str, user_id: str
) -> bool:
    row = await pool.fetchrow(
        """
        SELECT 1 FROM project_members
        WHERE project_id = $1::uuid AND user_id = $2::uuid
        """,
        project_id,
        user_id,
    )
    return row is not None


async def project_id_from_slug(pool: asyncpg.Pool, slug: str) -> Optional[str]:
    """Resolve a project slug to its UUID. Returns None if unknown.

    Used by the scope-path resolver so URLs can carry friendlier slugs
    (e.g. ``project:topside-design``) and only the resolved UUID lands
    in the storage prefix.
    """
    row = await pool.fetchrow(
        """
        SELECT id FROM projects
        WHERE slug = $1 AND archived_at IS NULL
        """,
        slug,
    )
    return str(row["id"]) if row else None


# ── Admin repository helpers ──────────────────────────────────────────


def _project_row_to_dict(r) -> dict:
    return {
        "id": str(r["id"]),
        "slug": r["slug"],
        "name": r["name"],
        "shelf_base_url": r["shelf_base_url"],
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "archived_at": r["archived_at"].isoformat() if r["archived_at"] else None,
    }


async def list_all_projects(pool: asyncpg.Pool) -> list[dict]:
    """Admin view: every project (including archived). With member counts."""
    rows = await pool.fetch(
        """
        SELECT p.id, p.slug, p.name, p.shelf_base_url,
               p.created_at, p.archived_at,
               COUNT(m.user_id) AS member_count
        FROM projects p
        LEFT JOIN project_members m ON m.project_id = p.id
        GROUP BY p.id
        ORDER BY p.archived_at IS NOT NULL, p.name
        """
    )
    out = []
    for r in rows:
        d = _project_row_to_dict(r)
        d["member_count"] = int(r["member_count"])
        out.append(d)
    return out


async def create_project(pool: asyncpg.Pool, slug: str, name: str) -> dict:
    """Insert a project and return it. Slug is unique; conflicts → ValueError."""
    try:
        row = await pool.fetchrow(
            """
            INSERT INTO projects (slug, name) VALUES ($1, $2)
            RETURNING id, slug, name, shelf_base_url, created_at, archived_at
            """,
            slug,
            name,
        )
    except asyncpg.UniqueViolationError as exc:
        raise ValueError(f"slug {slug!r} already exists") from exc
    assert row is not None
    d = _project_row_to_dict(row)
    d["member_count"] = 0
    return d


async def update_project(
    pool: asyncpg.Pool,
    project_id: str,
    *,
    name: Optional[str] = None,
    shelf_base_url: Optional[str] = None,
    clear_shelf_base_url: bool = False,
) -> Optional[dict]:
    """Partial update. Returns the updated project row, or None if missing.

    ``shelf_base_url=None`` leaves the field untouched (no change);
    pass ``clear_shelf_base_url=True`` to explicitly set it to NULL.
    """
    sets: list[str] = []
    args: list = []
    if name is not None:
        sets.append(f"name = ${len(args) + 1}")
        args.append(name)
    if clear_shelf_base_url:
        sets.append("shelf_base_url = NULL")
    elif shelf_base_url is not None:
        sets.append(f"shelf_base_url = ${len(args) + 1}")
        args.append(shelf_base_url)
    if not sets:
        # Nothing to update; treat as "fetch current row".
        row = await pool.fetchrow(
            "SELECT id, slug, name, shelf_base_url, created_at, archived_at "
            "FROM projects WHERE id = $1::uuid",
            project_id,
        )
        return _project_row_to_dict(row) if row else None
    args.append(project_id)
    query = (
        f"UPDATE projects SET {', '.join(sets)} "
        f"WHERE id = ${len(args)}::uuid "
        f"RETURNING id, slug, name, shelf_base_url, created_at, archived_at"
    )
    row = await pool.fetchrow(query, *args)
    return _project_row_to_dict(row) if row else None


async def archive_project(pool: asyncpg.Pool, project_id: str) -> bool:
    """Soft-delete: stamp archived_at. Returns False when not found.

    Preserves project_members + future audit refs; un-archive is left
    as a future admin tool. Hard-delete intentionally not exposed.
    """
    row = await pool.fetchrow(
        "UPDATE projects SET archived_at = NOW() "
        "WHERE id = $1::uuid AND archived_at IS NULL RETURNING id",
        project_id,
    )
    return row is not None


async def project_exists(pool: asyncpg.Pool, project_id: str) -> bool:
    row = await pool.fetchrow(
        "SELECT 1 FROM projects WHERE id = $1::uuid", project_id
    )
    return row is not None


async def list_project_members(pool: asyncpg.Pool, project_id: str) -> list[dict]:
    rows = await pool.fetch(
        """
        SELECT m.user_id, m.role, m.added_at,
               u.email, u.display_name, u.oidc_iss, u.oidc_sub, u.last_seen_at
        FROM project_members m
        JOIN users u ON u.id = m.user_id
        WHERE m.project_id = $1::uuid
        ORDER BY u.display_name, u.id
        """,
        project_id,
    )
    return [
        {
            "user_id": str(r["user_id"]),
            "role": r["role"],
            "added_at": r["added_at"].isoformat() if r["added_at"] else None,
            "email": r["email"],
            "display_name": r["display_name"],
            "oidc_iss": r["oidc_iss"],
            "oidc_sub": r["oidc_sub"],
            "last_seen_at": r["last_seen_at"].isoformat() if r["last_seen_at"] else None,
        }
        for r in rows
    ]


async def add_project_member(
    pool: asyncpg.Pool, project_id: str, user_id: str, role: str = "member"
) -> bool:
    """Idempotent membership add. Returns True on insert, False on duplicate.

    The user must already exist (we don't pre-seed placeholder rows
    here — paradoc only adds users who've authenticated at least once,
    so the admin can pick them from a list).
    """
    row = await pool.fetchrow(
        """
        INSERT INTO project_members (project_id, user_id, role)
        VALUES ($1::uuid, $2::uuid, $3)
        ON CONFLICT (project_id, user_id) DO NOTHING
        RETURNING user_id
        """,
        project_id,
        user_id,
        role,
    )
    return row is not None


async def remove_project_member(
    pool: asyncpg.Pool, project_id: str, user_id: str
) -> bool:
    row = await pool.fetchrow(
        "DELETE FROM project_members "
        "WHERE project_id = $1::uuid AND user_id = $2::uuid RETURNING user_id",
        project_id,
        user_id,
    )
    return row is not None


async def list_users(pool: asyncpg.Pool, *, limit: int = 200) -> list[dict]:
    """List known users. Admin UI uses this for the member-picker."""
    rows = await pool.fetch(
        """
        SELECT id, oidc_iss, oidc_sub, email, display_name, last_seen_at
        FROM users
        ORDER BY display_name NULLS LAST, last_seen_at DESC
        LIMIT $1
        """,
        limit,
    )
    return [
        {
            "id": str(r["id"]),
            "oidc_iss": r["oidc_iss"],
            "oidc_sub": r["oidc_sub"],
            "email": r["email"],
            "display_name": r["display_name"],
            "last_seen_at": r["last_seen_at"].isoformat() if r["last_seen_at"] else None,
        }
        for r in rows
    ]


async def user_exists(pool: asyncpg.Pool, user_id: str) -> bool:
    row = await pool.fetchrow(
        "SELECT 1 FROM users WHERE id = $1::uuid", user_id
    )
    return row is not None


# ── API tokens ──────────────────────────────────────────────────────
#
# Long-lived bearer credentials for the `paradoc publish` CLI and other
# automation that can't drive the interactive OIDC flow. Issued by the
# user from the UI; presented as a `Bearer paradoc_<32-byte-base64url>`
# in the Authorization header on uploads. The verifier hashes the
# plaintext and looks up here.


async def create_api_token(
    pool: asyncpg.Pool,
    *,
    user_id: str,
    name: str,
    token_hash: bytes,
) -> dict:
    """Insert a fresh token row and return the row contents (no plaintext)."""
    row = await pool.fetchrow(
        """
        INSERT INTO api_tokens (user_id, name, token_hash)
        VALUES ($1::uuid, $2, $3)
        RETURNING id, user_id, name, created_at
        """,
        user_id,
        name,
        token_hash,
    )
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "name": row["name"],
        "created_at": row["created_at"].isoformat(),
    }


async def list_api_tokens(pool: asyncpg.Pool, user_id: str) -> list[dict]:
    """All non-revoked tokens for ``user_id`` with metadata only."""
    rows = await pool.fetch(
        """
        SELECT id, name, created_at, last_used_at
        FROM api_tokens
        WHERE user_id = $1::uuid AND revoked_at IS NULL
        ORDER BY created_at DESC
        """,
        user_id,
    )
    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "created_at": r["created_at"].isoformat(),
            "last_used_at": r["last_used_at"].isoformat() if r["last_used_at"] else None,
        }
        for r in rows
    ]


async def revoke_api_token(
    pool: asyncpg.Pool, *, token_id: str, user_id: str
) -> bool:
    """Mark a user's token revoked. Returns whether anything changed."""
    row = await pool.fetchrow(
        """
        UPDATE api_tokens
        SET revoked_at = NOW()
        WHERE id = $1::uuid AND user_id = $2::uuid AND revoked_at IS NULL
        RETURNING id
        """,
        token_id,
        user_id,
    )
    return row is not None


async def resolve_api_token(pool: asyncpg.Pool, token_hash: bytes) -> Optional[dict]:
    """Look up a presented token by hash. Bumps last_used_at on hit.

    Returns the owning user's identity tuple (id, oidc_iss, oidc_sub,
    display_name, email) so the verifier can hand a paradoc User
    upstream without a second SELECT. None when the hash doesn't match
    a live (non-revoked) token.
    """
    row = await pool.fetchrow(
        """
        UPDATE api_tokens
        SET last_used_at = NOW()
        WHERE token_hash = $1 AND revoked_at IS NULL
        RETURNING user_id
        """,
        token_hash,
    )
    if row is None:
        return None
    user = await pool.fetchrow(
        """
        SELECT id, oidc_iss, oidc_sub, display_name, email
        FROM users
        WHERE id = $1::uuid
        """,
        row["user_id"],
    )
    if user is None:
        return None
    return {
        "id": str(user["id"]),
        "oidc_iss": user["oidc_iss"],
        "oidc_sub": user["oidc_sub"],
        "display_name": user["display_name"],
        "email": user["email"],
    }
