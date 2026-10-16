import React from 'react'
import { WebsocketStatusMenu } from './WebsocketStatusMenu'
import { DocSwitcher } from './DocSwitcher'
import { AppMenu } from './AppMenu'
import { BrandMark } from './BrandMark'
import { getRuntimeConfig } from '../transport'
import { usePageViewStore } from '../store/pageViewStore'
import { useLibrary } from './library/useLibrary'
import { Icon } from './library/ui'

// App shell header, shared by the landing page, the Library and the reader:
//
//   [outline] [mark] paradoc / <scope> / <doc title v>      [find] [page] [Library] [menu]
//
// The outline toggle, breadcrumb, find and page-view buttons appear only with
// a doc open. On a phone the bar is 48px, the wordmark and scope crumb drop
// out, and Library / page view move into the menu so the reader keeps its
// content area.

export type ShellView = 'home' | 'library' | 'reader'

const iconBtn =
  'cursor-pointer inline-flex items-center justify-center rounded-md w-9 h-9 text-gray-600 dark:text-gray-400 ' +
  'hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800'

function PageViewToggle() {
  const enabled = usePageViewStore((s) => s.enabled)
  const toggle = usePageViewStore((s) => s.toggle)
  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={enabled}
      aria-label="Page view"
      title={enabled ? 'Page view: A4 sheets (click for web layout)' : 'Web layout (click for A4 page view)'}
      className={
        'cursor-pointer hidden sm:inline-flex items-center justify-center rounded-md w-9 h-9 ' +
        (enabled
          ? 'bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900'
          : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800')
      }
    >
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" className="w-5 h-5" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
      </svg>
    </button>
  )
}

function Sep() {
  return <span className="text-gray-300 dark:text-gray-700 select-none shrink-0">/</span>
}

