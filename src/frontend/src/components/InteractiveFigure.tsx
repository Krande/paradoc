import React from 'react'
import { PlotRenderer } from './PlotRenderer'
import type { PandocBlock } from '../ast/types'
import { renderBlock } from '../ast/render'
import { getPlotData } from '../sections/store'

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
  const [plotExists, setPlotExists] = React.useState(false)

  // Check if plot data exists for this plot key (handle suffixes like _1, _2)
  React.useEffect(() => {
    if (!docId || !plotKey) {
      setPlotExists(false)
      return
    }

    // Try to find plot data - first try the exact key, then try without suffix
    const checkPlotExists = async () => {
      // Try exact match first
      let data = await getPlotData(docId, plotKey)
      if (data) {
        console.log('[InteractiveFigure] Found plot data for key:', plotKey)
        setPlotExists(true)
        return
      }

      // If plotKey has a suffix like _1, _2, try the base key
      const underscoreIndex = plotKey.lastIndexOf('_')
      if (underscoreIndex > 0) {
        const suffix = plotKey.substring(underscoreIndex + 1)
        if (/^\d+$/.test(suffix)) {
          // Has numeric suffix, try base key
          const baseKey = plotKey.substring(0, underscoreIndex)
          data = await getPlotData(docId, baseKey)
          if (data) {
            console.log('[InteractiveFigure] Found plot data for base key:', baseKey, '(original:', plotKey, ')')
            setPlotExists(true)
            return
          }
        }
      }

      console.log('[InteractiveFigure] No plot data found for key:', plotKey)
      setPlotExists(false)
    }

    checkPlotExists()

    // Listen for plot data being stored and re-check
    const handlePlotDataStored = (event: Event) => {
      const customEvent = event as CustomEvent<{ docId: string; plotKey: string }>
      // Check if this event is relevant to our component
      if (customEvent.detail.docId === docId) {
        // Check if the stored plot key matches ours (with or without suffix)
        if (customEvent.detail.plotKey === plotKey) {
          checkPlotExists()
        } else {
          // Check if our plotKey has a suffix and the base matches
          const underscoreIndex = plotKey.lastIndexOf('_')
          if (underscoreIndex > 0) {
            const suffix = plotKey.substring(underscoreIndex + 1)
            if (/^\d+$/.test(suffix)) {
              const baseKey = plotKey.substring(0, underscoreIndex)
              if (customEvent.detail.plotKey === baseKey) {
                checkPlotExists()
              }
            }
          }
        }
      }
    }

    window.addEventListener('paradoc:plot-data-stored', handlePlotDataStored)

    return () => {
      window.removeEventListener('paradoc:plot-data-stored', handlePlotDataStored)
    }
  }, [docId, plotKey])

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

      {/* Show either static figure or interactive plot */}
      {showInteractive ? (
        <div className="my-4">
          <PlotRenderer plotKey={plotKey} docId={docId} />
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
