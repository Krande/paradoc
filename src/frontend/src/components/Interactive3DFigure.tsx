import React from 'react'
import type { PandocBlock } from '../ast/types'
import { renderBlock } from '../ast/render'
import { getAssetTransport } from '../transport'

interface Interactive3DFigureProps {
  figureId?: string
  className: string
  threeDKey: string
  docId?: string
  content: PandocBlock[]
  caption?: React.ReactNode
}

const ThreeDRenderer = React.lazy(() =>
  import('./ThreeDRenderer').then((mod) => ({ default: mod.ThreeDRenderer })),
)

export function Interactive3DFigure({
  figureId,
  className,
  threeDKey,
  docId,
  content,
  caption,
}: Interactive3DFigureProps) {
  // Default to the interactive viewer once we've confirmed the GLB is
  // available. The static-figure branch existed for WS / pandoc-DOCX
  // hosts where there was a real PNG fallback alongside the GLB; the
  // static-web exporter ships only the GLB so the markdown
  // `MISSING_3D_IMAGE.png` placeholder would render as a broken
  // image until the user found the hover-only 3D toggle.
  const [showInteractive, setShowInteractive] = React.useState(true)
  const [isHovering, setIsHovering] = React.useState(false)
  const [exists, setExists] = React.useState(false)

  React.useEffect(() => {
    if (!docId || !threeDKey) {
      setExists(false)
      return
    }
    const transport = getAssetTransport()
    if (!transport) return

    let canceled = false
    const check = async () => {
      const meta = await transport.getThreeDMeta(docId, threeDKey)
      if (!canceled) setExists(!!meta)
    }
    check()

    const handleStored = (event: Event) => {
      const detail = (event as CustomEvent<{ docId: string; key: string }>).detail
      if (detail.docId === docId && detail.key === threeDKey) check()
    }
    window.addEventListener('paradoc:3d-data-stored', handleStored)
    return () => {
      canceled = true
      window.removeEventListener('paradoc:3d-data-stored', handleStored)
    }
  }, [docId, threeDKey])

  const staticFigure = (
    <figure id={figureId} className={className}>
      {Array.isArray(content) ? content.map((bb, j) => renderBlock(bb, j)) : null}
      {caption && (
        <figcaption className="text-sm text-gray-600 italic mt-2">{caption}</figcaption>
      )}
    </figure>
  )

  if (!exists) return staticFigure

  return (
    <div
      className="relative group"
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
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
            3D
          </button>
        </div>
      )}

      {showInteractive && docId ? (
        <div className="my-4">
          <React.Suspense fallback={<div className="text-sm text-gray-500">Loading 3D viewer…</div>}>
            <ThreeDRenderer
              threeDKey={threeDKey}
              docId={docId}
              caption={typeof caption === 'string' ? caption : undefined}
            />
          </React.Suspense>
          {caption && (
            <figcaption className="text-sm text-gray-600 italic mt-2">{caption}</figcaption>
          )}
        </div>
      ) : (
        staticFigure
      )}
    </div>
  )
}
