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

  // Fast path: plan every push from ONE measurement of the natural flow, write them all, then
  // check them in ONE more read. The pass below measures after each write instead, and every one of
  // those reads is a forced layout of the whole section -- on a report appendix with a thousand
  // blocks and hundreds of page breaks that is seconds of blocked main thread, on every resize of
  // any block in it (a figure switched to its 3D viewer). Only a block the plan put in the wrong
  // place falls through to the measuring pass.
  if (paginatePlanned(paper, blocks)) {
    const last = blocks[blocks.length - 1]
    if (!last) return 1
    const bottom = last.getBoundingClientRect().bottom - paper.getBoundingClientRect().top
    return Math.max(1, Math.floor(bottom / STRIDE) + 1)
  }
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

/**
 * The same layout as the measuring pass in `paginate`, planned arithmetically: read every block's
 * natural top and height once, walk them carrying the accumulated shift, and turn each block's
 * total push into a new top margin. Returns false -- with the margins it wrote still in place for
 * the caller to undo -- when a block did not land where the plan put it.
 *
 * A push of `d` moves a block by exactly `d` when its new top margin is the old border-to-border
 * gap above it plus `d`: the gap is already the collapsed margin, and a larger top margin wins the
 * collapse outright. That holds for ordinary block siblings; anything else (a margin that does not
 * collapse, a float, a flex parent) shows up in the check and takes the measuring pass.
 */
function paginatePlanned(paper: HTMLElement, blocks: HTMLElement[]): boolean {
  const n = blocks.length
  if (n === 0) return true
  const originTop = paper.getBoundingClientRect().top
  const tops = new Float64Array(n)
  const heights = new Float64Array(n)
  const gaps = new Float64Array(n)
  for (let i = 0; i < n; i++) {
    const r = blocks[i].getBoundingClientRect()
    tops[i] = r.top - originTop
    heights[i] = r.height
  }
  for (let i = 0; i < n; i++) {
    gaps[i] = i === 0
      ? parseFloat(getComputedStyle(blocks[0]).marginTop) || 0
      : tops[i] - (tops[i - 1] + heights[i - 1])
  }

  const push = new Float64Array(n)
  let shift = 0
  const topOf = (i: number) => tops[i] + shift
  for (let i = 0; i < n; i++) {
    if (heights[i] === 0) continue
    const top = topOf(i)
    const p = Math.floor(top / STRIDE)
    // Below a block that ran across the gap, the next can start in a sheet's top margin.
    if (top < pageTop(p) - 0.5) {
      const d = pageTop(p) - top
      push[i] += d
      shift += d
      i -= 1 // re-check it where it now sits
      continue
    }
    const crosses = top + heights[i] > pageBottom(p) + 0.5
    if (!crosses || heights[i] > USABLE_H) continue

    // Keep a heading with what it introduces: move the heading, then re-check this block below it.
    // The heading's top is where it sits now: its natural top plus every push up to and including
    // it -- the current shift less what this block has itself been pushed by already (a block
    // re-checked after the top-margin branch above), which moves only this block and what follows.
    const prev = i - 1
    if (prev >= 0 && isHeading(blocks[prev]) && push[prev] === 0) {
      const prevTop = tops[prev] + shift - push[i]
      if (Math.floor(prevTop / STRIDE) === p && prevTop > pageTop(p) + 1) {
        const d = pageTop(p + 1) - prevTop
        push[prev] += d
        shift += d
        i -= 1
        continue
      }
    }
    const d = pageTop(p + 1) - top
    push[i] += d
    shift += d
  }

  // Write every push at once, then read once to check.
  for (let i = 0; i < n; i++) {
    if (push[i] === 0) continue
    const el = blocks[i]
    el.setAttribute(PUSH_ATTR, el.style.marginTop)
    el.style.marginTop = `${gaps[i] + push[i]}px`
  }
  let acc = 0
  const checkOrigin = paper.getBoundingClientRect().top
  for (let i = 0; i < n; i++) {
    acc += push[i]
    if (heights[i] === 0) continue
    // A pixel, not half of one: layout snaps positions to sub-pixel units, and far down a long
    // section (y ~ 98 000 px) a correctly placed block reads ~0.5 px off its planned top. Failing
    // the check on that sent every large report through the slow pass.
    const want = tops[i] + acc
    if (Math.abs(blocks[i].getBoundingClientRect().top - checkOrigin - want) > 1) return false
  }
  return true
}

type Props = {
  children: React.ReactNode
  /** The section's position in the document, handed back with its page count. */
  index: number
  /** Number printed on this section's first sheet. */
  firstPage: number
  /** Must be stable across renders (a `useCallback`): it is an effect dependency. */
  onPageCount: (index: number, n: number) => void
}

/** One document section on A4 sheets. Starts on a new sheet, like a chapter in the exports. */
export function PagedSection({ children, index, firstPage, onPageCount }: Props) {
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
    //
    // The observer is the only re-run trigger -- not a change of `children`. A parent re-render
    // hands over a new `children` element every time even when nothing in it changed, and
    // re-paginating on that turned one block's resize (a 3D figure switched to interactive) into
    // a page-count change, a document re-render, and a full re-pagination of every section: ~10 s
    // of forced layouts on a large report. What a children change could alter here is block
    // heights, and those resize `content`.
    const ro = new ResizeObserver(run)
    ro.observe(content)
    return () => {
      cancelAnimationFrame(frame)
      ro.disconnect()
    }
  }, [])

  useLayoutEffect(() => onPageCount(index, pages), [index, pages, onPageCount])

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
