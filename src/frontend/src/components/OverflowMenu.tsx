import React from 'react'
import { AboutModal } from './AboutModal'
import { UserInfoModal } from './UserInfoModal'
import { BundleFilesModal } from './BundleFilesModal'
import { OptionsModal } from './OptionsModal'
import { clearAllCache } from '../sections/store'

interface OverflowMenuProps {
  // Mobile-only inline control that we want available even when the
  // viewport is narrow enough to hide the toolbar version. On desktop
  // it's still passed but the menu item hides via `sm:hidden` and the
  // user uses the inline toolbar instead.
  sourceDisplayEnabled: boolean
  onToggleSourceDisplay: () => void
  // Doc id is still surfaced so the "Bundle files" modal knows which
  // doc to list. Doc *switching* lives in the Topbar's ``DocSwitcher``
  // dropdown for both viewports — it used to be duplicated here on
  // mobile, but that cluttered the menu and the dropdown already shows
  // up at every breakpoint.
  currentDocId: string
}

// Settings dropdown (cog icon) that hosts About / User info / Bundle
// files / Admin / Clear-cache actions plus the "Options" entry that
// opens a dedicated preferences modal (theme, 3D viewer controls). The
// preferences live in their own panel so this menu stays focused on
// actions and doesn't grow each time a new toggle is added. Source view
// is re-surfaced here on mobile (`sm:hidden`) because the toolbar
// version is hidden at narrow widths. Closes on outside click and
// Escape.
export function OverflowMenu({
  sourceDisplayEnabled,
  onToggleSourceDisplay,
  currentDocId,
}: OverflowMenuProps) {
  const [open, setOpen] = React.useState(false)
  const [aboutOpen, setAboutOpen] = React.useState(false)
  const [userOpen, setUserOpen] = React.useState(false)
  const [filesOpen, setFilesOpen] = React.useState(false)
  const [optionsOpen, setOptionsOpen] = React.useState(false)
  const ref = React.useRef<HTMLDivElement>(null)

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
          {/* Cog icon (Heroicons v2 outline). The previous hand-rolled
              path placed tooth tips at y≈1 and y≈23 which clipped at
              stroke-width 1.8 and pushed the inner ring off-centre. The
              Heroicons path is properly inset so the gear is centred
              and fully inside the 24×24 viewBox. */}
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="w-5 h-5"
            aria-hidden="true"
          >
            <path d="M10.343 3.94c.09-.542.56-.94 1.11-.94h1.093c.55 0 1.02.398 1.11.94l.149.894c.07.424.384.764.78.93.398.164.855.142 1.205-.108l.737-.527a1.125 1.125 0 011.45.12l.773.774c.39.389.44 1.002.12 1.45l-.527.737c-.25.35-.272.806-.107 1.204.165.397.505.71.93.78l.893.15c.543.09.94.56.94 1.109v1.094c0 .55-.397 1.02-.94 1.11l-.893.149c-.425.07-.765.383-.93.78-.165.398-.143.854.107 1.204l.527.738c.32.447.269 1.06-.12 1.45l-.774.773a1.125 1.125 0 01-1.449.12l-.738-.527c-.35-.25-.806-.272-1.203-.107-.397.165-.71.505-.781.929l-.149.894c-.09.542-.56.94-1.11.94h-1.094c-.55 0-1.019-.398-1.11-.94l-.148-.894c-.071-.424-.384-.764-.781-.93-.398-.164-.854-.142-1.204.108l-.738.527c-.447.32-1.06.269-1.45-.12l-.773-.774a1.125 1.125 0 01-.12-1.45l.527-.737c.25-.35.273-.806.108-1.204-.165-.397-.505-.71-.93-.78l-.894-.15c-.542-.09-.94-.56-.94-1.109v-1.094c0-.55.398-1.02.94-1.11l.894-.149c.424-.07.764-.383.93-.78.165-.398.143-.854-.107-1.204l-.527-.738a1.125 1.125 0 01.12-1.45l.773-.773a1.125 1.125 0 011.45-.12l.737.527c.35.25.807.272 1.204.107.397-.165.71-.505.78-.929l.15-.894z" />
            <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>

        {open && (
          <div
            role="menu"
            className="absolute right-0 top-full mt-2 w-60 max-h-[80vh] overflow-y-auto bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg shadow-lg dark:shadow-black/30 z-30 py-1 text-sm text-gray-900 dark:text-gray-100"
          >
            {/* Mobile-only re-surface of the toolbar's Source view
                toggle (toolbar is hidden by `sm:flex` at narrow widths). */}
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

            <div className="sm:hidden border-t border-gray-100 dark:border-gray-800 my-1" />

            <button
              role="menuitem"
              onClick={() => {
                setOptionsOpen(true)
                setOpen(false)
              }}
              className="cursor-pointer w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-800"
              title="Display theme and 3D viewer preferences"
            >
              Options
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
            <button
              role="menuitem"
              onClick={() => {
                setFilesOpen(true)
                setOpen(false)
              }}
              className="cursor-pointer w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-800"
              title="List every file in this report's bundle (sections, GLBs, FEA artefacts, posters, the SQLite db)."
            >
              Bundle files
            </button>
            <a
              role="menuitem"
              href="/admin"
              className="cursor-pointer block w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              Admin
            </a>

            <div className="border-t border-gray-100 dark:border-gray-800 my-1" />

            <button
              role="menuitem"
              onClick={() => {
                void (async () => {
                  try {
                    await clearAllCache()
                  } catch (err) {
                    console.warn('clearAllCache failed:', err)
                  }
                  // Reload bust caches a stale image/section that the
                  // SPA already had in memory but hadn't re-read from
                  // IndexedDB. A hard reload (no cache) also evicts
                  // any HTTP-level cache.
                  window.location.reload()
                })()
              }}
              className="cursor-pointer w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-800"
              title="Wipe IndexedDB-cached manifests / sections / images / plots / tables / 3D blobs and reload"
            >
              Clear cache &amp; reload
            </button>
          </div>
        )}
      </div>

      <OptionsModal open={optionsOpen} onClose={() => setOptionsOpen(false)} />
      <AboutModal open={aboutOpen} onClose={() => setAboutOpen(false)} />
      <UserInfoModal open={userOpen} onClose={() => setUserOpen(false)} />
      <BundleFilesModal
        open={filesOpen}
        onClose={() => setFilesOpen(false)}
        docId={currentDocId}
      />

    </>
  )
}
