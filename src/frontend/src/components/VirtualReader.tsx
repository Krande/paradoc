import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import type { DocManifest, SectionBundle, Header } from '../ast/types'
import { renderBlock, RenderWithDocId } from '../ast/render'
import { predictivePrefetch } from '../sections/store'
import { calculateHeadingNumbers } from '../ast/headingNumbers'
import { clampZoom, usePageViewStore } from '../store/pageViewStore'
import { PagedSection, PAGE_STRIDE_PX, PAGE_WIDTH_PX } from './PagedSection'
import { collectIds, estimatePages, mountTarget } from './progressiveMount'
import { REVEAL_EVENT } from './readerNav'
import type { RevealDetail } from './readerNav'

/** Height of one estimated page of the scroll (web) layout, px. */
const SCROLL_PAGE_PX = 1100

interface Props {
  docId: string
  manifest: DocManifest
  sections: Record<string, SectionBundle>
}

export function VirtualReader({ docId, manifest, sections }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [visibleIndex, setVisibleIndex] = useState(0)

  // Filter manifest to only include H1 sections (level === 1) which have actual content bundles
  // All headers are in the manifest for TOC, but only H1s have section content
  const h1Sections = useMemo(() => manifest.sections.filter(s => s.level === 1), [manifest.sections])

  // Build ordered list of rendered items with fallback placeholders
  const items = useMemo(() => h1Sections.map((s) => sections[s.id] || null), [h1Sections, sections])

  // Calculate heading numbers for all sections (including H2-H6 for TOC)
  const headingNumbers = useMemo(() => calculateHeadingNumbers(manifest.sections), [manifest.sections])

  useEffect(() => {
    if (!manifest) return
    // Use h1Sections for prefetching since those are the only ones with content
    const visibleH1 = h1Sections[visibleIndex]
    if (visibleH1) {
      const originalIndex = manifest.sections.findIndex(s => s.id === visibleH1.id)
      predictivePrefetch(docId, manifest, originalIndex)
    }
  }, [docId, manifest, h1Sections, visibleIndex])

  useEffect(() => {
    const root = containerRef.current
    if (!root) return
    const headings = Array.from(root.querySelectorAll('[data-section-index]')) as HTMLElement[]
    const obs = new IntersectionObserver((entries) => {
      let best = { i: visibleIndex, ratio: 0 }
      for (const e of entries) {
        const i = parseInt(e.target.getAttribute('data-section-index') || '0', 10)
        if (e.isIntersecting && e.intersectionRatio > best.ratio) {
          best = { i, ratio: e.intersectionRatio }
        }
      }
      if (best.ratio > 0) setVisibleIndex(best.i)
    }, { root, rootMargin: '0px', threshold: [0, 0.25, 0.5, 0.75, 1] })

    headings.forEach((el) => obs.observe(el))
    return () => obs.disconnect()
  }, [items])

  // Page view: sheets per section, numbered straight through the document.
  const pageView = usePageViewStore((s) => s.enabled)

  // Progressive mounting: sections [0, mounted) are rendered, the rest are placeholders sized from
  // an estimate (progressiveMount.ts). Mounting follows the reader's scroll, in document order.
  const [mounted, setMounted] = useState(1)
  const mountedRef = useRef(mounted)
  mountedRef.current = mounted
  const estPages = useMemo(
    () => h1Sections.map((s) => estimatePages(sections[s.id]?.doc?.blocks ?? [])),
    [h1Sections, sections],
  )
  const [pageCounts, setPageCounts] = useState<Record<number, number>>({})
  const setPageCount = useCallback(
    (i: number, n: number) => setPageCounts((prev) => (prev[i] === n ? prev : { ...prev, [i]: n })),
    [],
  )
  const firstPages = useMemo(() => {
    const out: number[] = []
    let next = 1
    h1Sections.forEach((_, i) => {
      out.push(next)
      next += pageCounts[i] ?? estPages[i] ?? 1
    })
    return out
  }, [h1Sections, pageCounts, estPages])

  // Sheet zoom: the stored zoom, or fit-to-width (at most 100 %) from the reader's inner width.
  const zoom = usePageViewStore((s) => s.zoom)
  const setZoom = usePageViewStore((s) => s.setZoom)
  const [fit, setFit] = useState(1)
  useEffect(() => {
    const root = containerRef.current
    if (!root || !pageView) return
    const measure = () => {
      const cs = getComputedStyle(root)
      const inner = root.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)
      setFit(Math.min(1, Math.max(0.1, inner / PAGE_WIDTH_PX)))
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(root)
    return () => ro.disconnect()
  }, [pageView])
  const scale = pageView ? (zoom ?? fit) : 1

  // Keep the reading position when the zoom changes: everything scales about the top, so the
  // scroll offsets scale with it.
  const lastScale = useRef(scale)
  useLayoutEffect(() => {
    const root = containerRef.current
    const prev = lastScale.current
    lastScale.current = scale
    if (!root || prev === scale) return
    const k = scale / prev
    root.scrollTop = root.scrollTop * k
    root.scrollLeft = root.scrollLeft * k
  }, [scale])

  // Two-finger pinch zooms the sheets. The browser's own pinch cannot zoom out past the device
  // width, which is exactly what a phone needs to see a whole sheet, so it is handled here
  // (touch-action below hands pinch to us and keeps one-finger panning native).
  const scaleRef = useRef(scale)
  scaleRef.current = scale
  useEffect(() => {
    const root = containerRef.current
    if (!root || !pageView) return
    let start: { d: number; z: number } | null = null
    let frame = 0
    const dist = (t: TouchList) => Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY)
    const onStart = (e: TouchEvent) => {
      if (e.touches.length === 2) start = { d: dist(e.touches), z: scaleRef.current }
    }
    const onMove = (e: TouchEvent) => {
      if (!start || e.touches.length !== 2) return
      e.preventDefault()
      const z = clampZoom((start.z * dist(e.touches)) / start.d)
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => setZoom(z))
    }
    const onEnd = (e: TouchEvent) => {
      if (e.touches.length < 2) start = null
    }
    root.addEventListener('touchstart', onStart, { passive: true })
    root.addEventListener('touchmove', onMove, { passive: false })
    root.addEventListener('touchend', onEnd, { passive: true })
    root.addEventListener('touchcancel', onEnd, { passive: true })
    return () => {
      cancelAnimationFrame(frame)
      root.removeEventListener('touchstart', onStart)
      root.removeEventListener('touchmove', onMove)
      root.removeEventListener('touchend', onEnd)
      root.removeEventListener('touchcancel', onEnd)
    }
  }, [pageView, setZoom])

  // Mount whatever has scrolled within reach: every placeholder whose top is above the bottom of
  // the viewport plus a look-ahead margin. Runs after each commit (a mounted section changes the
  // layout) and on scroll, at most once a frame, and one step at a time so each step paints.
  const checkFrame = useRef(0)
  const checkMount = useCallback(() => {
    if (checkFrame.current) return
    checkFrame.current = requestAnimationFrame(() => {
      checkFrame.current = 0
      const root = containerRef.current
      const m = mountedRef.current
      if (!root || m >= h1Sections.length) return
      const r = root.getBoundingClientRect()
      const coverBottom = r.bottom + Math.max(600, root.clientHeight * 1.5)
      const tops: number[] = []
      for (let i = m; i < h1Sections.length; i++) {
        const el = root.querySelector(`[data-section-index="${i}"]`)
        if (!el) break
        const top = el.getBoundingClientRect().top - coverBottom
        tops.push(top)
        if (top >= 0) break
      }
      const target = mountTarget(m, tops)
      if (target <= m) return
      // Filling in below the frontier: one section per step, so the first lines paint early and
      // no single task builds more than one section. A jump past the frontier (it is above the
      // viewport) mounts everything up to what is on screen at once.
      const frontierAbove = tops[0] + coverBottom < r.top
      setMounted(frontierAbove ? target : m + 1)
    })
  }, [h1Sections.length])
  useEffect(() => {
    // After the commit has painted: a timer, not a frame, so the browser gets to paint first.
    const t = window.setTimeout(checkMount, 0)
    return () => window.clearTimeout(t)
  }, [mounted, pageCounts, scale, pageView, checkMount])
  useEffect(() => {
    const root = containerRef.current
    if (!root) return
    root.addEventListener('scroll', checkMount, { passive: true })
    window.addEventListener('resize', checkMount)
    return () => {
      root.removeEventListener('scroll', checkMount)
      window.removeEventListener('resize', checkMount)
      cancelAnimationFrame(checkFrame.current)
      checkFrame.current = 0
    }
  }, [checkMount])

  // Navigation to an anchor in a section not rendered yet (cross-reference, TOC sub-heading,
  // search, print): mount every section up to and including it. Ids are looked up per section,
  // and a section's id set is built only when a reveal needs it (keyed by the bundle object, so a
  // section re-sent by the live view is re-indexed).
  const idSets = useRef(new WeakMap<SectionBundle, Set<string>>())
  useEffect(() => {
    const sectionOf = (id: string): number => {
      for (let i = 0; i < h1Sections.length; i++) {
        const s = h1Sections[i]
        if (s.id === id) return i
        const bundle = sections[s.id]
        if (!bundle) continue
        let ids = idSets.current.get(bundle)
        if (!ids) {
          ids = collectIds(bundle.doc?.blocks)
          idSets.current.set(bundle, ids)
        }
        if (ids.has(id)) return i
      }
      return -1
    }
    const onReveal = (e: Event) => {
      const d = (e as CustomEvent<RevealDetail>).detail || {}
      const want = d.all ? h1Sections.length : d.id ? sectionOf(d.id) + 1 : 0
      if (want > mountedRef.current) setMounted(want)
    }
    // A browser print of the reader prints what is in the DOM: render it all first.
    const onPrint = () => {
      if (mountedRef.current < h1Sections.length) flushSync(() => setMounted(h1Sections.length))
    }
    window.addEventListener(REVEAL_EVENT, onReveal)
    window.addEventListener('beforeprint', onPrint)
    return () => {
      window.removeEventListener(REVEAL_EVENT, onReveal)
      window.removeEventListener('beforeprint', onPrint)
    }
  }, [h1Sections, sections])

  return (
    <RenderWithDocId docId={docId}>
      <div
        ref={containerRef}
        className={`flex-1 overflow-auto overscroll-contain ${pageView ? 'px-4 py-2 bg-gray-200 dark:bg-gray-950' : 'p-6'}`}
        style={pageView ? { touchAction: 'pan-x pan-y' } : undefined}
        data-search-root
      >
        <div className={pageView ? 'w-max min-w-full' : 'max-w-none w-full'}>
          {h1Sections.map((s, i) => {
            const bundle = sections[s.id]
            if (i >= mounted) {
              // Not reached yet: a placeholder of about the section's height, so the scrollbar and
              // the jump-ahead check above see roughly the document's real length.
              const h = pageView ? estPages[i] * PAGE_STRIDE_PX * scale : estPages[i] * SCROLL_PAGE_PX
              return (
                <section
                  key={s.id}
                  id={s.id}
                  data-section-index={i}
                  data-section-placeholder=""
                  className={pageView ? 'scroll-mt-14 mx-auto my-6' : 'my-6 scroll-mt-14'}
                  style={pageView ? { height: `${h}px`, width: `${PAGE_WIDTH_PX * scale}px` } : { height: `${h}px` }}
                >
                  <Skeleton title={s.title} pulse={false} />
                </section>
              )
            }
            const body = bundle ? (
              <Section blockKey={s.id} bundle={bundle} headingNumbers={headingNumbers} />
            ) : (
              <Skeleton title={s.title} />
            )
            if (pageView) {
              // No content-visibility here: pagination measures every block, and a skipped
              // subtree has no layout to measure.
              return (
                <section key={s.id} id={s.id} data-section-index={i} className="scroll-mt-14">
                  <PagedSection index={i} firstPage={firstPages[i]} onPageCount={setPageCount} scale={scale}>
                    {body}
                  </PagedSection>
                </section>
              )
            }
            return (
              <section
                key={s.id}
                id={s.id}
                data-section-index={i}
                // `auto`: once a section has rendered, the browser keeps its real height instead of
                // snapping back to the 800px placeholder, so positions below it stop drifting.
                style={{ containIntrinsicSize: 'auto 1px auto 800px' as any }}
                className="content-visibility-auto my-6 scroll-mt-14"
              >
                {body}
              </section>
            )
          })}
        </div>
      </div>
      {pageView && <ZoomControls scale={scale} fitted={zoom === null} onZoom={setZoom} />}
    </RenderWithDocId>
  )
}

