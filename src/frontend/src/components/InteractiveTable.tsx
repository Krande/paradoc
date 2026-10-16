import React from 'react'
import { TableRenderer } from './TableRenderer'
import { resolveTableKey } from '../sections/store'

interface InteractiveTableProps {
  tableId?: string
  className?: string
  tableKey: string
  docId?: string
  staticContent: React.ReactNode
  caption?: React.ReactNode
}

export function InteractiveTable({ tableId, className, tableKey, docId, staticContent, caption }: InteractiveTableProps) {
  const [showInteractive, setShowInteractive] = React.useState(false)
  const [isHovering, setIsHovering] = React.useState(false)
  const [resolvedKey, setResolvedKey] = React.useState<string | null>(null)
  const tableExists = resolvedKey !== null

  // Does the document have interactive data for this table (exact key, or without a `_N`
  // suffix)? Re-checked when table data arrives after mount (`tableKey: '*'` is a whole set).
  React.useEffect(() => {
    if (!docId || !tableKey) {
      setResolvedKey(null)
      return
    }
    let canceled = false
    const check = () => {
      resolveTableKey(docId, tableKey)
        .then((k) => {
          if (!canceled) setResolvedKey(k ?? null)
        })
        .catch(() => {
          if (!canceled) setResolvedKey(null)
        })
    }
    check()
    const onStored = (event: Event) => {
      const d = (event as CustomEvent<{ docId: string; tableKey: string }>).detail
      if (d.docId !== docId) return
      if (d.tableKey === '*' || d.tableKey === tableKey || d.tableKey === tableKey.replace(/_\d+$/, '')) check()
    }
    window.addEventListener('paradoc:table-data-stored', onStored)
    return () => {
      canceled = true
      window.removeEventListener('paradoc:table-data-stored', onStored)
    }
  }, [docId, tableKey])

  // If no table data exists, just render as static table
  if (!tableExists) {
    return (
      <div id={tableId} className={className}>
        {staticContent}
        {caption}
      </div>
    )
  }

  // Table exists - render with interactive toggle
  return (
    <div
      className="relative group"
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      {/* Context menu - shown on hover */}
      {isHovering && (
        <div className="absolute top-2 right-2 bg-white shadow-lg rounded-md border border-gray-200 p-2 z-10 flex gap-2">
          <button
            onClick={() => setShowInteractive(false)}
            className={`px-3 py-1 rounded text-sm cursor-pointer transition-colors ${
              !showInteractive 
                ? 'bg-blue-600 text-white' 
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            Static
          </button>
          <button
            onClick={() => setShowInteractive(true)}
            className={`px-3 py-1 rounded text-sm cursor-pointer transition-colors ${
              showInteractive 
                ? 'bg-blue-600 text-white' 
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            Interactive
          </button>
        </div>
      )}

      {/* Show either static table or interactive table */}
      {showInteractive ? (
        <div className="my-4">
          <TableRenderer tableKey={resolvedKey ?? tableKey} docId={docId} />
        </div>
      ) : (
        <div id={tableId} className={className}>
          {staticContent}
          {caption}
        </div>
      )}
    </div>
  )
}
