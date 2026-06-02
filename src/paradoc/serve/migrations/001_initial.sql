-- 001_initial.sql — control-plane schema for paradoc-serve.
--
-- Bundle content stays in per-bundle sqlite files (paradoc/db/manager.py).
-- This Postgres schema is the *control* plane: who can sign in, which
-- projects exist, who's a member, and where each project's linked shelf
-- instance lives.
--
-- Users are identified by the (oidc_iss, oidc_sub) tuple — never email,
-- which can change across IdPs. Each (iss, sub) maps to one users row
-- via the UNIQUE constraint; a person who signs in via two different
-- IdPs gets two users rows (no implicit merge — see the harmonization
-- note `dap/plan/v1/notes_auth_scope_harmonization.md`).

CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    oidc_iss      TEXT NOT NULL,
    oidc_sub      TEXT NOT NULL,
    display_name  TEXT,
    email         TEXT,
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (oidc_iss, oidc_sub)
);

CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    shelf_base_url  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at     TIMESTAMPTZ
);

CREATE TABLE project_members (
    project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role         TEXT NOT NULL DEFAULT 'member',
    added_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (project_id, user_id)
);

CREATE INDEX project_members_user_idx ON project_members(user_id);
