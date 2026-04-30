import React from 'react'
import { Modal } from './Modal'
import { getRuntimeConfig } from '../transport'

interface MeResponse {
  principal: string | null
  allowed: boolean
  ingress_headers: Record<string, string | null>
}

interface UserInfoModalProps {
  open: boolean
  onClose: () => void
}

function joinUrl(base: string, path: string): string {
  return base.replace(/\/?$/, '') + path
}

// Reflects whatever the server's AuthPolicy + ingress headers report.
// Anonymous (no oauth2-proxy in front) renders as "Not signed in" rather
// than an error — paradoc-serve allows anonymous reads by default.
export function UserInfoModal({ open, onClose }: UserInfoModalProps) {
  const [me, setMe] = React.useState<MeResponse | null>(null)
  const [error, setError] = React.useState<string | null>(null)
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
    ;(async () => {
      try {
        const res = await fetch(joinUrl(cfg.apiBase || '', '/api/me'), { cache: 'no-store' })
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
      {me && (
        <div className="space-y-3">
          <div>
            <div className="text-gray-500 text-xs uppercase tracking-wide">Principal</div>
            <div className="font-mono text-gray-800 break-all">
              {me.principal || <span className="text-gray-400 italic">Not signed in</span>}
            </div>
          </div>
          <div>
            <div className="text-gray-500 text-xs uppercase tracking-wide mb-1">Ingress headers seen by the server</div>
            <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1">
              {Object.entries(me.ingress_headers).map(([k, v]) => (
                <React.Fragment key={k}>
                  <dt className="font-mono text-xs text-gray-500">{k}</dt>
                  <dd className="font-mono text-xs text-gray-800 break-all">
                    {v || <span className="text-gray-400 italic">—</span>}
                  </dd>
                </React.Fragment>
              ))}
            </dl>
          </div>
          {!me.principal && (
            <p className="text-xs text-gray-500 italic">
              No principal — the deployment is either intra-cluster or runs without an
              authenticating ingress. The default policy still allows reads.
            </p>
          )}
        </div>
      )}
    </Modal>
  )
}
