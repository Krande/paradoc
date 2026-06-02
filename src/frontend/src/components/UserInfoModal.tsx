import React from 'react'
import { Modal } from './Modal'
import { getRuntimeConfig } from '../transport'
import { authedFetch } from '../services/auth/oidc'

interface MeResponse {
  id: string
  iss: string
  subject: string
  email: string
  display_name: string
  groups: string[]
  is_admin: boolean
}

interface UserInfoModalProps {
  open: boolean
  onClose: () => void
}

function joinUrl(base: string, path: string): string {
  return base.replace(/\/?$/, '') + path
}

// Renders whatever the OIDC verifier resolved the current user to.
// When the deployment runs with auth disabled (PARADOC_AUTH_ENABLED unset
// or false), the server returns the synthetic "local-dev" admin user; a
// 401 here means auth is on and no valid bearer was attached to the
// request.
export function UserInfoModal({ open, onClose }: UserInfoModalProps) {
  const [me, setMe] = React.useState<MeResponse | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [unauthenticated, setUnauthenticated] = React.useState(false)
  const [loading, setLoading] = React.useState(false)

  React.useEffect(() => {
    if (!open) return
    const cfg = getRuntimeConfig()
    if (cfg.transport !== 'rest') {
      setError('User info is only available in REST mode.')
      setMe(null)
      return
    }
    let canceled = false
    setLoading(true)
    setError(null)
    setUnauthenticated(false)
    ;(async () => {
      try {
        const res = await authedFetch(joinUrl(cfg.apiBase || '', '/api/me'), { cache: 'no-store' })
        if (res.status === 401) {
          if (!canceled) {
            setUnauthenticated(true)
            setMe(null)
          }
          return
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const body = (await res.json()) as MeResponse
        if (!canceled) setMe(body)
      } catch (e) {
        if (!canceled) setError(e instanceof Error ? e.message : 'failed')
      } finally {
        if (!canceled) setLoading(false)
      }
    })()
    return () => {
      canceled = true
    }
  }, [open])

  return (
    <Modal open={open} onClose={onClose} title="User info">
      {loading && <div className="text-gray-500 dark:text-gray-400">Loading…</div>}
      {error && <div className="text-red-600 dark:text-red-400">Could not load user info: {error}</div>}
      {unauthenticated && (
        <div className="space-y-2">
          <div className="font-mono text-gray-800 dark:text-gray-200">Not signed in</div>
          <p className="text-xs text-gray-500 dark:text-gray-400 italic">
            The server requires an OIDC bearer token but none was provided.
            Sign in via the upstream IdP and reload.
          </p>
        </div>
      )}
      {me && (
        <div className="space-y-3">
          <div>
            <div className="text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">Signed in as</div>
            <div className="font-mono text-gray-800 dark:text-gray-200 break-all">
              {me.display_name}
              {me.email && <span className="text-gray-500 dark:text-gray-400"> &lt;{me.email}&gt;</span>}
            </div>
          </div>
          <div>
            <div className="text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide mb-1">Identity</div>
            <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1">
              <dt className="font-mono text-xs text-gray-500 dark:text-gray-400">id</dt>
              <dd className="font-mono text-xs text-gray-800 dark:text-gray-200 break-all">{me.id}</dd>
              <dt className="font-mono text-xs text-gray-500 dark:text-gray-400">issuer</dt>
              <dd className="font-mono text-xs text-gray-800 dark:text-gray-200 break-all">{me.iss}</dd>
              <dt className="font-mono text-xs text-gray-500 dark:text-gray-400">subject</dt>
              <dd className="font-mono text-xs text-gray-800 dark:text-gray-200 break-all">{me.subject}</dd>
              <dt className="font-mono text-xs text-gray-500 dark:text-gray-400">admin</dt>
              <dd className="font-mono text-xs text-gray-800 dark:text-gray-200">{me.is_admin ? 'yes' : 'no'}</dd>
            </dl>
          </div>
          {me.groups.length > 0 && (
            <div>
              <div className="text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide mb-1">Groups</div>
              <ul className="font-mono text-xs text-gray-800 dark:text-gray-200 space-y-0.5">
                {me.groups.map((g) => (
                  <li key={g}>{g}</li>
                ))}
              </ul>
            </div>
          )}
          {me.iss === 'local-dev' && (
            <p className="text-xs text-gray-500 dark:text-gray-400 italic">
              Auth is disabled (PARADOC_AUTH_ENABLED unset or false). All
              requests get the synthetic local-dev admin user.
            </p>
          )}
          {me.iss !== 'local-dev' && <TokenSection />}
        </div>
      )}
    </Modal>
  )
}

interface ApiToken {
  id: string
  name: string
  created_at: string
  last_used_at?: string
}

// Tokens section. Lists active API tokens, lets the user create a new
// one (plaintext shown once with a copy button), and revoke any of
// them. Backed by the /api/me/tokens endpoints — server only ever
// returns the plaintext on create.
function TokenSection() {
  const [tokens, setTokens] = React.useState<ApiToken[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [newName, setNewName] = React.useState('')
  const [creating, setCreating] = React.useState(false)
  const [createdPlaintext, setCreatedPlaintext] = React.useState<string | null>(null)
  const [createdName, setCreatedName] = React.useState<string | null>(null)

  const apiBase = getRuntimeConfig().apiBase || ''

  const refresh = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await authedFetch(joinUrl(apiBase, '/api/me/tokens'), { cache: 'no-store' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const body = (await res.json()) as { tokens: ApiToken[] }
      setTokens(body.tokens || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'failed')
    } finally {
      setLoading(false)
    }
  }, [apiBase])

  React.useEffect(() => {
    void refresh()
  }, [refresh])

  const create = async () => {
    const name = newName.trim()
    if (!name) return
    setCreating(true)
    setError(null)
    try {
      const res = await authedFetch(joinUrl(apiBase, '/api/me/tokens'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const body = (await res.json()) as { token: string; name: string }
      setCreatedPlaintext(body.token)
      setCreatedName(body.name)
      setNewName('')
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'failed')
    } finally {
      setCreating(false)
    }
  }

  const revoke = async (id: string) => {
    setError(null)
    try {
      const res = await authedFetch(joinUrl(apiBase, `/api/me/tokens/${encodeURIComponent(id)}`), {
        method: 'DELETE',
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'failed')
    }
  }

  return (
    <div>
      <div className="text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide mb-2">
        API tokens
      </div>

      {createdPlaintext && (
        <div className="mb-3 p-3 border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/40 rounded">
          <div className="text-xs font-semibold text-amber-800 dark:text-amber-300 mb-1">
            New token "{createdName}" — copy now, this is the only time you'll see it.
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 font-mono text-xs break-all bg-white dark:bg-gray-900 border border-amber-200 dark:border-amber-800 rounded px-2 py-1">
              {createdPlaintext}
            </code>
            <button
              type="button"
              className="text-xs px-2 py-1 rounded bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900 hover:opacity-80 cursor-pointer"
              onClick={() => {
                void navigator.clipboard.writeText(createdPlaintext)
              }}
            >
              Copy
            </button>
            <button
              type="button"
              className="text-xs px-2 py-1 rounded border border-gray-300 dark:border-gray-700 cursor-pointer"
              onClick={() => {
                setCreatedPlaintext(null)
                setCreatedName(null)
              }}
            >
              Done
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-gray-500 dark:text-gray-400 text-xs">Loading…</div>
      ) : tokens.length === 0 ? (
        <div className="text-gray-500 dark:text-gray-400 text-xs italic">
          No tokens yet. Create one below to use with `paradoc publish`.
        </div>
      ) : (
        <ul className="space-y-1.5">
          {tokens.map((t) => (
            <li
              key={t.id}
              className="flex items-center justify-between gap-2 text-xs border border-gray-200 dark:border-gray-800 rounded px-2 py-1.5"
            >
              <div className="min-w-0">
                <div className="font-medium text-gray-900 dark:text-gray-100 truncate">{t.name}</div>
                <div className="text-gray-500 dark:text-gray-400 font-mono">
                  created {t.created_at.slice(0, 10)}
                  {t.last_used_at && ` · last used ${t.last_used_at.slice(0, 10)}`}
                </div>
              </div>
              <button
                type="button"
                className="text-xs text-red-600 dark:text-red-400 hover:underline cursor-pointer shrink-0"
                onClick={() => void revoke(t.id)}
              >
                Revoke
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-center gap-2 mt-3">
        <input
          type="text"
          value={newName}
          placeholder="Token name (e.g. ci-build, laptop)"
          onChange={(e) => setNewName(e.target.value)}
          className="flex-1 text-xs px-2 py-1.5 rounded border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <button
          type="button"
          disabled={creating || !newName.trim()}
          onClick={() => void create()}
          className="text-xs px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
        >
          {creating ? 'Creating…' : 'New token'}
        </button>
      </div>

      {error && (
        <div className="text-red-600 dark:text-red-400 text-xs mt-2">Token error: {error}</div>
      )}
    </div>
  )
}
