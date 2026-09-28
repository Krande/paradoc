import React, { useEffect, useMemo, useState } from 'react'

export type TocItem = {
  id: string
  text: string
  level: number // 0-based: h1 -> 0
  number?: string // Optional heading number (e.g., "1.1", "A.2")
}

type NavbarProps = {
  toc: TocItem[]
  open: boolean
  onClose: () => void
}

/** Gap left above a heading once it has been scrolled to, px. */
const SCROLL_TOP_GAP = 16
/** How many times a scroll is re-aimed while sections below it are still being laid out. */
const MAX_SCROLL_CORRECTIONS = 8

/**
 * Scroll the reader so `el` sits at the top of it, and keep re-aiming until it stays there.
 *
 * The reader renders its sections with `content-visibility: auto`, so every section not yet on
 * screen is laid out at a placeholder height. A target computed up front is therefore computed
 * against placeholders; as the smooth scroll passes sections they render at their real height,
 * everything below them moves, and the scroll ends short of the heading -- by more the further
 * down it is. So once a scroll settles, measure again and go again, until the heading is where it
 * should be, the scroller can go no further, or the reader takes over the scroll themselves.
 */
function scrollToHeading(el: HTMLElement) {
  // Find the reader's overflow-auto container explicitly (it carries `data-search-root`). Scroll
  // *only* that container -- neither `window.scrollTo` (worked on desktop, triggered the
  // visual-viewport pinch-zoom heuristic on mobile) nor `scrollIntoView` (walks multiple scroll
  // ancestors on iOS / Android Chrome, shifting the page chrome and pushing the topbar out of view).
  const root = el.closest('[data-search-root]') as HTMLElement | null
  if (!root) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return
  }
  const scroller: HTMLElement = root

  const targetTop = () => {
    const elRect = el.getBoundingClientRect()
    const scRect = scroller.getBoundingClientRect()
    const target = elRect.top - scRect.top + scroller.scrollTop - SCROLL_TOP_GAP
    return Math.max(0, Math.min(target, scroller.scrollHeight - scroller.clientHeight))
  }

  let corrections = 0
  let cancelled = false
  let fallback: number | undefined

  const stop = () => {
    cancelled = true
    window.clearTimeout(fallback)
    scroller.removeEventListener('scrollend', onSettled)
    scroller.removeEventListener('wheel', stop)
    scroller.removeEventListener('touchstart', stop)
    scroller.removeEventListener('keydown', stop)
  }

  const go = (behavior: ScrollBehavior) => {
    window.clearTimeout(fallback)
    scroller.scrollTo({ top: targetTop(), behavior })
    // `scrollend` is not everywhere yet, and it does not fire when the scroll had nowhere to go.
    fallback = window.setTimeout(onSettled, behavior === 'smooth' ? 1200 : 150)
  }

  function onSettled() {
    if (cancelled) return
    // Let the sections that just came on screen lay out before measuring again.
    requestAnimationFrame(() => {
      if (cancelled) return
      const off = Math.abs(targetTop() - scroller.scrollTop)
      if (off <= 2 || corrections >= MAX_SCROLL_CORRECTIONS) {
        stop()
        return
      }
      corrections += 1
      go('auto')
    })
  }

  scroller.addEventListener('scrollend', onSettled)
  // The reader grabbing the scroll mid-flight wins; don't drag them back to the heading.
  scroller.addEventListener('wheel', stop, { passive: true })
  scroller.addEventListener('touchstart', stop, { passive: true })
  scroller.addEventListener('keydown', stop)
  go('smooth')
}

/** For each item, whether the next one is nested under it -- i.e. whether it can be collapsed. */
function childFlags(toc: TocItem[]): boolean[] {
  return toc.map((item, i) => i + 1 < toc.length && toc[i + 1].level > item.level)
}

/** The items not hidden inside a collapsed ancestor. */
function visibleItems(toc: TocItem[], hasChildren: boolean[], collapsed: Set<string>) {
  const out: { item: TocItem; index: number }[] = []
  let hideDeeperThan: number | null = null
  toc.forEach((item, index) => {
    if (hideDeeperThan !== null) {
      if (item.level > hideDeeperThan) return
      hideDeeperThan = null
    }
    out.push({ item, index })
    if (hasChildren[index] && collapsed.has(item.id)) hideDeeperThan = item.level
  })
  return out
}

function Chevron({ expanded }: { expanded: boolean }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className={`h-3.5 w-3.5 transition-[rotate] duration-100 ${expanded ? 'rotate-90' : ''}`}
      aria-hidden="true"
    >
      <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.17 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
    </svg>
  )
}

