import React from 'react'
import { AboutModal } from './AboutModal'
import { UserInfoModal } from './UserInfoModal'
import { BundleFilesModal } from './BundleFilesModal'
import { clearAllCache } from '../sections/store'
import { getRuntimeConfig } from '../transport'
import { authedFetch, isAuthEnabled, isSignedIn, signOut } from '../services/auth/oidc'
import { useTheme, type Theme } from '../store/themeStore'
import { useViewerControlsStore } from '../store/viewerControlsStore'
import { useSourceDisplayStore } from '../store/sourceDisplayStore'
import { usePageViewStore } from '../store/pageViewStore'
import { Icon, menuItem, onMenuKeyDown, useDismiss } from './library/ui'

// The account / options menu at the top right of every view. Grouped:
//   identity header (REST mode),
//   Document   -- only with a doc open: find in document, page view, source
//                 view, 3D viewer controls, bundle files (downloads),
//   Go to      -- phone only: Library (the topbar shows it on wider screens),
//   Appearance -- theme,
//   Account    -- account & API tokens, admin panel (admins), sign out,
//   About, clear cache & reload.
// Arrow keys move between items; Escape and outside clicks close it.

interface Me {
  display_name?: string
  email?: string
  is_admin?: boolean
}

let meCache: Promise<Me | null> | null = null

function fetchMe(): Promise<Me | null> {
  if (!meCache) {
    const cfg = getRuntimeConfig()
    meCache =
      cfg.transport !== 'rest'
        ? Promise.resolve(null)
        : authedFetch((cfg.apiBase || '').replace(/\/?$/, '') + '/api/me', { cache: 'no-store' })
            .then((r) => (r.ok ? (r.json() as Promise<Me>) : null))
            .catch(() => null)
  }
  return meCache
}

export function useMe(): Me | null {
  const [me, setMe] = React.useState<Me | null>(null)
  React.useEffect(() => {
    let live = true
    fetchMe().then((m) => live && setMe(m))
    return () => {
      live = false
    }
  }, [])
  return me
}

