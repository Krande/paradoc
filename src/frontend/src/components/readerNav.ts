// Navigation inside the reader: scrolling to a heading / anchor, and asking the reader to render
// the section an anchor lives in first.
//
// The reader mounts sections progressively (see VirtualReader): a section far below the one being
// read is a placeholder until the reader scrolls near it. An anchor in such a section -- a
// cross-reference target, a sub-heading in the TOC, a search hit -- has no element yet, so
// navigation asks the reader to mount it (`paradoc:reveal`) and waits for the element to appear.

export const REVEAL_EVENT = 'paradoc:reveal'

export interface RevealDetail {
  /** The anchor id to render; omitted together with `all` to render every section. */
  id?: string
  all?: boolean
}

function findById(id: string): HTMLElement | null {
  return document.getElementById(id)
}

/** Is `el` a section placeholder rather than rendered content? */
function isPlaceholder(el: HTMLElement): boolean {
  return el.hasAttribute('data-section-placeholder')
}

/**
 * The element with id `id`, after asking the reader to render the section it is in.
 * Resolves null when no such anchor appears within ~2 s.
 */
export function revealElement(id: string): Promise<HTMLElement | null> {
  const ready = () => {
    const el = findById(id)
    return el && !isPlaceholder(el) ? el : null
  }
  const now = ready()
  if (now) return Promise.resolve(now)
  window.dispatchEvent(new CustomEvent<RevealDetail>(REVEAL_EVENT, { detail: { id } }))
  return new Promise((resolve) => {
    const deadline = performance.now() + 2000
    const tick = () => {
      const el = ready()
      if (el) return resolve(el)
      if (performance.now() > deadline) return resolve(findById(id))
      requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  })
}

/** Ask the reader to render every section (search, print). */
export function revealAll() {
  window.dispatchEvent(new CustomEvent<RevealDetail>(REVEAL_EVENT, { detail: { all: true } }))
}

/** Gap left above a heading once it has been scrolled to, px. */
const SCROLL_TOP_GAP = 16
/** Once on target, how long the layout must stay still before the heading is let go, ms. */
const SCROLL_HOLD_QUIET_MS = 2500
/** Upper bound on how long a scroll keeps re-aiming, ms. */
const SCROLL_MAX_MS = 10000

/**
 * Scroll the reader so `el` sits at the top of it, and keep re-aiming until it stays there.
 *
 * Layout keeps moving under a long scroll. In the web layout, sections render with
 * `content-visibility: auto`, so every section not yet on screen is laid out at a placeholder
 * height, and takes its real height as the scroll passes it. In the page view, lazily loaded
 * images take their height on arrival and the sheets re-paginate around them. Either way a target
 * computed up front goes stale, and a scroll aimed once ends short of the heading -- by more the
 * further down it is. So re-aim each time the scroll settles, and keep holding the heading in place
 * while the content around it is still resizing; stop once it has been still for a moment, the
 * time budget is spent, or the reader takes over the scroll themselves.
 */
export function scrollToHeading(el: HTMLElement) {
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

  let cancelled = false
  let fallback: number | undefined
  let quiet: number | undefined
  const budget = window.setTimeout(() => stop(), SCROLL_MAX_MS)

  // Content resizing while we hold the heading: re-check once the frame has laid out. Not before
  // the first scroll has settled -- re-aiming mid-flight would cut the smooth scroll short.
  let settledOnce = false
  const resized = new ResizeObserver(() => {
    if (settledOnce) onSettled()
  })
  const content = scroller.firstElementChild
  if (content) resized.observe(content)

  function stop() {
    cancelled = true
    window.clearTimeout(fallback)
    window.clearTimeout(quiet)
    window.clearTimeout(budget)
    resized.disconnect()
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
    settledOnce = true
    // Let whatever just came on screen lay out before measuring again.
    requestAnimationFrame(() => {
      if (cancelled) return
      const off = Math.abs(targetTop() - scroller.scrollTop)
      if (off <= 2) {
        // On target. Hold it there until the content has been still for a moment.
        window.clearTimeout(quiet)
        quiet = window.setTimeout(stop, SCROLL_HOLD_QUIET_MS)
        return
      }
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

