import React from 'react'
import { AboutModal } from './AboutModal'
import { UserInfoModal } from './UserInfoModal'
import { useViewerControlsStore } from '../store/viewerControlsStore'

interface OverflowMenuProps {
  // Mobile-only inline controls that we want available even when the
  // viewport is narrow enough to hide the toolbar versions. On desktop
  // these props are still passed but the menu items hide via `sm:hidden`
  // and the user uses the inline toolbar instead.
  sourceDisplayEnabled: boolean
  onToggleSourceDisplay: () => void
  // Doc switcher entries (mobile only). Empty = WS mode or single doc;
  // the switcher section just doesn't render in that case.
  docs: string[]
  currentDocId: string
  onSelectDoc: (id: string) => void
}

// Settings dropdown (cog icon) that hosts the About / User Info / Admin
// actions plus the 3D viewer toggle, and re-surfaces the toolbar's
// inline controls (Source view, document switcher) on small screens
// where they're hidden by `sm:flex`. The icon was previously a kebab
// (three vertical dots) — "more" rather than "settings" — but most of
// the entries are preferences, so a cog reads more truthfully and
// users find the 3D viewer controls toggle faster. Closes on outside
// click and Escape.
export function OverflowMenu({
  sourceDisplayEnabled,
  onToggleSourceDisplay,
  docs,
  currentDocId,
  onSelectDoc,
}: OverflowMenuProps) {
  const [open, setOpen] = React.useState(false)
  const [aboutOpen, setAboutOpen] = React.useState(false)
  const [userOpen, setUserOpen] = React.useState(false)
  const ref = React.useRef<HTMLDivElement>(null)
  const { enabled: viewerControlsEnabled, toggleEnabled: toggleViewerControls } =
    useViewerControlsStore()

  React.useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const showSwitcher = docs.length > 1

  return (
    <>
      <div className="relative" ref={ref}>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="cursor-pointer inline-flex items-center justify-center rounded p-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800"
          aria-label="Settings"
          aria-haspopup="menu"
          aria-expanded={open}
          title="Settings"
        >
          {/* Cog icon. Outline style matches the rest of the topbar
              iconography (hamburger, theme toggle SVGs). */}
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="w-5 h-5"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 14a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 18.36V19a2 2 0 0 1-4 0v-.09A1.7 1.7 0 0 0 9.9 17.5a1.7 1.7 0 0 0-1.87.34l-.06.06A2 2 0 1 1 5.14 15.07l.06-.06A1.7 1.7 0 0 0 5.54 13a1.7 1.7 0 0 0-1.55-1H4a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 5.64 7.1a1.7 1.7 0 0 0-.34-1.87l-.06-.06A2 2 0 1 1 8.07 2.34l.06.06A1.7 1.7 0 0 0 10 2.74H10a1.7 1.7 0 0 0 1-1.55V1a2 2 0 1 1 4 0v.09A1.7 1.7 0 0 0 16 2.64a1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 20.36 7v.09A1.7 1.7 0 0 0 21.91 8.36L22 8.4a2 2 0 0 1 0 4h-.09a1.7 1.7 0 0 0-1.55 1.55Z" />
          </svg>
        </button>

        {open && (
          <div
            role="menu"
            className="absolute right-0 top-full mt-2 w-60 max-h-[80vh] overflow-y-auto bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg shadow-lg dark:shadow-black/30 z-30 py-1 text-sm text-gray-900 dark:text-gray-100"
          >
            {/* Mobile-only re-surfaces of toolbar controls. */}
            <button
              role="menuitem"
              onClick={() => {
                onToggleSourceDisplay()
                setOpen(false)
              }}
              className="sm:hidden cursor-pointer w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center justify-between"
            >
              <span>Source view</span>
              <span
                className={`text-xs ${
                  sourceDisplayEnabled
                    ? 'text-blue-600 dark:text-blue-400 font-medium'
                    : 'text-gray-400 dark:text-gray-500'
                }`}
              >
                {sourceDisplayEnabled ? 'on' : 'off'}
              </span>
            </button>

            {showSwitcher && (
              <div className="sm:hidden border-t border-gray-100 dark:border-gray-800 my-1 pt-1">
                <div className="px-3 py-1 text-xs uppercase tracking-wide text-gray-400 dark:text-gray-500">
                  Switch document
                </div>
                {docs.map((id) => (
                  <button
                    key={id}
                    role="menuitem"
                    onClick={() => {
                      onSelectDoc(id)
                      setOpen(false)
                    }}
                    className={`cursor-pointer w-full text-left px-3 py-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 ${
                      id === currentDocId
                        ? 'font-semibold text-blue-700 dark:text-blue-400'
                        : 'text-gray-700 dark:text-gray-300'
                    }`}
                  >
                    {id}
                  </button>
                ))}
              </div>
            )}

            {/* Always-on entries. The mobile-only block above renders a
                divider already; on desktop we need our own divider here. */}
            <div className="border-t border-gray-100 dark:border-gray-800 my-1 hidden sm:block" />

            <button
              role="menuitem"
              onClick={() => {
                toggleViewerControls()
              }}
              className="cursor-pointer w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center justify-between"
              title="Show adapy's native viewer controls (top navbar, selection tree, object/group info)"
            >
              <span>3D viewer controls</span>
              <span
                className={`text-xs ${
                  viewerControlsEnabled
                    ? 'text-blue-600 dark:text-blue-400 font-medium'
                    : 'text-gray-400 dark:text-gray-500'
                }`}
              >
                {viewerControlsEnabled ? 'on' : 'off'}
              </span>
            </button>

            <button
              role="menuitem"
              onClick={() => {
                setAboutOpen(true)
                setOpen(false)
              }}
              className="cursor-pointer w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              About
            </button>
            <button
              role="menuitem"
              onClick={() => {
                setUserOpen(true)
                setOpen(false)
              }}
              className="cursor-pointer w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              User info
            </button>
            <a
              role="menuitem"
              href="/admin"
              className="cursor-pointer block w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              Admin
            </a>
          </div>
        )}
      </div>

      <AboutModal open={aboutOpen} onClose={() => setAboutOpen(false)} />
      <UserInfoModal open={userOpen} onClose={() => setUserOpen(false)} />
    </>
  )
}
