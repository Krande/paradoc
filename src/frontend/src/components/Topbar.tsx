import React from 'react'
import { useSourceDisplayStore } from '../store/sourceDisplayStore'
import { WebsocketStatusMenu } from './WebsocketStatusMenu'
import { DocSwitcher } from './DocSwitcher'
import { OverflowMenu } from './OverflowMenu'
import { ThemeToggle } from './ThemeToggle'
import { useDocList } from './useDocList'
import { getRuntimeConfig } from '../transport'

// Inline favicon glyph — same paths as public/favicon.svg, but rendered
// inline so it inherits `currentColor` and adapts to dark mode without
// fetching a second copy.
function BrandMark({ className = 'w-5 h-5' }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M5 3 H14 L19 8 V21 H5 Z" />
      <path d="M14 3 V8 H19" />
      <path d="M7 17 L10 13 L13 15 L17 10" />
    </svg>
  )
}

export function Topbar({
  connected,
  frontendId,
  docId,
  onSelectDoc,
  onToggleSidebar,
  processInfo,
  connectedFrontends,
  logFilePath,
  workerRef,
}: {
  connected: boolean
  frontendId: string
  docId: string
  onSelectDoc: (docId: string) => void
  onToggleSidebar: () => void
  processInfo: { pid: number; thread_id: number } | null
  connectedFrontends: string[]
  logFilePath: string
  workerRef: React.RefObject<Worker | null>
}) {
  const { enabled: sourceDisplayEnabled, toggleEnabled: toggleSourceDisplay } =
    useSourceDisplayStore()
  const runtimeCfg = getRuntimeConfig()
  const isRestMode = runtimeCfg.transport === 'rest'
  const headerLinks = runtimeCfg.headerLinks ?? []
  const { allDocs } = useDocList()
  const hasDoc = Boolean(docId)

  return (
    <header
      id="paradoc-topbar"
      className="sticky top-0 z-10 bg-white/80 dark:bg-gray-950/80 backdrop-blur border-b border-gray-200 dark:border-gray-800"
    >
      <div className="max-w-full mx-auto px-2 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-2 min-w-0">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <button
            className="cursor-pointer -ml-2 inline-flex items-center justify-center rounded p-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800"
            onClick={onToggleSidebar}
            aria-label="Toggle contents"
            title="Toggle Outline"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth="1.5"
              stroke="currentColor"
              className="w-6 h-6"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
              />
            </svg>
          </button>

          {/* Brand mark + product name. Acts as a "go home" affordance:
              clicking clears the open doc. */}
          <button
            onClick={() => hasDoc && onSelectDoc('')}
            className="inline-flex items-center gap-1.5 text-gray-900 dark:text-gray-100 cursor-pointer hover:opacity-80 transition"
            title={hasDoc ? 'Back to all reports' : 'paradoc'}
          >
            <BrandMark />
            <span className="text-sm font-semibold tracking-tight">paradoc</span>
          </button>

          {/* Breadcrumb separator + doc switcher chip. Only appears when
              a doc is open. WS mode still wants the WS status pill, so
              we keep that to the right of the breadcrumb. */}
          {hasDoc && (
            <>
              <span className="text-gray-300 dark:text-gray-700 select-none">/</span>
              <div className="min-w-0 shrink truncate">
                <DocSwitcher currentDocId={docId} onSelect={onSelectDoc} />
              </div>
            </>
          )}

          {!isRestMode && (
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
                  rel={
                    link.rel ?? (link.target === '_blank' ? 'noopener noreferrer' : undefined)
                  }
                  title={link.label}
                  className="inline-flex items-center px-2 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-semibold bg-blue-600 text-white hover:bg-blue-700 transition whitespace-nowrap max-w-[40vw] truncate"
                >
                  {link.label}
                </a>
              ))}
            </nav>
          )}
        </div>

        <div className="flex items-center gap-2 min-w-0">
          <div className="hidden sm:block">
            <ThemeToggle />
          </div>
          <OverflowMenu
            sourceDisplayEnabled={sourceDisplayEnabled}
            onToggleSourceDisplay={toggleSourceDisplay}
            docs={allDocs}
            currentDocId={docId}
            onSelectDoc={onSelectDoc}
          />
        </div>
      </div>
    </header>
  )
}
