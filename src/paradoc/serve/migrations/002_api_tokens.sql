-- 002_api_tokens.sql — long-lived API tokens for the `paradoc publish`
-- CLI (and other automation that can't go through the interactive OIDC
-- flow). Issued and revoked per-user from the UI; the CLI presents
-- one as a bearer alongside any OIDC JWT, and the verifier resolves
-- either form to the same `User`.
--
-- Hashing: we store sha256(plaintext) only. The plaintext is 32 bytes
-- of `secrets.token_bytes` rendered as base64url with a `paradoc_`
-- prefix (mirrors GitHub PAT shape `ghp_*`); 256 bits is well past
-- what brute force can reach, so no salt/argon2 is needed. We can
-- still revoke a leaked token by deleting the row.
--
-- Lookup pattern: the verifier hashes the incoming bearer and SELECTs
-- by (token_hash, revoked_at IS NULL). The UNIQUE index on token_hash
-- makes this a single index lookup. last_used_at is bumped on each
-- successful resolution so the UI can show "last used 3h ago".

CREATE TABLE IF NOT EXISTS api_tokens (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    -- 32 bytes; raw sha256 digest. Stored as bytea so we can compare
    -- with `decode($1, 'hex')` from asyncpg without TEXT encoding.
    token_hash    BYTEA NOT NULL UNIQUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at  TIMESTAMPTZ,
    revoked_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS api_tokens_user_idx ON api_tokens(user_id)
    WHERE revoked_at IS NULL;
