import React, { useEffect } from 'react'

export type TocItem = {
  id: string
  text: string
  level: number // 0-based: h1 -> 0
}

type NavbarProps = {
  toc: TocItem[]
  open: boolean
  onClose: () => void
}

export function Navbar({ toc, open, onClose }: NavbarProps) {
  const NavList = (
    <nav className="p-2">
      <ul className="space-y-1">
        {toc.map((item) => (
          <li key={item.id}>
            <a
              className="cursor-pointer block text-sm text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded px-2 py-1"
              style={{ paddingLeft: `${item.level * 16 + 8}px` }}
              href={`#${item.id}`}
              onClick={(e) => {
                e.preventDefault()
                const el = document.getElementById(item.id)
                if (el) {
                  const topbar = document.getElementById('paradoc-topbar')
                  const offset = topbar ? topbar.getBoundingClientRect().height : 0
                  const top = window.scrollY + el.getBoundingClientRect().top - offset - 8
                  window.scrollTo({ top, behavior: 'smooth' })
                }
                onClose()
              }}
              aria-label={`Go to ${item.text}`}
            >
              {item.text}
            </a>
          </li>
        ))}
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

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:flex-col w-72 shrink-0 border-r border-gray-200 bg-white/60 backdrop-blur sticky top-0 h-screen overflow-auto">
        <div className="px-4 py-3 border-b border-gray-200">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">Outline</div>
        </div>
        {NavList}
      </aside>

      {/* Mobile drawer */}
      <div
        id="paradoc-mobile-drawer-root"
        className={`fixed inset-0 z-40 md:hidden ${open ? 'pointer-events-auto' : 'pointer-events-none'}`}
        {...(!open ? ({ inert: '' } as any) : {})}
      >
        {/* Backdrop */}
        <div
          className={`absolute inset-0 bg-black/20 transition-opacity ${open ? 'opacity-100' : 'opacity-0'}`}
          onClick={onClose}
        />
        {/* Panel */}
        <aside
          className={`absolute left-0 top-0 bottom-0 w-72 bg-white border-r border-gray-200 shadow-xl transform transition-transform ${open ? 'translate-x-0' : '-translate-x-full'}`}
          role="dialog"
          aria-modal="true"
        >
          <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
            <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">Outline</div>
            <button
              className="cursor-pointer inline-flex items-center justify-center rounded p-2 text-gray-500 hover:text-gray-700"
              onClick={onClose}
              aria-label="Close contents"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
          <div className="h-full overflow-auto">{NavList}</div>
        </aside>
      </div>
    </>
  )
}
