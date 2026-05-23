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
  // Bound the interactive viewer to the static poster's rendered
  // dimensions on first measurement so it doesn't expand the figure's
  // visual footprint on wide desktops. After that, a custom pointer-
  // event resize handle in the bottom-right corner (outside the embed's
  // canvas) lets the user grow / shrink the viewer independently of
  // the poster. CSS `resize: both` won't do: its drag handle is
  // always inside the box, which on this layout overlaps the adapy
  // viewer's orientation gizmo + gets pointer-events consumed by the
  // embed's input handler, so dragging never reaches the wrapper.
  const posterRef = React.useRef<HTMLElement | null>(null)
  const [viewerSize, setViewerSize] = React.useState<{width: number; height: number} | null>(null)
  // Locks viewerSize once the user has dragged the resize handle so
  // subsequent posterRef reflows don't snap their custom size back to
  // the auto-measured value.
  const userResizedRef = React.useRef(false)
  const resizeStartRef = React.useRef<
    {pointerId: number; startX: number; startY: number; baseW: number; baseH: number} | null
  >(null)

  React.useEffect(() => {
    const el = posterRef.current
    if (!el) return
    const update = () => {
      if (userResizedRef.current) return
      const rect = el.getBoundingClientRect()
      // Keep updating until the user takes over via the resize handle.
      // The previous ``prev ?? …`` seed-once logic locked viewerSize to
      // the figure's *placeholder* height (~200 px — dashed box + icon
      // + caption) because that's what was rendered the first time the
      // effect ran, before the poster image had loaded. The wrapper
      // then ended up shorter than mountViewer's 400 px min-height
      // floor, the canvas overflowed, and the intermediate
      // ``overflow: hidden`` div clipped its bottom — taking the beam
      // tip with it.
      if (rect.width > 0 && rect.height > 0) {
        setViewerSize({width: Math.round(rect.width), height: Math.round(rect.height)})
      }
    }
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [posterUrl])

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

  const onResizeStart = React.useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!viewerSize) return
    // Lock auto-measurement so the user's drag isn't fought by the
    // ResizeObserver loop that's watching the posterRef figure.
    userResizedRef.current = true
    // Capture so subsequent move / up events fire on the handle even
    // when the pointer leaves it. This is what makes pointer-event
    // resize feel native.
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    resizeStartRef.current = {
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      baseW: viewerSize.width,
      baseH: viewerSize.height,
    }
    e.preventDefault()
    e.stopPropagation()
  }, [viewerSize])

  const onResizeMove = React.useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    const s = resizeStartRef.current
    if (!s || s.pointerId !== e.pointerId) return
    const dx = e.clientX - s.startX
    const dy = e.clientY - s.startY
    setViewerSize({
      width: Math.max(320, Math.round(s.baseW + dx)),
      height: Math.max(240, Math.round(s.baseH + dy)),
    })
  }, [])

  const onResizeEnd = React.useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    const s = resizeStartRef.current
    if (!s || s.pointerId !== e.pointerId) return
    try {
      ;(e.target as HTMLElement).releasePointerCapture(e.pointerId)
    } catch {/* already released */}
    resizeStartRef.current = null
  }, [])

  const captionNode = caption ? (
    <figcaption className="text-sm text-gray-600 italic mt-2">{caption}</figcaption>
  ) : null

  const staticView = (
    <figure
      id={figureId}
      ref={posterRef as React.RefObject<HTMLElement>}
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
      {/* Tiny always-on "leaf" handle in the top-right corner, outside
          the embed viewer's interactive area. On mobile the toggle's
          auto-hide stranded users with no obvious way back to Static
          (page-scroll listeners are flaky inside a scrollable doc
          frame, and we deliberately don't reveal on touches inside
          the live 3D viewer). The leaf is the fallback affordance:
          always visible, single tap pulls the toggle back. Hides
          itself when the toggle is up so they don't visually fight.
          Positioned slightly above + outside the figure's frame
          (`-top-3 -right-3`) so it doesn't overlap the embed's
          top-right inset. */}
      <button
        type="button"
        aria-label="Show static / interactive toggle"
        onClick={(e) => {
          e.stopPropagation()
          revealToggle()
        }}
        className={`absolute -top-3 -right-3 w-7 h-7 rounded-full bg-blue-600 text-white shadow-md flex items-center justify-center text-xs cursor-pointer z-30 transition-opacity duration-200 ${
          toggleVisible ? 'opacity-0 pointer-events-none' : 'opacity-90 hover:opacity-100'
        }`}
        title="Show Static | Interactive toggle"
      >
        {/* Chevron-down hint: tap to drop the toggle down. */}
        <svg viewBox="0 0 12 12" className="w-3 h-3" fill="currentColor" aria-hidden="true">
          <path d="M2 4l4 4 4-4H2z" />
        </svg>
      </button>

      {/* Segmented toggle — mirrors InteractiveTable/InteractiveFigure
          so users see one consistent control across every kind of
          embedded artefact. Auto-hides on idle so it stops covering
          the embed's top-left toolbar on mobile; reappears on hover,
          page scroll, leaf-tap, or touch on the static poster (NOT
          the live viewer — orbiting the 3D model would otherwise
          keep summoning the toggle back over the adapy toolbar). */}
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
        <div
          className="relative mx-auto"
          style={{
            width: viewerSize ? `${viewerSize.width}px` : '100%',
            height: viewerSize ? `${viewerSize.height}px` : 'auto',
            maxWidth: '100%',
            minWidth: '320px',
            minHeight: '240px',
            display: showInteractive ? 'block' : 'none',
          }}
        >
          {/* Bounded to the static poster's rendered dimensions on
              first paint; resized below via the bottom-right pointer
              handle. The embed's internal ResizeObserver picks up
              the new container size and re-renders the canvas at
              that resolution. */}
          <div className="w-full h-full overflow-hidden">
            <React.Suspense
              fallback={
                <div className="border border-gray-200 rounded bg-gray-50 p-6 text-sm text-gray-500 text-center w-full h-full flex items-center justify-center">
                  Loading 3D viewer…
                </div>
              }
            >
              <ThreeDRenderer
                threeDKey={threeDKey}
                docId={docId}
                caption={typeof caption === 'string' ? caption : undefined}
                // Fill the resizable wrapper; opt out of the
                // renderer's default 4:3 aspect ratio so the
                // wrapper's explicit width/height drive the canvas.
                style={{
                  width: '100%',
                  height: '100%',
                  aspectRatio: 'auto',
                }}
              />
            </React.Suspense>
          </div>

          {/* Resize handle — anchored outside the viewer's bottom-right
              corner so it doesn't sit on top of the adapy embed's
              orientation gizmo and doesn't get its pointer events
              swallowed by the embed's input handler. `touch-none`
              prevents the page-scroll gesture from cancelling the
              drag on mobile. */}
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize 3D viewer"
            title="Drag to resize"
            onPointerDown={onResizeStart}
            onPointerMove={onResizeMove}
            onPointerUp={onResizeEnd}
            onPointerCancel={onResizeEnd}
            className="absolute -bottom-3 -right-3 w-6 h-6 rounded-full bg-blue-600 text-white shadow-md flex items-center justify-center cursor-nwse-resize z-30 touch-none opacity-90 hover:opacity-100"
          >
            <svg viewBox="0 0 12 12" className="w-3 h-3" fill="currentColor" aria-hidden="true">
              <path d="M11 1v3L4 11H1V8l7-7h3z" />
            </svg>
          </div>

          {/* Caption underneath the viewer too — the renderer wraps
              its own canvas without one. */}
          {captionNode}
        </div>
      )}
    </div>
  )
}
