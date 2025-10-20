import React from 'react'
import type { Attr, PandocBlock, Table } from './types'
import { attrs } from './utils'
import { renderInlines } from './inlineRenderers'
import { InteractiveFigure } from '../components/InteractiveFigure'
import { InteractiveTable } from '../components/InteractiveTable'
import { useDocId } from './context'
import type { HeadingNumbering } from './headingNumbers'

/**
 * Render a Div block (generic container)
 */
export function renderDiv(b: any, renderBlock: (b: any, k?: React.Key, hn?: HeadingNumbering) => React.ReactElement | null, key?: React.Key): React.ReactElement {
  const [a, blocks] = b.c as [Attr, PandocBlock[]]
  const divAttrs = attrs(a)
  if (divAttrs.className?.includes('figure')) {
    // Basic figure styling; render children and allow captions to flow
    const className = ['my-4', divAttrs.className].filter(Boolean).join(' ')
    return (
      <figure key={key} {...divAttrs} className={className}>
        {blocks.map((bb, j) => renderBlock(bb, j))}
      </figure>
    )
  }
  return <div key={key} {...divAttrs}>{blocks.map((bb, j) => renderBlock(bb, j))}</div>
}

/**
 * Render a Figure block (Pandoc v3+ with proper caption support)
 */
export function renderFigure(b: any, renderBlock: (b: any, k?: React.Key, hn?: HeadingNumbering) => React.ReactElement | null, key?: React.Key): React.ReactElement {
  // Pandoc v3+ Figure block: c = [Attr, [ShortCaption|null, [Blocks caption]], [Blocks content]]
  const [a, cap, content] = b.c as [Attr, any, PandocBlock[]]
  const captionBlocks: any[] = (cap && Array.isArray(cap) && Array.isArray(cap[1])) ? cap[1] : []
  // Extract inlines from first caption block if present
  let captionInlines: any[] = []
  if (captionBlocks.length > 0) {
    const firstCap = captionBlocks[0]
    // Supports { t: 'Plain'|'Para', c: [inlines...] } and list-form
    if (firstCap && typeof firstCap === 'object') {
      if (Array.isArray(firstCap)) {
        // list-form, [ 'Plain', inlines ]
        captionInlines = (firstCap.length > 1 && Array.isArray(firstCap[1])) ? firstCap[1] : []
      } else if ('t' in firstCap) {
        captionInlines = Array.isArray((firstCap as any).c) ? (firstCap as any).c : []
      }
    }
  }
  const figAttrs = attrs(a)
  const className = ['my-4', figAttrs.className].filter(Boolean).join(' ')

  // Extract plot key from figure ID (format: fig:plot_key or fig:plot_key_1)
  // Check if this figure corresponds to a plot from the database
  let plotKey: string | undefined
  const docId = useDocId()

  if (figAttrs.id && figAttrs.id.startsWith('fig:')) {
    // Remove 'fig:' prefix to get the plot key (possibly with suffix like _1, _2)
    const figKey = figAttrs.id.substring(4)

    // For now, assume the figKey directly matches a plot key
    // If the plot has been used multiple times, it might have a suffix like plot_key_1
    // We'll check if it exists in the plot data by trying the full key first,
    // then trying without numeric suffix
    plotKey = figKey

    console.log('[renderFigure] Figure with ID:', {
      figureId: figAttrs.id,
      extractedPlotKey: plotKey,
      docId: docId,
      hasDocId: !!docId
    })
  }

  if (plotKey && docId) {
    // This is potentially an interactive plot - wrap it with InteractiveFigure component
    // The InteractiveFigure component will check if the plot exists in the database
    console.log('[renderFigure] Rendering as interactive plot candidate:', { plotKey, figureId: figAttrs.id })
    const caption = captionInlines && captionInlines.length > 0 ? renderInlines(captionInlines as any) : undefined

    return (
      <InteractiveFigure
        key={key}
        figureId={figAttrs.id}
        className={className}
        plotKey={plotKey}
        docId={docId}
        content={content}
        caption={caption}
      />
    )
  }

  // Regular figure without plot key (not a fig: ID or no docId)
  return (
    <figure key={key} {...figAttrs} className={className}>
      {Array.isArray(content) ? content.map((bb, j) => renderBlock(bb as any, j)) : null}
      {captionInlines && captionInlines.length > 0 ? (
        <figcaption className="text-sm text-gray-600 italic mt-2">
          {renderInlines(captionInlines as any)}
        </figcaption>
      ) : null}
    </figure>
  )
}

/**
 * Render a Table block
 */
