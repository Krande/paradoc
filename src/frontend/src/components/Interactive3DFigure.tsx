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

// Lazy-load the live viewer — pulls in the bundled adapy embed
// (~3 MiB), three.js, and the worker-cache wiring. Only mounted when
// the user flips to the Interactive tab; the Static path doesn't pay
// the import cost.
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
  // Match the InteractiveTable / InteractiveFigure idiom: hover-only
  // Static | Interactive segmented toggle in the top-right corner.
  // Default to Static so the page stays calm on first paint — the
  // big "Load interactive 3D viewer" button felt like a distraction
  // wherever a figure landed in the doc flow.
  const [showInteractive, setShowInteractive] = React.useState(false)
  // Once the user has opened Interactive once, keep the viewer mounted
  // so flipping back-and-forth is instant. Toggling Static just hides
  // it; we don't dispose the GL context until unmount.
  const [hasMounted, setHasMounted] = React.useState(false)
  // Toggle visibility. On desktop the hover state controls it — pointer
  // enters, toggle appears; pointer leaves, toggle hides. On mobile
  // (no hover) we fade it out after 2 s of idle so it stops covering
  // the embed's top-left toolbar; any scroll / tap brings it back.
  const [toggleVisible, setToggleVisible] = React.useState(false)
  const [posterUrl, setPosterUrl] = React.useState<string | undefined>(undefined)
  const hideTimerRef = React.useRef<number | null>(null)

  const revealToggle = React.useCallback(() => {
    setToggleVisible(true)
    if (hideTimerRef.current !== null) {
      window.clearTimeout(hideTimerRef.current)
    }
    // Touch users get an auto-hide so the toggle doesn't permanently
    // cover the adapy viewer's tree / info / simcontrols buttons.
    // Desktop's `onMouseLeave` will pre-empt this with an instant
    // hide; the timeout is the mobile-friendly fallback.
    hideTimerRef.current = window.setTimeout(() => {
      setToggleVisible(false)
      hideTimerRef.current = null
    }, 2200)
  }, [])

  React.useEffect(() => () => {
    if (hideTimerRef.current !== null) {
      window.clearTimeout(hideTimerRef.current)
    }
  }, [])

  // Re-reveal on page scroll so the user can find the toggle again
  // after it auto-hides. Scoped to window because the user might
  // scroll outside the figure's bounds while still wanting to flip
  // back to Static.
  React.useEffect(() => {
    if (!hasMounted) return
    const onScroll = () => revealToggle()
    window.addEventListener('scroll', onScroll, {passive: true})
    return () => window.removeEventListener('scroll', onScroll)
  }, [hasMounted, revealToggle])

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

  const captionNode = caption ? (
    <figcaption className="text-sm text-gray-600 italic mt-2">{caption}</figcaption>
  ) : null

  const staticView = (
    <figure
      id={figureId}
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
    </figure>
  )

  if (!docId || !threeDKey) return staticView

  return (
    <div
      className="relative group my-4"
      onMouseEnter={revealToggle}
      onMouseLeave={() => setToggleVisible(false)}
    >
      {/* Segmented toggle — mirrors InteractiveTable/InteractiveFigure
          so users see one consistent control across every kind of
          embedded artefact. Auto-hides on idle so it stops covering
          the embed's top-left toolbar on mobile; reappears on hover,
          page scroll, or touch on the static poster (NOT the live
          viewer — orbiting the 3D model would otherwise keep
          summoning the toggle back over the adapy toolbar). */}
      <div
        className={`absolute top-2 right-2 bg-white shadow-lg rounded-md border border-gray-200 p-2 z-20 flex gap-2 transition-opacity duration-200 ${
          toggleVisible ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
      >
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
            onClick={() => {
              setShowInteractive(true)
              setHasMounted(true)
            }}
            className={`px-3 py-1 rounded text-sm cursor-pointer transition-colors ${
              showInteractive
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            Interactive
          </button>
      </div>

      {/* Keep both panes in the DOM once Interactive has mounted, but
          hide the inactive one with `display: none`. The viewer keeps
          its GL context warm; toggling back is instant.

          `onTouchStart` is scoped to the Static pane only so touches
          on the live 3D viewer (camera orbit on mobile) don't reveal
          the toggle. Page-scroll still reveals it from anywhere via
          the window listener in the `revealToggle` effect. */}
      <div
        style={{ display: showInteractive ? 'none' : 'block' }}
        onTouchStart={revealToggle}
      >
        {staticView}
      </div>
      {hasMounted && (
        <div style={{ display: showInteractive ? 'block' : 'none' }}>
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
          {/* Caption underneath the viewer too — the renderer wraps
              its own canvas without one. */}
          {captionNode}
        </div>
      )}
    </div>
  )
}