function initials(name?: string): string {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return ''
  return ((parts[0][0] || '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

const THEMES: { value: Theme; label: string }[] = [
  { value: 'light', label: 'Light' },
  { value: 'system', label: 'System' },
  { value: 'dark', label: 'Dark' },
]

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-3 pt-2.5 pb-1 text-[10.5px] font-semibold uppercase tracking-[0.14em] text-gray-400 dark:text-gray-500">
      {children}
    </div>
  )
}

function Divider({ className = '' }: { className?: string }) {
  return <div className={`my-1 border-t border-gray-100 dark:border-gray-800 ${className}`} />
}

function Check({ on }: { on: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={
        'ml-auto inline-flex h-4 w-7 shrink-0 items-center rounded-full p-0.5 transition ' +
        (on ? 'bg-sky-600 justify-end' : 'bg-gray-300 dark:bg-gray-700 justify-start')
      }
    >
      <span className="h-3 w-3 rounded-full bg-white shadow" />
    </span>
  )
}

export function AppMenu({
  docId,
  onOpenSearch,
  onOpenLibrary,
}: {
  docId: string
  onOpenSearch?: () => void
  onOpenLibrary?: () => void
}) {
  const [open, setOpen] = React.useState(false)
  const [aboutOpen, setAboutOpen] = React.useState(false)
  const [userOpen, setUserOpen] = React.useState(false)
  const [filesOpen, setFilesOpen] = React.useState(false)
  const ref = React.useRef<HTMLDivElement>(null)
  const panelRef = React.useRef<HTMLDivElement>(null)
  const close = React.useCallback(() => setOpen(false), [])
  useDismiss(open, ref, close)

  const me = useMe()
  const [theme, setTheme] = useTheme()
  const viewer = useViewerControlsStore()
  const source = useSourceDisplayStore()
  const pageView = usePageViewStore((s) => s.enabled)
  const togglePageView = usePageViewStore((s) => s.toggle)
  const rest = getRuntimeConfig().transport === 'rest'
  const hasDoc = Boolean(docId)
  const canSignOut = isAuthEnabled() && isSignedIn()
  const name = me?.display_name || me?.email || ''

  // Focus the first item when the menu opens from the keyboard or a click.
  React.useEffect(() => {
    if (open) panelRef.current?.querySelector<HTMLElement>('[role^=menuitem]')?.focus()
  }, [open])

  const act = (fn: () => void) => () => {
    setOpen(false)
    fn()
  }

  return (
    <>
      <div className="relative" ref={ref}>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-label="Account and options"
          aria-haspopup="menu"
          aria-expanded={open}
          title="Account and options"
          data-testid="app-menu-button"
          className={
            'cursor-pointer inline-flex items-center justify-center rounded-full w-9 h-9 transition ' +
            'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 ' +
            (open ? 'bg-gray-100 dark:bg-gray-800' : '')
          }
        >
          {initials(name) ? (
            <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900 text-[11px] font-semibold tracking-wide">
              {initials(name)}
            </span>
          ) : (
            <svg viewBox="0 0 24 24" className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          )}
        </button>

        {open && (
          <div
            ref={panelRef}
            role="menu"
            aria-label="Account and options"
            onKeyDown={onMenuKeyDown}
            data-testid="app-menu"
            className={
              'absolute right-0 top-full mt-2 z-40 w-[min(18.5rem,calc(100vw-1rem))] max-h-[calc(100dvh-4.5rem)] overflow-y-auto ' +
              'rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-xl shadow-gray-900/10 dark:shadow-black/50 ' +
              'py-1 text-sm text-gray-800 dark:text-gray-100'
            }
          >
            {me && (
              <>
                <div className="px-3 py-2.5 flex items-center gap-3">
                  <span className="inline-flex items-center justify-center w-9 h-9 rounded-full bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900 text-xs font-semibold shrink-0">
                    {initials(name) || '?'}
                  </span>
                  <span className="min-w-0">
                    <span className="flex items-center gap-1.5">
                      <span className="block truncate font-medium text-gray-900 dark:text-gray-100">{me.display_name || 'Signed in'}</span>
                      {me.is_admin && (
                        <span className="shrink-0 rounded bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 px-1.5 text-[10px] font-semibold uppercase tracking-wide">
                          admin
                        </span>
                      )}
                    </span>
                    {me.email && <span className="block truncate text-xs text-gray-500 dark:text-gray-400">{me.email}</span>}
                  </span>
                </div>
                <Divider />
              </>
            )}

            {hasDoc && (
              <>
                <SectionLabel>Document</SectionLabel>
                {onOpenSearch && (
                  <button role="menuitem" type="button" className={menuItem} onClick={act(onOpenSearch)}>
                    <Icon.Search className="w-4 h-4 text-gray-400" />
                    Find in document
                    <kbd className="ml-auto font-mono text-[10.5px] text-gray-400">Ctrl F</kbd>
                  </button>
                )}
                <button role="menuitemcheckbox" aria-checked={pageView} type="button" className={menuItem} onClick={togglePageView}>
                  Page view (A4 sheets)
                  <Check on={pageView} />
                </button>
                <button role="menuitemcheckbox" aria-checked={source.enabled} type="button" className={menuItem} onClick={source.toggleEnabled}>
                  Source view
                  <Check on={source.enabled} />
                </button>
                <button
                  role="menuitemcheckbox"
                  aria-checked={viewer.enabled}
                  type="button"
                  className={menuItem}
                  onClick={viewer.toggleEnabled}
                  title="Show the 3D viewer's own controls (top bar, selection tree, object info)"
                >
                  3D viewer controls
                  <Check on={viewer.enabled} />
                </button>
                <button
                  role="menuitem"
                  type="button"
                  className={menuItem}
                  onClick={act(() => setFilesOpen(true))}
                  title="Every file in this document's bundle, with downloads"
                >
                  Bundle files &amp; downloads…
                </button>
                <Divider />
              </>
            )}

            {rest && onOpenLibrary && (
              <div className="sm:hidden">
                <button role="menuitem" type="button" className={menuItem} onClick={act(onOpenLibrary)}>
                  <Icon.Library className="w-4 h-4 text-gray-400" />
                  Library
                </button>
                <Divider />
              </div>
            )}

            <SectionLabel>Appearance</SectionLabel>
            <div className="px-3 pb-2" role="group" aria-label="Theme">
              <div className="grid grid-cols-3 gap-1 rounded-lg bg-gray-100 dark:bg-gray-800 p-0.5">
                {THEMES.map((t) => (
                  <button
                    key={t.value}
                    type="button"
                    role="menuitemradio"
                    aria-checked={theme === t.value}
                    onClick={() => setTheme(t.value)}
                    className={
                      'cursor-pointer rounded-md py-1 text-xs font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ' +
                      (theme === t.value
                        ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-950 dark:text-gray-100'
                        : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100')
                    }
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
            <Divider />

            {rest && (
              <>
                <SectionLabel>Account</SectionLabel>
                <button role="menuitem" type="button" className={menuItem} onClick={act(() => setUserOpen(true))}>
                  Account &amp; API tokens…
                </button>
                {me?.is_admin && (
                  <a role="menuitem" href="/admin" className={menuItem}>
                    Admin panel
                  </a>
                )}
                {canSignOut && (
                  <button role="menuitem" type="button" className={menuItem} onClick={act(() => void signOut())}>
                    Sign out
                  </button>
                )}
                <Divider />
              </>
            )}

            <button role="menuitem" type="button" className={menuItem} onClick={act(() => setAboutOpen(true))}>
              About paradoc…
            </button>
            <button
              role="menuitem"
              type="button"
              className={menuItem}
              title="Wipe cached manifests, sections, images, plots, tables and 3D blobs, then reload"
              onClick={act(() => {
                void (async () => {
                  try {
                    await clearAllCache()
                  } catch (err) {
                    console.warn('clearAllCache failed:', err)
                  }
                  window.location.reload()
                })()
              })}
            >
              Clear cache &amp; reload
            </button>
          </div>
        )}
      </div>

      <AboutModal open={aboutOpen} onClose={() => setAboutOpen(false)} />
      <UserInfoModal open={userOpen} onClose={() => setUserOpen(false)} />
      <BundleFilesModal open={filesOpen} onClose={() => setFilesOpen(false)} docId={docId} />
    </>
  )
}
