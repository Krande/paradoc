import React from 'react'
import { Modal } from './Modal'
import { getRuntimeConfig } from '../transport'
import { authedFetch } from '../services/auth/oidc'
import { useSectionStore } from '../sections/store'

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

// Read-only build/runtime identity. REST mode hits /api/info for the
// paradoc-serve image's build identity. Static / embed mode (ada-docs
// FEA report, `OneDoc.export_static` bundles) has no server to ask, so
// we fall back to the DocManifest's bundle-time `paradoc_version` +
// `published_at` + git block — same provenance ada-build / paradoc
// publish stamp at bake time.
export function AboutModal({ open, onClose }: AboutModalProps) {
  const [info, setInfo] = React.useState<BuildInfo | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(false)
  const { state } = useSectionStore()
  const manifest = state.manifest

  React.useEffect(() => {
    if (!open) return
    const cfg = getRuntimeConfig()
    if (cfg.transport !== 'rest') {
      // Static / embed: there's no /api/info, but we still have the
      // bundle's manifest in memory. Drop loading state and let the
      // render fall through to the manifest-backed view below.
      setInfo(null)
      setLoading(false)
      setError(null)
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

  const isRestMode = getRuntimeConfig().transport === 'rest'
  const git = manifest?.git
  const fullCommit = git?.commit
  const remoteHref = git?.remote_url?.startsWith('http') ? git.remote_url : undefined

  return (
    <Modal open={open} onClose={onClose} title="About paradoc">
      {loading && <div className="text-gray-500 dark:text-gray-400">Loading…</div>}
      {error && (
        <div className="text-red-600 dark:text-red-400">Could not load build info: {error}</div>
      )}
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
      {/* Bundle-side identity. Always shown when we have it — gives the
          embed/static case a usable About panel, and adds doc-level
          context (when was THIS report baked, from what commit) on top
          of the server's image identity in REST mode. */}
      {manifest && (manifest.published_at || manifest.paradoc_version || git) && (
        <div className={info ? 'mt-4 pt-3 border-t border-gray-200 dark:border-gray-800' : ''}>
          {!isRestMode && !info && (
            <p className="text-xs text-gray-500 dark:text-gray-400 italic mb-2">
              This bundle was baked statically — no server to query for
              runtime info. Showing the values the exporter stamped into
              this report's manifest.
            </p>
          )}
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2">
            <Row label="bundle id" value={manifest.docId} mono />
            <Row label="paradoc" value={manifest.paradoc_version} />
            <Row label="published" value={manifest.published_at} mono />
            {git && (
              <>
                <Row label="branch" value={git.branch} mono />
                <Row label="commit" value={git.short_commit} mono title={fullCommit} />
                {git.is_dirty !== undefined && (
                  <Row
                    label="dirty"
                    value={git.is_dirty ? 'yes — uncommitted changes at build' : 'no'}
                  />
                )}
                {git.author_email && <Row label="author" value={git.author_email} mono />}
                {git.timestamp && <Row label="committed" value={git.timestamp} mono />}
                {remoteHref && (
                  <Row
                    label="remote"
                    value={
                      <a
                        href={remoteHref}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 dark:text-blue-400 hover:underline break-all"
                      >
                        {remoteHref}
                      </a>
                    }
                  />
                )}
              </>
            )}
          </dl>
        </div>
      )}
    </Modal>
  )
}

function Row({
  label,
  value,
  mono,
  title,
}: {
  label: string
  value?: React.ReactNode
  mono?: boolean
  title?: string
}) {
  return (
    <>
      <dt className="text-gray-500 dark:text-gray-400">{label}</dt>
      <dd
        className={(mono ? 'font-mono ' : '') + 'text-gray-800 dark:text-gray-200 break-all'}
        title={title}
      >
        {value !== undefined && value !== '' ? (
          value
        ) : (
          <span className="text-gray-400 dark:text-gray-500 italic">unknown</span>
        )}
      </dd>
    </>
  )
}
