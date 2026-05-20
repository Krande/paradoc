import React from 'react'
import { Modal } from './Modal'
import { getRuntimeConfig } from '../transport'
import { authedFetch } from '../services/auth/oidc'

interface BuildInfo {
  paradoc_version?: string
  python_version?: string
  python_full_version?: string
  platform?: string
  fastapi_version?: string
  uvicorn_version?: string
  obstore_version?: string
  image_sha?: string
  image_tag?: string
  build_time?: string
}

interface AboutModalProps {
  open: boolean
  onClose: () => void
}

function joinUrl(base: string, path: string): string {
  return base.replace(/\/?$/, '') + path
}

// Read-only build/runtime identity. Only fetches when the modal opens
// (no point hitting /api/info on every page load). REST mode only — in
// WS mode the info would have to come over the worker, which we haven't
// wired yet, so we just say so.
export function AboutModal({ open, onClose }: AboutModalProps) {
  const [info, setInfo] = React.useState<BuildInfo | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(false)

  React.useEffect(() => {
    if (!open) return
    const cfg = getRuntimeConfig()
    if (cfg.transport !== 'rest') {
      setError('Build info is only exposed in REST mode.')
      setInfo(null)
      return
    }
    let canceled = false
    setLoading(true)
    setError(null)
    ;(async () => {
      try {
        const res = await authedFetch(joinUrl(cfg.apiBase || '', '/api/info'), { cache: 'no-store' })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const body = (await res.json()) as BuildInfo
        if (!canceled) setInfo(body)
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
    <Modal open={open} onClose={onClose} title="About paradoc">
      {loading && <div className="text-gray-500 dark:text-gray-400">Loading…</div>}
      {error && <div className="text-red-600 dark:text-red-400">Could not load build info: {error}</div>}
      {info && (
        <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2">
          <Row label="paradoc" value={info.paradoc_version} />
          <Row label="image tag" value={info.image_tag} mono />
          <Row label="image sha" value={info.image_sha?.slice(0, 12)} mono title={info.image_sha} />
          <Row label="built" value={info.build_time} mono />
          <Row label="python" value={info.python_version} />
          <Row label="fastapi" value={info.fastapi_version} />
          <Row label="uvicorn" value={info.uvicorn_version} />
          <Row label="obstore" value={info.obstore_version} />
          <Row label="platform" value={info.platform} />
        </dl>
      )}
    </Modal>
  )
}

function Row({ label, value, mono, title }: { label: string; value?: string; mono?: boolean; title?: string }) {
  return (
    <>
      <dt className="text-gray-500 dark:text-gray-400">{label}</dt>
      <dd className={(mono ? 'font-mono ' : '') + 'text-gray-800 dark:text-gray-200 break-all'} title={title}>
        {value || <span className="text-gray-400 dark:text-gray-500 italic">unknown</span>}
      </dd>
    </>
  )
}