function OutlineControls({ onExpandAll, onCollapseAll, disabled }: { onExpandAll: () => void; onCollapseAll: () => void; disabled: boolean }) {
  const btn =
    'cursor-pointer rounded px-1.5 py-0.5 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-40 disabled:cursor-default'
  return (
    <div className="flex items-center gap-1">
      <button type="button" className={btn} onClick={onExpandAll} disabled={disabled} title="Expand all" aria-label="Expand all outline items">
        Expand all
      </button>
      <button type="button" className={btn} onClick={onCollapseAll} disabled={disabled} title="Collapse all" aria-label="Collapse all outline items">
        Collapse all
      </button>
    </div>
  )
}

export function Navbar({ toc, open, onClose }: NavbarProps) {
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set())
  const hasChildren = useMemo(() => childFlags(toc), [toc])
  const shown = useMemo(() => visibleItems(toc, hasChildren, collapsed), [toc, hasChildren, collapsed])
  const collapsible = hasChildren.some(Boolean)

  const toggle = (id: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  const expandAll = () => setCollapsed(new Set())
  const collapseAll = () => setCollapsed(new Set(toc.filter((_, i) => hasChildren[i]).map((t) => t.id)))

  const NavList = (
    <nav className="p-2">
      <ul className="space-y-1">
        {shown.map(({ item, index }) => {
          const expandable = hasChildren[index]
          const expanded = expandable && !collapsed.has(item.id)
          return (
            <li key={item.id} className="flex items-start" style={{ paddingLeft: `${item.level * 16}px` }}>
              {expandable ? (
                <button
                  type="button"
                  className="cursor-pointer mt-1 shrink-0 inline-flex items-center justify-center rounded h-5 w-5 text-gray-400 dark:text-gray-500 hover:text-gray-800 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800"
                  onClick={() => toggle(item.id)}
                  aria-expanded={expanded}
                  aria-label={`${expanded ? 'Collapse' : 'Expand'} ${item.text}`}
                >
                  <Chevron expanded={expanded} />
                </button>
              ) : (
                <span className="shrink-0 w-5" aria-hidden="true" />
              )}
              <a
                className="cursor-pointer block flex-1 min-w-0 text-sm text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 rounded px-2 py-1"
                href={`#${item.id}`}
                onClick={(e) => {
                  e.preventDefault()
                  const el = document.getElementById(item.id)
                  if (el) scrollToHeading(el)
                  onClose()
                }}
                aria-label={`Go to ${item.text}`}
              >
                {item.number && <span className="mr-2 text-gray-500 dark:text-gray-400">{item.number}</span>}
                {item.text}
              </a>
            </li>
          )
        })}
      </ul>
    </nav>
  )

  useEffect(() => {
    if (!open) {
      const panel = document.getElementById('paradoc-mobile-drawer')
      const active = document.activeElement as HTMLElement | null
      if (panel && active && panel.contains(active)) {
        try { active.blur() } catch {}
      }
    }
  }, [open])

  const controls = <OutlineControls onExpandAll={expandAll} onCollapseAll={collapseAll} disabled={!collapsible} />

  return (
    <>
      {/* Desktop sidebar */}
      <aside className={`${open ? 'md:flex' : 'md:hidden'} hidden flex-col w-72 shrink-0 border-r border-gray-200 dark:border-gray-800 bg-white/60 dark:bg-gray-950/60 backdrop-blur sticky top-0 h-dvh overflow-auto`}>
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between gap-2">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Outline</div>
          {controls}
        </div>
        {NavList}
      </aside>

      {/* Mobile drawer */}
      <div
        id="paradoc-mobile-drawer-root"
        className={`fixed inset-0 z-40 md:hidden ${open ? 'pointer-events-auto' : 'pointer-events-none'}`}
        {...(!open ? ({ inert: true } as any) : {})}
      >
        {/* Backdrop */}
        <div
          className={`absolute inset-0 bg-black/20 transition-opacity ${open ? 'opacity-100' : 'opacity-0'}`}
          onClick={onClose}
        />
        {/* Panel. Tailwind v4 dropped the `transform` helper class —
            it still emits a CSS rule but the rule references legacy
            `--tw-rotate` / `--tw-skew-*` vars that don't exist in v4,
            so the resulting `transform: translate(…) rotate(…) skew(…)`
            value is invalid and the browser falls back to `none`. The
            v4-correct utilities (`-translate-x-full` / `translate-x-0`)
            already set the CSS `translate` property directly, so we
            need `transition-[translate]` to animate that property
            instead of the old `transition-transform`. */}
        <aside
          className={`absolute left-0 top-0 bottom-0 w-72 bg-white dark:bg-gray-950 border-r border-gray-200 dark:border-gray-800 shadow-xl transition-[translate] duration-150 ease-out ${open ? 'translate-x-0' : '-translate-x-full'}`}
          role="dialog"
          aria-modal="true"
        >
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between gap-2">
            <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Outline</div>
            <div className="flex items-center gap-1">
              {controls}
              <button
                className="cursor-pointer inline-flex items-center justify-center rounded p-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                onClick={onClose}
                aria-label="Close contents"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5">
                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
          </div>
          <div className="h-full overflow-auto">{NavList}</div>
        </aside>
      </div>
    </>
  )
}