const ZOOM_STEPS = [0.25, 0.33, 0.5, 0.67, 0.75, 0.9, 1, 1.25, 1.5, 2, 3]

/** −, fit / percentage, + for the A4 sheets. Bottom-right, out of the way of the text. */
function ZoomControls({ scale, fitted, onZoom }: { scale: number; fitted: boolean; onZoom: (z: number | null) => void }) {
  const down = () => onZoom([...ZOOM_STEPS].reverse().find((z) => z < scale - 0.005) ?? ZOOM_STEPS[0])
  const up = () => onZoom(ZOOM_STEPS.find((z) => z > scale + 0.005) ?? ZOOM_STEPS[ZOOM_STEPS.length - 1])
  const btn =
    'cursor-pointer px-2.5 py-1.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800'
  return (
    <div className="fixed bottom-4 right-4 z-30 flex items-stretch rounded-md bg-white/95 dark:bg-gray-900/95 shadow-md ring-1 ring-black/10 dark:ring-white/10 divide-x divide-gray-200 dark:divide-gray-700 select-none">
      <button type="button" className={btn} onClick={down} aria-label="Zoom out" title="Zoom out">−</button>
      <button
        type="button"
        className={`${btn} min-w-[4.5rem] tabular-nums`}
        onClick={() => onZoom(fitted ? 1 : null)}
        aria-label={fitted ? 'Actual size' : 'Fit page to width'}
        title={fitted ? 'Fitted to width (click for 100 %)' : 'Click to fit the page to the width'}
      >
        {fitted ? 'Fit' : `${Math.round(scale * 100)} %`}
      </button>
      <button type="button" className={btn} onClick={up} aria-label="Zoom in" title="Zoom in">+</button>
    </div>
  )
}

