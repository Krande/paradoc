import React from 'react'
import { PlotRenderer } from './PlotRenderer'
import type { PandocBlock } from '../ast/types'
import { renderBlock } from '../ast/render'
import { getPlotData, resolvePlotKey } from '../sections/store'

interface InteractiveFigureProps {
  figureId?: string
  className: string
  plotKey: string
  docId?: string
  content: PandocBlock[]
  caption?: React.ReactNode
}

export function InteractiveFigure({ figureId, className, plotKey, docId, content, caption }: InteractiveFigureProps) {
  const [showInteractive, setShowInteractive] = React.useState(false)
  const [isHovering, setIsHovering] = React.useState(false)
  // The key the plot data is stored under (the figure id may carry a `_N` suffix), or null when
  // the figure has no interactive data. Only the index is consulted: the plot's data itself is
  // fetched when the reader switches to interactive (or hovers, as a head start).
  const [resolvedKey, setResolvedKey] = React.useState<string | null>(null)
  const plotExists = resolvedKey !== null

  React.useEffect(() => {
    if (!docId || !plotKey) {
      setResolvedKey(null)
      return
    }
    let canceled = false
    const check = () => {
      resolvePlotKey(docId, plotKey)
        .then((k) => {
          if (!canceled) setResolvedKey(k ?? null)
        })
        .catch(() => {
          if (!canceled) setResolvedKey(null)
        })
    }
    check()

    // Plot data can arrive after mount (the WS relay; a plot index registered after the first
    // render). `plotKey: '*'` is a whole index being registered.
    const onStored = (event: Event) => {
      const d = (event as CustomEvent<{ docId: string; plotKey: string }>).detail
      if (d.docId !== docId) return
      if (d.plotKey === '*' || d.plotKey === plotKey || d.plotKey === plotKey.replace(/_\d+$/, '')) check()
    }
    window.addEventListener('paradoc:plot-data-stored', onStored)
    return () => {
      canceled = true
      window.removeEventListener('paradoc:plot-data-stored', onStored)
    }
  }, [docId, plotKey])

  // Start fetching the plot's data as soon as the reader shows interest in the figure.
  const prefetch = React.useCallback(() => {
    if (docId && resolvedKey) void getPlotData(docId, resolvedKey).catch(() => {})
  }, [docId, resolvedKey])

  // If no plot data exists, just render as static figure
  if (!plotExists) {
    return (
      <figure id={figureId} className={className}>
        {Array.isArray(content) ? content.map((bb, j) => renderBlock(bb, j)) : null}
        {caption && (
          <figcaption className="text-sm text-gray-600 italic mt-2">
            {caption}
          </figcaption>
        )}
      </figure>
    )
  }

  // Plot exists - render with interactive toggle
  return (
    <div
      className="relative group"
      onMouseEnter={() => {
        setIsHovering(true)
        prefetch()
      }}
      onMouseLeave={() => setIsHovering(false)}
      onTouchStart={prefetch}
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

      {/* Show either static figure or interactive plot */}
      {showInteractive ? (
        <div className="my-4">
          <PlotRenderer plotKey={resolvedKey ?? plotKey} docId={docId} />
          {caption && (
            <figcaption className="text-sm text-gray-600 italic mt-2">
              {caption}
            </figcaption>
          )}
        </div>
      ) : (
        <figure id={figureId} className={className}>
          {Array.isArray(content) ? content.map((bb, j) => renderBlock(bb, j)) : null}
          {caption && (
            <figcaption className="text-sm text-gray-600 italic mt-2">
              {caption}
            </figcaption>
          )}
        </figure>
      )}
    </div>
  )
}