export function Topbar({
  view,
  connected,
  frontendId,
  docId,
  docScope,
  onSelectDoc,
  onHome,
  onOpenLibrary,
  onOpenSearch,
  onToggleSidebar,
  processInfo,
  connectedFrontends,
  logFilePath,
  workerRef,
}: {
  view: ShellView
  connected: boolean
  frontendId: string
  docId: string
  /** URL-form scope of the open doc (`shared`, `user:me`, `project:<slug>`). */
  docScope: string
  onSelectDoc: (docId: string, scope?: string) => void
  onHome: () => void
  /** Open the Library, optionally filtered to one scope. */
  onOpenLibrary: (scope?: string) => void
  onOpenSearch: () => void
  onToggleSidebar: () => void
  processInfo: { pid: number; thread_id: number } | null
  connectedFrontends: string[]
  logFilePath: string
  workerRef: React.RefObject<Worker | null>
}) {
  const runtimeCfg = getRuntimeConfig()
  // The WS connection pill only makes sense in WS mode; REST and static
  // exports have no socket.
  const isWsMode = runtimeCfg.transport === 'ws'
  const isRest = runtimeCfg.transport === 'rest'
  const headerLinks = runtimeCfg.headerLinks ?? []
  const hasDoc = Boolean(docId)
  const inReader = view === 'reader' && hasDoc
  const scopeName = useLibrary((s) => s.data?.scopes.find((x) => x.ref === docScope)?.name)

  return (
    <header
      id="paradoc-topbar"
      className="sticky top-0 z-10 bg-white/85 dark:bg-gray-950/85 backdrop-blur border-b border-gray-200 dark:border-gray-800"
    >
      <div className="px-2 sm:px-4 lg:px-6 h-12 sm:h-14 flex items-center justify-between gap-2 min-w-0">
        <div className="flex items-center gap-1.5 sm:gap-2 min-w-0 flex-1">
          {inReader && (
            <button className={iconBtn + ' -ml-0.5'} onClick={onToggleSidebar} aria-label="Toggle outline" title="Outline">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" className="w-5 h-5" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h10.5m-10.5 5.25h16.5" />
              </svg>
            </button>
          )}

          {/* Brand: always the way home. */}
          <a
            href="/"
            onClick={(e) => {
              if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
              e.preventDefault()
              onHome()
            }}
            className={
              'inline-flex items-center gap-2 shrink-0 rounded-md px-1.5 py-1 text-gray-900 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 ' +
              (inReader ? '' : 'pl-1')
            }
            title="Home"
            aria-label="paradoc home"
            data-testid="brand-home"
          >
            <BrandMark />
            <span
              className={
                'font-mono text-[13px] font-medium uppercase tracking-[0.18em] ' +
                (inReader ? 'hidden md:inline' : view === 'home' ? 'hidden' : '')
              }
            >
              paradoc
            </span>
          </a>

          {view === 'library' && !hasDoc && (
            <>
              <Sep />
              <span className="text-sm font-medium text-gray-900 dark:text-gray-100">Library</span>
            </>
          )}

          {inReader && (
            <nav aria-label="Breadcrumb" className="flex items-center gap-1 sm:gap-1.5 min-w-0">
              {isRest && scopeName && (
                <>
                  <span className="hidden md:inline"><Sep /></span>
                  <button
                    type="button"
                    onClick={() => onOpenLibrary(docScope)}
                    className="cursor-pointer hidden md:inline truncate max-w-[14rem] rounded-md px-1.5 py-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800"
                    title={`${scopeName} in the Library`}
                  >
                    {scopeName}
                  </button>
                </>
              )}
              <Sep />
              <DocSwitcher
                docId={docId}
                scopeRef={docScope}
                enabled={isRest}
                onSelect={onSelectDoc}
                onOpenLibrary={() => onOpenLibrary()}
              />
            </nav>
          )}

          {isWsMode && (
            <div className="ml-1">
              <WebsocketStatusMenu
                connected={connected}
                frontendId={frontendId}
                processInfo={processInfo}
                connectedFrontends={connectedFrontends}
                logFilePath={logFilePath}
                workerRef={workerRef}
              />
            </div>
          )}

          {headerLinks.length > 0 && (
            <nav className="flex items-center gap-2 ml-1 pl-2 sm:pl-3 border-l border-gray-200 dark:border-gray-800 min-w-0 shrink">
              {headerLinks.map((link, i) => (
                <a
                  key={`${link.href}-${i}`}
                  href={link.href}
                  target={link.target}
                  rel={link.rel ?? (link.target === '_blank' ? 'noopener noreferrer' : undefined)}
                  title={link.label}
                  className="inline-flex items-center px-2 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-semibold bg-blue-600 text-white hover:bg-blue-700 transition whitespace-nowrap max-w-[40vw] truncate"
                >
                  {link.label}
                </a>
              ))}
            </nav>
          )}
        </div>

        <div className="flex items-center gap-0.5 sm:gap-1 shrink-0">
          {inReader && (
            <button type="button" className={iconBtn} onClick={onOpenSearch} aria-label="Find in document" title="Find in document (Ctrl+F)">
              <Icon.Search className="w-[18px] h-[18px]" />
            </button>
          )}
          {inReader && <PageViewToggle />}
          {isRest && view !== 'library' && view !== 'home' && (
            <button
              type="button"
              onClick={() => onOpenLibrary()}
              className="cursor-pointer hidden sm:inline-flex items-center gap-1.5 h-9 px-2.5 rounded-md text-sm text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800"
              title="Library"
            >
              <Icon.Library />
              <span className="hidden lg:inline">Library</span>
            </button>
          )}
          {inReader && <span className="hidden sm:block w-px h-5 bg-gray-200 dark:bg-gray-800 mx-1" />}
          <AppMenu docId={inReader ? docId : ''} onOpenSearch={onOpenSearch} onOpenLibrary={isRest ? () => onOpenLibrary() : undefined} />
        </div>
      </div>
    </header>
  )
}
