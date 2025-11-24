import React from 'react'
import { TableRenderer } from './TableRenderer'
import { getTableData } from '../sections/store'

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
  const [tableExists, setTableExists] = React.useState(false)

  // Check if table data exists for this table key (handle suffixes like _1, _2)
  React.useEffect(() => {
    if (!docId || !tableKey) {
      setTableExists(false)
      return
    }

    // Try to find table data - first try the exact key, then try without suffix
    const checkTableExists = async () => {
      // Try exact match first
      let data = await getTableData(docId, tableKey)
      if (data) {
        console.log('[InteractiveTable] Found table data for key:', tableKey)
        setTableExists(true)
        return
      }

      // If tableKey has a suffix like _1, _2, try the base key
      const underscoreIndex = tableKey.lastIndexOf('_')
      if (underscoreIndex > 0) {
        const suffix = tableKey.substring(underscoreIndex + 1)
        if (/^\d+$/.test(suffix)) {
          // Has numeric suffix, try base key
          const baseKey = tableKey.substring(0, underscoreIndex)
          data = await getTableData(docId, baseKey)
          if (data) {
            console.log('[InteractiveTable] Found table data for base key:', baseKey, '(original:', tableKey, ')')
            setTableExists(true)
            return
          }
        }
      }

      console.log('[InteractiveTable] No table data found for key:', tableKey)
      setTableExists(false)
    }

    checkTableExists()

    // Listen for table data being stored (handles race condition where data arrives after component mounts)
    const handleTableDataStored = (event: CustomEvent) => {
      const { docId: eventDocId, tableKey: eventTableKey } = event.detail
      if (eventDocId === docId) {
        // Check if the stored table matches our key (exact or base key)
        if (eventTableKey === tableKey) {
          checkTableExists()
        } else {
          // Check if it's a base key match
          const underscoreIndex = tableKey.lastIndexOf('_')
          if (underscoreIndex > 0) {
            const suffix = tableKey.substring(underscoreIndex + 1)
            if (/^\d+$/.test(suffix)) {
              const baseKey = tableKey.substring(0, underscoreIndex)
              if (eventTableKey === baseKey) {
                checkTableExists()
              }
            }
          }
        }
      }
    }

    window.addEventListener('paradoc:table-data-stored', handleTableDataStored as EventListener)

    return () => {
      window.removeEventListener('paradoc:table-data-stored', handleTableDataStored as EventListener)
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
          <TableRenderer tableKey={tableKey} docId={docId} />
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
