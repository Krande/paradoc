import React from 'react'
import type { PandocBlock } from '../ast/types'
import { getAssetTransport } from '../transport'
import { AsyncImage } from '../ast/inlineRenderers'

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
  content: _content,
  caption,
}: Interactive3DFigureProps) {
  const containerRef = React.useRef<HTMLDivElement | null>(null)
  // `mountViewer` flips on when the user explicitly clicks the load
  // button. Auto-mounting on intersection was *too* eager — a long
  // page still ends up with 20+ live viewers as the user scrolls. The
  // poster PNG gives them a real preview; only mount the live viewer
  // when they actually want to interact with it.
  const [mountViewer, setMountViewer] = React.useState(false)
  // `showViewer` is the visible-state toggle; once mounted, the user
  // can hide it without disposing the GL context (re-show is instant).
  const [showViewer, setShowViewer] = React.useState(false)
  const [posterUrl, setPosterUrl] = React.useState<string | undefined>(undefined)

  React.useEffect(() => {
    if (!docId || !threeDKey) return
    const transport = getAssetTransport()
    if (!transport) return
    let canceled = false
    transport.getThreeDMeta(docId, threeDKey).then((meta) => {
      if (canceled) return
      setPosterUrl(meta?.imageUrl)
    }).catch(() => {})
    return () => {
      canceled = true
    }
  }, [docId, threeDKey])

  // Caption rendered as a string when possible — falls back to the
  // raw React nodes (e.g. with formatting) inside <figcaption>.
  const captionNode = caption ? (
    <figcaption className="text-sm text-gray-600 italic mt-2">{caption}</figcaption>
  ) : null

  const placeholder = (
    <figure
      id={figureId}
      ref={containerRef}
      className={`${className} my-4 border border-gray-200 rounded bg-gray-50 p-3 flex flex-col items-center text-center`}
    >
      {posterUrl ? (
        // AsyncImage handles `/api/...` URLs via authedFetch + blob URL
        // so the bearer token reaches paradoc-serve's /3d/{key}/poster
        // endpoint. A plain <img src=…> would 401 in REST mode because
        // browsers don't send Authorization headers on image loads.
        <AsyncImage
          src={posterUrl}
          alt={typeof caption === 'string' ? caption : `3D preview: ${threeDKey}`}
          title=""
          className="max-w-full max-h-[420px] rounded border border-gray-200 bg-white"
          imgAttrs={{ loading: 'lazy' }}
        />
      ) : (
        <div className="w-full max-h-[420px] flex flex-col items-center justify-center py-10 text-gray-400 border border-dashed border-gray-300 rounded">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="w-10 h-10 mb-2"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
          </svg>
          <p className="text-sm font-medium text-gray-600">3D model: {threeDKey}</p>
        </div>
      )}
      {captionNode}
      <button
        onClick={() => {
          setMountViewer(true)
          setShowViewer(true)
        }}
        className="mt-3 inline-flex items-center px-3 py-1.5 rounded-md text-sm font-semibold bg-blue-600 text-white hover:bg-blue-700 transition cursor-pointer"
      >
        Load interactive 3D viewer
      </button>
    </figure>
  )

  if (!docId || !threeDKey) return placeholder

  return (
    <div ref={containerRef} className="relative group my-4">
      {/* Hover toggle: show / hide viewer without disposing it once mounted. */}
      <div className="absolute top-2 right-2 z-10 opacity-0 group-hover:opacity-100 transition">
        <button
          onClick={() => setShowViewer((v) => !v)}
          className="bg-white shadow-md rounded-md border border-gray-200 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-100 cursor-pointer"
        >
          {showViewer ? 'Hide 3D' : 'Show 3D'}
        </button>
      </div>

      {mountViewer && showViewer ? (
        <React.Suspense
          fallback={
            <div className="border border-gray-200 rounded bg-gray-50 p-6 text-sm text-gray-500 text-center min-h-[180px] flex items-center justify-center">
              Loading 3D viewer…
            </div>
          }
        >
          <ThreeDRenderer
            threeDKey={threeDKey}
            docId={docId}
            caption={typeof caption === 'string' ? caption : undefined}
          />
        </React.Suspense>
      ) : (
        placeholder
      )}
      {/* Render caption underneath the viewer too (the renderer wraps
          its own canvas without one). */}
      {mountViewer && showViewer && captionNode}
    </div>
  )
}
