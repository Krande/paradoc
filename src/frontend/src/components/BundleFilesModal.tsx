import React from 'react'
import { Modal } from './Modal'
import { getRuntimeConfig } from '../transport'
import { authedFetch } from '../services/auth/oidc'

interface BundleFileEntry {
  rel_path: string
  size: number
  content_type: string
}

interface BundleFilesResponse {
  doc_id: string
  files: BundleFileEntry[]
}

interface BundleFilesModalProps {
  open: boolean
  onClose: () => void
  docId?: string
}

function joinUrl(base: string, path: string): string {
  return base.replace(/\/?$/, '') + path
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KiB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MiB`
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GiB`
}

// Lists every file the deployed bundle actually carries — markdown
// sections, GLBs, baked FEA artefacts, posters, paradoc.sqlite, etc.
// Useful for inspecting what shipped in a report (e.g. "is the
// chromium poster actually there?", "what FEA blobs are baked?"),
// and as a low-friction download surface for any embedded file the
// user wants to grab.
//
// REST-mode only today; static-mode would require reading the bundle's
// manifest.json + assets/ index, which the SPA doesn't load up-front
// — punt to a separate task if we ever need it there.
export function BundleFilesModal({ open, onClose, docId }: BundleFilesModalProps) {
  const [data, setData] = React.useState<BundleFilesResponse | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [filter, setFilter] = React.useState('')

  React.useEffect(() => {
    if (!open || !docId) return
    const cfg = getRuntimeConfig()
    if (cfg.transport !== 'rest') {
      setError('File manifest is only available in REST mode.')
      return
    }
    let canceled = false
    setLoading(true)
    setError(null)
    ;(async () => {
      try {
        const url = joinUrl(
          cfg.apiBase || '',
          `/api/docs/${encodeURIComponent(docId)}/manifest/files`,
        )
        const res = await authedFetch(url, { cache: 'no-store' })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const body = (await res.json()) as BundleFilesResponse
        if (!canceled) setData(body)
      } catch (e) {
        if (!canceled) setError(e instanceof Error ? e.message : 'failed')
      } finally {
        if (!canceled) setLoading(false)
      }
    })()
    return () => {
      canceled = true
    }
  }, [open, docId])

  const filtered = React.useMemo(() => {
    if (!data) return []
    const q = filter.trim().toLowerCase()
    if (!q) return data.files
    return data.files.filter((f) => f.rel_path.toLowerCase().includes(q))
  }, [data, filter])

  const totalBytes = React.useMemo(
    () => (data ? data.files.reduce((acc, f) => acc + f.size, 0) : 0),
    [data],
  )

  function downloadUrl(rel: string): string {
    const cfg = getRuntimeConfig()
    return joinUrl(
      cfg.apiBase || '',
      `/api/docs/${encodeURIComponent(docId || '')}/files/${rel}`,
    )
  }

  return (
    <Modal open={open} onClose={onClose} title={`Bundle files${docId ? ` — ${docId}` : ''}`}>
      {loading && <div className="text-gray-500 dark:text-gray-400">Loading…</div>}
      {error && (
        <div className="text-red-600 dark:text-red-400">Could not load file list: {error}</div>
      )}
      {data && (
        <div className="flex flex-col gap-2 min-w-0">
          <div className="flex items-baseline justify-between gap-2">
            <input
              type="search"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter by path…"
              className="flex-1 min-w-0 px-2 py-1 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 rounded"
            />
            <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
              {filtered.length} of {data.files.length} files ({formatBytes(totalBytes)} total)
            </span>
          </div>
          <div className="max-h-[60vh] overflow-y-auto border border-gray-200 dark:border-gray-800 rounded">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-gray-50 dark:bg-gray-900 text-left text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                <tr>
                  <th className="px-3 py-1.5 font-medium">Path</th>
                  <th className="px-3 py-1.5 font-medium text-right">Size</th>
                  <th className="px-3 py-1.5 font-medium">Type</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((f) => (
                  <tr
                    key={f.rel_path}
                    className="border-t border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-900"
                  >
                    <td className="px-3 py-1 font-mono text-xs break-all">
                      {/* The doc-files endpoint serves files under
                          `<bundle>/files/`; the manifest lists every
                          file in the bundle, so most won't open via
                          the click. Provide it anyway for the
                          ones that do — markdown sections etc. */}
                      <a
                        href={downloadUrl(f.rel_path)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 dark:text-blue-400 hover:underline"
                      >
                        {f.rel_path}
                      </a>
                    </td>
                    <td className="px-3 py-1 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">
                      {formatBytes(f.size)}
                    </td>
                    <td className="px-3 py-1 text-gray-500 dark:text-gray-400 font-mono text-xs whitespace-nowrap">
                      {f.content_type || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Modal>
  )
}
