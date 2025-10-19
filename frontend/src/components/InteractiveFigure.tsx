import React from 'react'
import { PlotRenderer } from './PlotRenderer'
import type { PandocBlock } from '../ast/types'

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

  // Import renderBlock here to avoid circular dependency
  const { renderBlock } = require('../ast/render')

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
