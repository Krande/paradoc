import React from 'react'
import { useDocList } from './useDocList'

interface DocSwitcherProps {
  currentDocId: string
  onSelect: (docId: string) => void
}

// Topbar dropdown for switching between docs published by the same
// paradoc-serve. Renders nothing in WS mode (no /api/docs) and renders
// nothing if the API came back empty — better than a stuck-loading UI.
export function DocSwitcher({ currentDocId, onSelect }: DocSwitcherProps) {
  const { loaded, groups, flat, allDocs } = useDocList()

  if (!loaded) return null

  if (allDocs.length <= 1) return null

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value
    if (id && id !== currentDocId) onSelect(id)
  }

  return (
    <select
      // Match the Source button (gray pill, same padding/text size) so
      // both controls feel like the same toolbar family. `pr-7` leaves
      // room for the native chevron the rounded variant tucks tight.
      className="cursor-pointer text-xs font-medium pl-3 pr-7 py-1.5 rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700 transition focus:outline-none focus:ring-2 focus:ring-blue-500 max-w-[18rem] appearance-none bg-no-repeat bg-[right_0.5rem_center] bg-[length:0.75rem]"
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