// Memoised: its props (the section's bundle, id and the document's heading numbers) only change
// when the content does. The reader re-renders on scroll position and on every page-count change,
// and without this each of those rendered every block of every section again -- every figure and
// table of a large report, on a single scroll or resize.
const Section = React.memo(function Section({ bundle, blockKey, headingNumbers }: { bundle: SectionBundle, blockKey: string, headingNumbers: Map<string, any> }) {
  return (
    <div>
      {bundle.doc.blocks.map((b, i) => {
        // Check if this block is a header and get its numbering
        let headingNumber
        if (b.t === 'Header') {
          const [, attrs] = (b as Header).c
          const headerId = typeof attrs === 'object' && attrs && 'id' in attrs ? attrs.id : (Array.isArray(attrs) && attrs[0] ? attrs[0] : undefined)
          if (headerId) {
            headingNumber = headingNumbers.get(headerId)
          }
        }
        return renderBlock(b, i, headingNumber)
      })}
    </div>
  )
})

function Skeleton({ title, pulse = true }: { title: string; pulse?: boolean }) {
  return (
    <div className={pulse ? 'animate-pulse' : undefined} aria-label={title}>
      <div className="h-8 bg-gray-200 w-1/2 rounded mb-4" />
      <div className="h-4 bg-gray-100 w-full rounded mb-2" />
      <div className="h-4 bg-gray-100 w-11/12 rounded mb-2" />
      <div className="h-4 bg-gray-100 w-10/12 rounded mb-2" />
      <div className="h-4 bg-gray-100 w-9/12 rounded" />
    </div>
  )
}
