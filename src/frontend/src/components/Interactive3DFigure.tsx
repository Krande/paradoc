import React from 'react'
import type { PandocBlock } from '../ast/types'

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

// IntersectionObserver only fires once we've mounted the placeholder
// and are sure the figure is on-screen, so a long page of 20+ 3D
// figures only spins up viewers as the user scrolls. `rootMargin`
// pre-loads slightly before the figure enters the viewport so the
// viewer is ready by the time it scrolls in.
const VIEWER_ROOT_MARGIN = '300px'

export function Interactive3DFigure({
  figureId,
  className,
  threeDKey,
  docId,
  content: _content,
  caption,
}: Interactive3DFigureProps) {
  const containerRef = React.useRef<HTMLDivElement | null>(null)
  // `mountViewer` flips on either when the user explicitly clicks the
  // load button OR when the figure scrolls into view. Once true we
  // never tear back down — switching back to the placeholder would
  // dispose the vendor viewer's GL context, defeating the cache.
  const [mountViewer, setMountViewer] = React.useState(false)
  // `showViewer` is the visible-state toggle; controls whether the
  // viewer's DOM is rendered. We keep both so the user can hide the
  // viewer without losing the loaded GLB (re-show is instant).
  const [showViewer, setShowViewer] = React.useState(false)

  React.useEffect(() => {
    if (!docId || !threeDKey) return
    const el = containerRef.current
    if (!el || typeof IntersectionObserver === 'undefined') {
      // No observer support → eager-load on mount as a fallback. This
      // also catches SSR / test environments.
      setMountViewer(true)
      setShowViewer(true)
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setMountViewer(true)
            setShowViewer(true)
            observer.disconnect()
            break
          }
        }
      },
      { rootMargin: VIEWER_ROOT_MARGIN, threshold: 0 },
    )
    observer.observe(el)
    return () => observer.disconnect()
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
      className={`${className} my-4 border border-dashed border-gray-300 rounded bg-gray-50 p-6 flex flex-col items-center justify-center text-center min-h-[180px]`}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        className="w-10 h-10 text-gray-400 mb-3"
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
      </svg>
      <p className="text-sm font-medium text-gray-700">3D model: {threeDKey}</p>
      {captionNode}
      <button
        onClick={() => {
          setMountViewer(true)
          setShowViewer(true)
        }}
        className="mt-3 inline-flex items-center px-3 py-1.5 rounded-md text-sm font-semibold bg-blue-600 text-white hover:bg-blue-700 transition cursor-pointer"
      >
        Load 3D viewer
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
