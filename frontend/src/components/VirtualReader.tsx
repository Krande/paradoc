import React, { useEffect, useMemo, useRef, useState } from 'react'
import type { DocManifest, SectionBundle } from '../ast/types'
import { renderBlocks } from '../ast/render'
import { predictivePrefetch } from '../sections/store'

interface Props {
  docId: string
  manifest: DocManifest
  sections: Record<string, SectionBundle>
}

export function VirtualReader({ docId, manifest, sections }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [visibleIndex, setVisibleIndex] = useState(0)

  // Build ordered list of rendered items with fallback placeholders
  const items = useMemo(() => manifest.sections.map((s) => sections[s.id] || null), [manifest, sections])

  useEffect(() => {
    if (!manifest) return
    predictivePrefetch(docId, manifest, visibleIndex)
  }, [docId, manifest, visibleIndex])

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

  return (
    <div ref={containerRef} className="flex-1 overflow-auto p-6">
      <div className="max-w-none w-full">
        {manifest.sections.map((s, i) => {
          const bundle = sections[s.id]
          return (
            <section
              key={s.id}
              id={s.id}
              data-section-index={i}
              style={{ containIntrinsicSize: '1px 800px' as any }}
              className="content-visibility-auto my-6 scroll-mt-14"
            >
              {bundle ? (
                <Section blockKey={s.id} bundle={bundle} />
              ) : (
                <Skeleton title={s.title} />
              )}
            </section>
          )
        })}
      </div>
    </div>
  )
}

function Section({ bundle, blockKey }: { bundle: SectionBundle, blockKey: string }) {
  return (
    <div>
      {renderBlocks(bundle.doc.blocks)}
    </div>
  )
}

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
