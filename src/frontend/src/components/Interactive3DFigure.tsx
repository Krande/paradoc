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
  // The static-figure branch existed for WS / pandoc-DOCX hosts where
  // there was a real PNG fallback alongside the GLB. The static-web
  // exporter ships only the GLB, so the markdown `MISSING_3D_IMAGE.png`
  // placeholder would otherwise render as a broken image while we
  // waited for `getThreeDMeta` to resolve (and again forever in
  // static-web mode if the meta probe failed for any reason).
  //
  // Default behavior: if the host gave us a `threeDKey`, mount the
  // ThreeDRenderer immediately and let *it* surface a loading state
  // / error state. We still keep the runtime toggle so static-figure
  // hosts can opt back in via the hover menu.
  const [showInteractive, setShowInteractive] = React.useState(true)
  const [isHovering, setIsHovering] = React.useState(false)
  // Optimistically assume the GLB exists when a threeDKey is provided
  // — the bundle / docstore is responsible for actually shipping it.
  const [exists, setExists] = React.useState<boolean>(!!threeDKey)

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
      if (!canceled && meta === undefined) {
        // Only downgrade to "not found" when the lookup explicitly
        // returned undefined; transports that don't know how to probe
        // ahead of time (most static hosts) keep us in the optimistic
        // state so the renderer mounts and fetches the binary.
        setExists(false)
      }
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
