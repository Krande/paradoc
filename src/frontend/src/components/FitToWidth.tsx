import React, { useLayoutEffect, useRef } from 'react'

type Fit = { outer: HTMLElement; inner: HTMLElement; minScale: number }

// Every FitToWidth that needs (re)fitting, flushed together once per commit / resize batch.
// Fitting one table means: reset its zoom, read its natural width, write the new zoom. Done one
// table at a time, each read forces a layout of the whole document the previous write dirtied --
// a large report with a hundred tables spent a third of its load in those layouts. Batched, all
// resets are written, then all widths read in one layout, then all zooms written.
const pending = new Set<Fit>()
let scheduled = false

function flush() {
  scheduled = false
  const batch = Array.from(pending).filter((f) => f.outer.isConnected)
  pending.clear()
  for (const f of batch) f.inner.style.zoom = '1'
  const sizes = batch.map((f) => [f.inner.scrollWidth, f.outer.clientWidth] as const)
  batch.forEach((f, i) => {
    const [natural, available] = sizes[i]
    const scale = natural > available + 1 ? Math.max(f.minScale, available / natural) : 1
    f.inner.style.zoom = scale === 1 ? '' : String(scale)
  })
}

function scheduleFit(f: Fit) {
  pending.add(f)
  if (scheduled) return
  scheduled = true
  // A microtask runs after the current commit's layout effects (or the current batch of resize
  // observer callbacks) and before the frame paints, so a wide table never shows unscaled.
  queueMicrotask(flush)
}

/**
 * Scale wide content (a table) down to the width it is given, instead of making it scroll.
 *
 * Uses CSS `zoom`, which -- unlike `transform: scale` -- shrinks the layout box too, so the
 * page flows around the scaled table and a paginated view measures its real height. Below
 * `minScale` text would be unreadable; there the content keeps that scale and scrolls
 * horizontally instead. Re-measured whenever the available width changes.
 */
export function FitToWidth({ children, minScale = 0.5 }: { children: React.ReactNode; minScale?: number }) {
  const outerRef = useRef<HTMLDivElement | null>(null)
  const innerRef = useRef<HTMLDivElement | null>(null)

  useLayoutEffect(() => {
    const outer = outerRef.current
    const inner = innerRef.current
    if (!outer || !inner) return

    const fit: Fit = { outer, inner, minScale }
    scheduleFit(fit)
    // Only the outer box: the inner one changes size because of the zoom itself. All observers'
    // callbacks of one frame land in one flush.
    const ro = new ResizeObserver(() => scheduleFit(fit))
    ro.observe(outer)
    return () => {
      ro.disconnect()
      pending.delete(fit)
    }
  }, [children, minScale])

  return (
    <div ref={outerRef} className="overflow-x-auto">
      <div ref={innerRef} className="w-max min-w-full">
        {children}
      </div>
    </div>
  )
}
