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

// Kebab-icon dropdown that hosts the About / User Info actions and
// re-surfaces the toolbar controls on small screens. Closes on outside
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
          className="cursor-pointer inline-flex items-center justify-center rounded p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100"
          aria-label="More options"
          aria-haspopup="menu"
          aria-expanded={open}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
            <path d="M10 4a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm0 4.5a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm0 4.5a1.5 1.5 0 110 3 1.5 1.5 0 010-3z" />
          </svg>
        </button>

        {open && (
          <div
            role="menu"
            className="absolute right-0 top-full mt-2 w-60 max-h-[80vh] overflow-y-auto bg-white border border-gray-200 rounded-lg shadow-lg z-30 py-1 text-sm"
          >
            {/* Mobile-only re-surfaces of toolbar controls. */}
            <button
              role="menuitem"
              onClick={() => {
                onToggleSourceDisplay()
                setOpen(false)
              }}
              className="sm:hidden cursor-pointer w-full text-left px-3 py-2 hover:bg-gray-100 flex items-center justify-between"
            >
              <span>Source view</span>
              <span className={`text-xs ${sourceDisplayEnabled ? 'text-blue-600 font-medium' : 'text-gray-400'}`}>
                {sourceDisplayEnabled ? 'on' : 'off'}
              </span>
            </button>

            {showSwitcher && (
              <div className="sm:hidden border-t border-gray-100 my-1 pt-1">
                <div className="px-3 py-1 text-xs uppercase tracking-wide text-gray-400">Switch document</div>
                {docs.map((id) => (
                  <button
                    key={id}
                    role="menuitem"
                    onClick={() => {
                      onSelectDoc(id)
                      setOpen(false)
                    }}
                    className={`cursor-pointer w-full text-left px-3 py-1.5 hover:bg-gray-100 ${
                      id === currentDocId ? 'font-semibold text-blue-700' : 'text-gray-700'
                    }`}
                  >
                    {id}
                  </button>
                ))}
              </div>
            )}

            {/* Always-on entries. The mobile-only block above renders a
                divider already; on desktop we need our own divider here. */}
            <div className="border-t border-gray-100 my-1 hidden sm:block" />

            <button
              role="menuitem"
              onClick={() => {
                toggleViewerControls()
              }}
              className="cursor-pointer w-full text-left px-3 py-2 hover:bg-gray-100 flex items-center justify-between"
              title="Show adapy's native viewer controls (top navbar, selection tree, object/group info)"
            >
              <span>3D viewer controls</span>
              <span className={`text-xs ${viewerControlsEnabled ? 'text-blue-600 font-medium' : 'text-gray-400'}`}>
                {viewerControlsEnabled ? 'on' : 'off'}
              </span>
            </button>

            <button
              role="menuitem"
              onClick={() => {
                setAboutOpen(true)
                setOpen(false)
              }}
              className="cursor-pointer w-full text-left px-3 py-2 hover:bg-gray-100"
            >
              About
            </button>
            <button
              role="menuitem"
              onClick={() => {
                setUserOpen(true)
                setOpen(false)
              }}
              className="cursor-pointer w-full text-left px-3 py-2 hover:bg-gray-100"
            >
              User info
            </button>
          </div>
        )}
      </div>

      <AboutModal open={aboutOpen} onClose={() => setAboutOpen(false)} />
      <UserInfoModal open={userOpen} onClose={() => setUserOpen(false)} />
    </>
  )
}
