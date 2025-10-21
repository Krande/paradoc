import React, { useEffect, useState } from 'react'
import { getTableData } from '../sections/store'

interface TableRendererProps {
  tableKey: string
  docId?: string
}

export function TableRenderer({ tableKey, docId }: TableRendererProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tableData, setTableData] = useState<any>(null)
  const [sortColumn, setSortColumn] = useState<string | null>(null)
  const [sortAscending, setSortAscending] = useState(true)
  const [columnFilters, setColumnFilters] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!docId) return

    // Load table data from IndexedDB
    getTableData(docId, tableKey)
      .then(data => {
        if (data) {
          setTableData(data)
          // Set default sort if available
          if (data.default_sort) {
            setSortColumn(data.default_sort.column_name)
            setSortAscending(data.default_sort.ascending)
          }
          setError(null)
        } else {
          setError(`Table '${tableKey}' not found`)
        }
        setLoading(false)
      })
      .catch(err => {
        console.error('Error loading table data:', err)
        setError('Failed to load table data')
        setLoading(false)
      })
  }, [tableKey, docId])

  if (loading) {
    return (
      <div className="my-4 p-4 border border-gray-300 rounded bg-gray-50">
        <div className="flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-3 text-gray-600">Loading table...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="my-4 p-4 border border-red-300 rounded bg-red-50">
        <p className="text-red-600 font-semibold">Error loading table: {tableKey}</p>
        <p className="text-red-500 text-sm">{error}</p>
      </div>
    )
  }

  if (!tableData) return null

  // Convert cells to rows for easier rendering
  const rowsMap: Record<number, Record<string, any>> = {}
  tableData.cells.forEach((cell: any) => {
    if (!rowsMap[cell.row_index]) {
      rowsMap[cell.row_index] = {}
    }
    rowsMap[cell.row_index][cell.column_name] = cell.value
  })

  let rows = Object.keys(rowsMap)
    .map(idx => ({ index: parseInt(idx), ...rowsMap[parseInt(idx)] }))
    .sort((a, b) => a.index - b.index)

  // Apply per-column filtering
  rows = rows.filter(row => {
    return Object.entries(columnFilters).every(([columnName, filterValue]) => {
      if (!filterValue) return true
      const cellValue = String((row as any)[columnName] || '')
      return cellValue.toLowerCase().includes(filterValue.toLowerCase())
    })
  })

  // Apply sorting
  if (sortColumn) {
    rows.sort((a, b) => {
      const aVal = (a as any)[sortColumn]
      const bVal = (b as any)[sortColumn]

      // Try numeric comparison first
      const aNum = parseFloat(aVal)
      const bNum = parseFloat(bVal)
      if (!isNaN(aNum) && !isNaN(bNum)) {
        return sortAscending ? aNum - bNum : bNum - aNum
      }

      // Fall back to string comparison
      const aStr = String(aVal || '')
      const bStr = String(bVal || '')
      const cmp = aStr.localeCompare(bStr)
      return sortAscending ? cmp : -cmp
    })
  }

  const handleSort = (columnName: string) => {
    if (sortColumn === columnName) {
      setSortAscending(!sortAscending)
    } else {
      setSortColumn(columnName)
      setSortAscending(true)
    }
  }

  const handleColumnFilter = (columnName: string, value: string) => {
    setColumnFilters(prev => ({
      ...prev,
      [columnName]: value
    }))
  }

  return (
    <div className="my-4">
      {tableData.caption && (
        <p className="text-sm font-semibold mb-2">{tableData.caption}</p>
      )}

      <div className="overflow-x-auto border border-gray-300 rounded">
        <table className="min-w-full border-collapse bg-white">
          <thead className="bg-gray-100">
            <tr>
              {tableData.show_index_default && (
                <th className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-sm">
                  #
                </th>
              )}
              {tableData.columns.map((col: any) => (
                <th
                  key={col.name}
                  className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-sm"
                >
                  <div className="flex flex-col gap-1">
                    <div
                      className="flex items-center cursor-pointer hover:bg-gray-200 -mx-3 -my-2 px-3 py-2 rounded select-none"
                      onClick={() => handleSort(col.name)}
                    >
                      <span>{col.name}</span>
                      {sortColumn === col.name && (
                        <span className="ml-1">
                          {sortAscending ? '↑' : '↓'}
                        </span>
                      )}
                    </div>
                    <input
                      type="text"
                      placeholder={`Filter ${col.name}...`}
                      value={columnFilters[col.name] || ''}
                      onChange={(e) => handleColumnFilter(col.name, e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      className="px-2 py-1 text-xs border border-gray-300 rounded w-full focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIdx) => (
              <tr
                key={rowIdx}
                className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
              >
                {tableData.show_index_default && (
                  <td className="px-3 py-2 border-b border-gray-200 text-sm text-gray-600">
                    {rowIdx}
                  </td>
                )}
                {tableData.columns.map((col: any) => (
                  <td
                    key={col.name}
                    className="px-3 py-2 border-b border-gray-200 text-sm"
                  >
                    {(row as any)[col.name] !== undefined ? String((row as any)[col.name]) : ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-gray-500 mt-2">
        Showing {rows.length} {rows.length === 1 ? 'row' : 'rows'}
      </p>
    </div>
  )
}