export function renderTable(b: Table, renderBlock: (b: any, k?: React.Key, hn?: HeadingNumbering) => React.ReactElement | null, key?: React.Key): React.ReactElement {
  // Table: [Attr, Caption, [ColSpec], TableHead, [TableBody], TableFoot]
  const [a, caption, , tableHead, tableBodies, tableFoot] = b.c

  // Extract caption text if present
  let captionInlines: any[] = []
  if (caption && Array.isArray(caption)) {
    // Caption structure: [ShortCaption|null, [Blocks]]
    const captionBlocks = (Array.isArray(caption[1])) ? caption[1] : []
    if (captionBlocks.length > 0) {
      const firstBlock = captionBlocks[0]
      if (firstBlock && typeof firstBlock === 'object' && 't' in firstBlock && Array.isArray(firstBlock.c)) {
        captionInlines = firstBlock.c
      }
    }
  }

  // Helper to render table cells
  const renderCell = (cell: any, cellKey: number, isHeader = false) => {
    // Cell structure: [Attr, Alignment, RowSpan, ColSpan, [Blocks]]
    if (!cell || !Array.isArray(cell)) return null
    const [cellAttr, , rowSpan, colSpan, cellBlocks] = cell
    const cellAttrs = attrs(cellAttr)
    const content = Array.isArray(cellBlocks) ? cellBlocks.map((bb: any, i: number) => renderBlock(bb, i)) : null
    const className = isHeader
      ? 'px-3 py-2 bg-gray-100 font-semibold text-left border border-gray-300'
      : 'px-3 py-2 border border-gray-300'

    const Tag = isHeader ? 'th' : 'td'
    return (
      <Tag
        key={cellKey}
        {...cellAttrs}
        className={className + (cellAttrs.className ? ' ' + cellAttrs.className : '')}
        rowSpan={rowSpan > 1 ? rowSpan : undefined}
        colSpan={colSpan > 1 ? colSpan : undefined}
      >
        {content}
      </Tag>
    )
  }

  // Helper to render table rows
  const renderRow = (row: any, rowKey: number | string, isHeader = false) => {
    // Row structure: [Attr, [Cell]]
    if (!row || !Array.isArray(row)) return null
    const [rowAttr, cells] = row
    const rowAttrs = attrs(rowAttr)
    return (
      <tr key={rowKey} {...rowAttrs}>
        {Array.isArray(cells) ? cells.map((cell: any, i: number) => renderCell(cell, i, isHeader)) : null}
      </tr>
    )
  }

  const tableAttrs = attrs(a)
  const docId = useDocId()

  // Check if this table has a tbl: ID for interactive rendering
  let tableKey: string | undefined
  if (tableAttrs.id && tableAttrs.id.startsWith('tbl:')) {
    // Remove 'tbl:' prefix to get the table key (possibly with suffix like _1, _2)
    tableKey = tableAttrs.id.substring(4)

    console.log('[renderTable] Table with ID:', {
      tableId: tableAttrs.id,
      extractedTableKey: tableKey,
      docId: docId,
      hasDocId: !!docId
    })
  }

  // Build the static table content (used in both interactive and non-interactive modes)
  const staticTableContent = (
    <div className="overflow-x-auto">
      <table
        {...tableAttrs}
        className={'min-w-full border-collapse border border-gray-300 ' + (tableAttrs.className || '')}
      >
        {tableHead && Array.isArray(tableHead) && tableHead.length > 1 && Array.isArray(tableHead[1]) && tableHead[1].length > 0 ? (
          <thead>
            {tableHead[1].map((row: any, i: number) => renderRow(row, i, true))}
          </thead>
        ) : null}
        {Array.isArray(tableBodies) && tableBodies.length > 0 ? (
          <tbody>
            {tableBodies.map((tbody: any, tbodyIdx: number) => {
              // TableBody: [Attr, RowHeadColumns, [HeaderRow], [BodyRow]]
              if (!Array.isArray(tbody) || tbody.length < 4) return null
              const [, , headerRows, bodyRows] = tbody
              return (
                <React.Fragment key={tbodyIdx}>
                  {Array.isArray(headerRows) ? headerRows.map((row: any, i: number) => renderRow(row, `tbody-${tbodyIdx}-h-${i}`, true)) : null}
                  {Array.isArray(bodyRows) ? bodyRows.map((row: any, i: number) => renderRow(row, `tbody-${tbodyIdx}-b-${i}`, false)) : null}
                </React.Fragment>
              )
            })}
          </tbody>
        ) : null}
        {tableFoot && Array.isArray(tableFoot) && tableFoot.length > 1 && Array.isArray(tableFoot[1]) && tableFoot[1].length > 0 ? (
          <tfoot>
            {tableFoot[1].map((row: any, i: number) => renderRow(row, i, false))}
          </tfoot>
        ) : null}
      </table>
    </div>
  )

  const captionContent = captionInlines && captionInlines.length > 0 ? (
    <div className="text-sm text-gray-600 italic mt-2 text-center">
      {renderInlines(captionInlines)}
    </div>
  ) : null

  // If table has a key and docId, try to render as interactive
  if (tableKey && docId) {
    console.log('[renderTable] Rendering as interactive table candidate:', { tableKey, tableId: tableAttrs.id })
    return (
      <InteractiveTable
        key={key}
        tableId={tableAttrs.id}
        className="my-4"
        tableKey={tableKey}
        docId={docId}
        staticContent={staticTableContent}
        caption={captionContent}
      />
    )
  }

  // Regular table without interactive capability
  return (
    <div key={key} className="my-4 overflow-x-auto">
      {staticTableContent}
      {captionContent}
    </div>
  )
}
