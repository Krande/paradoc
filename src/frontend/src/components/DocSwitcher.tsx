import React from 'react'
import { getRuntimeConfig } from '../transport'

interface DocGroup {
  key: string
  label: string
  docs: string[]
}

interface DocsResponse {
  docs?: string[]
  groups?: DocGroup[]
}

interface DocSwitcherProps {
  currentDocId: string
  onSelect: (docId: string) => void
}

function joinUrl(base: string, path: string): string {
  return base.replace(/\/?$/, '') + path
}

// Topbar dropdown for switching between docs published by the same
// paradoc-serve. Renders nothing in WS mode (no /api/docs) and renders
// nothing if the API came back empty — better than a stuck-loading UI.
export function DocSwitcher({ currentDocId, onSelect }: DocSwitcherProps) {
  const [groups, setGroups] = React.useState<DocGroup[]>([])
  const [flat, setFlat] = React.useState<string[]>([])
  const [loaded, setLoaded] = React.useState(false)

  React.useEffect(() => {
    const cfg = getRuntimeConfig()
    if (cfg.transport !== 'rest') {
      setLoaded(true)
      return
    }
    let canceled = false
    ;(async () => {
      try {
        const res = await fetch(joinUrl(cfg.apiBase || '', '/api/docs'), { cache: 'no-store' })
        if (!res.ok) return
        const body = (await res.json()) as DocsResponse
        if (canceled) return
        setGroups(body.groups || [])
        setFlat(body.docs || [])
      } catch {
        // Silent — switcher just stays hidden.
      } finally {
        if (!canceled) setLoaded(true)
      }
    })()
    return () => {
      canceled = true
    }
  }, [])

  if (!loaded) return null

  // Hide entirely when there's nothing to switch to. Showing a single-
  // option dropdown next to the doc title is just visual noise.
  const totalDocs = (groups.reduce((n, g) => n + g.docs.length, 0)) || flat.length
  if (totalDocs <= 1) return null

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value
    if (id && id !== currentDocId) onSelect(id)
  }

  return (
    <select
      // Match the Source button (gray pill, same padding/text size) so
      // both controls feel like the same toolbar family. `pr-7` leaves
      // room for the native chevron the rounded variant tucks tight.
      className="cursor-pointer text-xs font-medium pl-3 pr-7 py-1.5 rounded-md bg-gray-200 text-gray-700 hover:bg-gray-300 transition focus:outline-none focus:ring-2 focus:ring-blue-500 max-w-[18rem] appearance-none bg-no-repeat bg-[right_0.5rem_center] bg-[length:0.75rem]"
      style={{
        backgroundImage:
          "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20' stroke='%23374151' stroke-width='1.6'><path stroke-linecap='round' stroke-linejoin='round' d='M6 8l4 4 4-4'/></svg>\")",
      }}
      value={currentDocId}
      onChange={handleChange}
      aria-label="Switch document"
      title="Switch document"
    >
      {!currentDocId && <option value="">Select a document…</option>}
      {groups.length > 0 ? (
        groups.map((g) => (
          <optgroup key={g.key} label={g.label}>
            {g.docs.length === 0 ? (
              <option disabled value={`__empty_${g.key}`}>(none)</option>
            ) : (
              g.docs.map((id) => (
                <option key={id} value={id}>{id}</option>
              ))
            )}
          </optgroup>
        ))
      ) : (
        flat.map((id) => (
          <option key={id} value={id}>{id}</option>
        ))
      )}
    </select>
  )
}
