import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { DocManifest, SectionBundle, Header } from '../ast/types'
import { renderBlock, RenderWithDocId } from '../ast/render'
import { predictivePrefetch } from '../sections/store'
import { calculateHeadingNumbers } from '../ast/headingNumbers'
import { usePageViewStore } from '../store/pageViewStore'
import { PagedSection } from './PagedSection'

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
      next += pageCounts[i] ?? 1
    })
    return out
  }, [h1Sections, pageCounts])

  return (
    <RenderWithDocId docId={docId}>
      <div
        ref={containerRef}
        className={`flex-1 overflow-auto overscroll-contain ${pageView ? 'px-4 py-2 bg-gray-200 dark:bg-gray-950' : 'p-6'}`}
        data-search-root
      >
        <div className={pageView ? 'w-max min-w-full' : 'max-w-none w-full'}>
          {h1Sections.map((s, i) => {
            const bundle = sections[s.id]
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
                  <PagedSection index={i} firstPage={firstPages[i]} onPageCount={setPageCount}>
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
    </RenderWithDocId>
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

function Skeleton({ title }: { title: string }) {
  return (
    <div className="animate-pulse">
      <div className="h-8 bg-gray-200 w-1/2 rounded mb-4" />
      <div className="h-4 bg-gray-100 w-full rounded mb-2" />
      <div className="h-4 bg-gray-100 w-11/12 rounded mb-2" />
      <div className="h-4 bg-gray-100 w-10/12 rounded mb-2" />
      <div className="h-4 bg-gray-100 w-9/12 rounded" />
    </div>
  )
}
