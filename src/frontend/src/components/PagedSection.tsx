import React, { useLayoutEffect, useRef, useState } from 'react'

// A4 portrait, in CSS millimetres (an absolute unit: 1mm is 96/25.4 px regardless of screen).
const MM = 96 / 25.4
const PAGE_W_MM = 210
const PAGE_H_MM = 297
const MARGIN_Y_MM = 25
const MARGIN_X_MM = 20
/** Gray canvas between two sheets. */
const GAP_MM = 8

const STRIDE = (PAGE_H_MM + GAP_MM) * MM
const USABLE_H = (PAGE_H_MM - 2 * MARGIN_Y_MM) * MM
const pageTop = (p: number) => p * STRIDE + MARGIN_Y_MM * MM
const pageBottom = (p: number) => p * STRIDE + (PAGE_H_MM - MARGIN_Y_MM) * MM

const PUSH_ATTR = 'data-page-push'
const isHeading = (el: Element) => /^H[1-6]$/.test(el.tagName)

/**
 * Lay the blocks under `content` out on sheets: a block that would cross a sheet's bottom margin
 * moves to the top of the next sheet, by growing its top margin. Blocks are never split, so a block
 * taller than a sheet is left to run across the gap. A heading that would be left at the foot of a
 * sheet moves with the block that follows it. Returns the number of sheets used.
 */
function paginate(paper: HTMLElement, content: HTMLElement): number {
  const blocks = Array.from(content.children) as HTMLElement[]

  // Undo the previous pass, so every measurement below is of the natural flow.
  for (const b of blocks) {
    if (b.hasAttribute(PUSH_ATTR)) {
      b.style.marginTop = b.getAttribute(PUSH_ATTR) || ''
      b.removeAttribute(PUSH_ATTR)
    }
  }

  const origin = () => paper.getBoundingClientRect().top
  /** Move `el` down so its top sits at `target` (px from the paper's top). */
  const pushTo = (el: HTMLElement, target: number) => {
    // Record the author's inline margin once; a block pushed twice in a pass keeps the first.
    if (!el.hasAttribute(PUSH_ATTR)) el.setAttribute(PUSH_ATTR, el.style.marginTop)
    // Aim, measure, correct: the top margin collapses with the previous block's bottom margin, so
    // growing it by d moves the block by less than d whenever that bottom margin was the larger.
    for (let k = 0; k < 3; k++) {
      const off = target - (el.getBoundingClientRect().top - origin())
      if (Math.abs(off) < 0.5) break
      const current = parseFloat(getComputedStyle(el).marginTop) || 0
      el.style.marginTop = `${current + off}px`
    }
  }

  for (let i = 0; i < blocks.length; i++) {
    const b = blocks[i]
    const r = b.getBoundingClientRect()
    if (r.height === 0) continue
    const top = r.top - origin()
    const p = Math.floor(top / STRIDE)
    // Below a block that ran across the gap, the next can start in a sheet's top margin.
    if (top < pageTop(p) - 0.5) {
      pushTo(b, pageTop(p))
      i -= 1 // re-check it where it now sits
      continue
    }
    const crosses = top + r.height > pageBottom(p) + 0.5
    if (!crosses || r.height > USABLE_H) continue

    // Keep a heading with what it introduces: move the heading, then re-check this block below it.
    const prev = blocks[i - 1]
    if (prev && isHeading(prev) && !prev.hasAttribute(PUSH_ATTR)) {
      const prevTop = prev.getBoundingClientRect().top - origin()
      if (Math.floor(prevTop / STRIDE) === p && prevTop > pageTop(p) + 1) {
        pushTo(prev, pageTop(p + 1))
        i -= 1
        continue
      }
    }
    pushTo(b, pageTop(p + 1))
  }

  const last = blocks[blocks.length - 1]
  if (!last) return 1
  const bottom = last.getBoundingClientRect().bottom - origin()
  return Math.max(1, Math.floor(bottom / STRIDE) + 1)
}

type Props = {
  children: React.ReactNode
  /** Number printed on this section's first sheet. */
  firstPage: number
  onPageCount: (n: number) => void
}

/** One document section on A4 sheets. Starts on a new sheet, like a chapter in the exports. */
export function PagedSection({ children, firstPage, onPageCount }: Props) {
  const paperRef = useRef<HTMLDivElement | null>(null)
  const contentRef = useRef<HTMLDivElement | null>(null)
  const [pages, setPages] = useState(1)

  useLayoutEffect(() => {
    const paper = paperRef.current
    const content = contentRef.current
    if (!paper || !content) return

    let frame = 0
    let running = false
    const run = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        if (running) return
        running = true
        try {
          // The section's blocks sit one level down, inside the section renderer's wrapper div.
          const flow = (content.firstElementChild as HTMLElement | null) ?? content
          const n = paginate(paper, flow)
          setPages((prev) => (prev === n ? prev : n))
        } finally {
          running = false
        }
      })
    }

    run()
    // Images, plots and 3D posters arrive after first paint and change block heights. Our own
    // pushes resize `content` too; that re-run lands on the same layout and changes nothing.
    const ro = new ResizeObserver(run)
    ro.observe(content)
    return () => {
      cancelAnimationFrame(frame)
      ro.disconnect()
    }
  }, [children])

  useLayoutEffect(() => onPageCount(pages), [pages, onPageCount])

  return (
    <div
      ref={paperRef}
      className="relative mx-auto my-6"
      style={{ width: `${PAGE_W_MM}mm`, minHeight: `${pages * STRIDE - GAP_MM * MM}px` }}
    >
      {/* The sheets, behind the text. */}
      {Array.from({ length: pages }, (_, i) => (
        <div
          key={i}
          aria-hidden="true"
          className="absolute inset-x-0 bg-white dark:bg-gray-900 shadow-md ring-1 ring-black/5 dark:ring-white/10"
          style={{ top: `${i * STRIDE}px`, height: `${PAGE_H_MM}mm` }}
        >
          <div
            className="absolute inset-x-0 text-center text-xs text-gray-400 dark:text-gray-500 select-none"
            style={{ bottom: `${MARGIN_Y_MM / 2}mm` }}
          >
            {firstPage + i}
          </div>
        </div>
      ))}
      <div
        ref={contentRef}
        className="paged relative"
        style={{ padding: `${MARGIN_Y_MM}mm ${MARGIN_X_MM}mm` }}
      >
        {children}
      </div>
    </div>
  )
}
