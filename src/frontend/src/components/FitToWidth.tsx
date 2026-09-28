import React, { useLayoutEffect, useRef } from 'react'

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

    const fit = () => {
      inner.style.zoom = '1'
      const natural = inner.scrollWidth
      const available = outer.clientWidth
      const scale = natural > available + 1 ? Math.max(minScale, available / natural) : 1
      inner.style.zoom = scale === 1 ? '' : String(scale)
    }

    fit()
    // Only the outer box: the inner one changes size because of the zoom itself.
    const ro = new ResizeObserver(fit)
    ro.observe(outer)
    return () => ro.disconnect()
  }, [children, minScale])

  return (
    <div ref={outerRef} className="overflow-x-auto">
      <div ref={innerRef} className="w-max min-w-full">
        {children}
      </div>
    </div>
  )
}
