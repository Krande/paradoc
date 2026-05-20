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
      {loading && <div className="text-gray-500">Loading…</div>}
      {error && <div className="text-red-600">Could not load user info: {error}</div>}
      {unauthenticated && (
        <div className="space-y-2">
          <div className="font-mono text-gray-800">Not signed in</div>
          <p className="text-xs text-gray-500 italic">
            The server requires an OIDC bearer token but none was provided.
            Sign in via the upstream IdP and reload.
          </p>
        </div>
      )}
      {me && (
        <div className="space-y-3">
          <div>
            <div className="text-gray-500 text-xs uppercase tracking-wide">Signed in as</div>
            <div className="font-mono text-gray-800 break-all">
              {me.display_name}
              {me.email && <span className="text-gray-500"> &lt;{me.email}&gt;</span>}
            </div>
          </div>
          <div>
            <div className="text-gray-500 text-xs uppercase tracking-wide mb-1">Identity</div>
            <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1">
              <dt className="font-mono text-xs text-gray-500">id</dt>
              <dd className="font-mono text-xs text-gray-800 break-all">{me.id}</dd>
              <dt className="font-mono text-xs text-gray-500">issuer</dt>
              <dd className="font-mono text-xs text-gray-800 break-all">{me.iss}</dd>
              <dt className="font-mono text-xs text-gray-500">subject</dt>
              <dd className="font-mono text-xs text-gray-800 break-all">{me.subject}</dd>
              <dt className="font-mono text-xs text-gray-500">admin</dt>
              <dd className="font-mono text-xs text-gray-800">{me.is_admin ? 'yes' : 'no'}</dd>
            </dl>
          </div>
          {me.groups.length > 0 && (
            <div>
              <div className="text-gray-500 text-xs uppercase tracking-wide mb-1">Groups</div>
              <ul className="font-mono text-xs text-gray-800 space-y-0.5">
                {me.groups.map((g) => (
                  <li key={g}>{g}</li>
                ))}
              </ul>
            </div>
          )}
          {me.iss === 'local-dev' && (
            <p className="text-xs text-gray-500 italic">
              Auth is disabled (PARADOC_AUTH_ENABLED unset or false). All
              requests get the synthetic local-dev admin user.
            </p>
          )}
        </div>
      )}
    </Modal>
  )
}
