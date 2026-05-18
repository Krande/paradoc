import React from 'react'
import { useSourceDisplayStore } from '../store/sourceDisplayStore'
import { WebsocketStatusMenu } from './WebsocketStatusMenu'
import { DocSwitcher } from './DocSwitcher'
import { OverflowMenu } from './OverflowMenu'
import { useDocList } from './useDocList'
import { getRuntimeConfig } from '../transport'

export function Topbar({
                           connected,
                           frontendId,
                           docId,
                           onSelectDoc,
                           onToggleSidebar,
                           processInfo,
                           connectedFrontends,
                           logFilePath,
                           workerRef
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
    const { enabled: sourceDisplayEnabled, toggleEnabled: toggleSourceDisplay } = useSourceDisplayStore()
    // The WS status pill (connection dot, "i" info popover, kill-server
    // button) is meaningless in REST mode — the worker isn't even
    // connected. Show a plain title instead so the topbar still
    // identifies the app.
    const runtimeCfg = getRuntimeConfig()
    const isRestMode = runtimeCfg.transport === 'rest'
    const headerLinks = runtimeCfg.headerLinks ?? []
    const { allDocs } = useDocList()

    return (
        <header id="paradoc-topbar" className="sticky top-0 z-10 bg-white/70 backdrop-blur border-b border-gray-200">
            {/* `min-w-0` on flex children + tighter padding on mobile keeps
                the row from overflowing the viewport on phones. The
                inline Source/DocSwitcher controls move into the kebab
                menu via `hidden sm:flex`. */}
            <div className="max-w-full mx-auto px-2 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-2 min-w-0">
                <div className="flex items-center gap-3">
                    <button
                        className="cursor-pointer -ml-2 inline-flex items-center justify-center rounded p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100"
                        onClick={onToggleSidebar}
                        aria-label="Toggle contents"
                        title="Toggle Outline"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5"
                             stroke="currentColor" className="w-6 h-6">
                            <path strokeLinecap="round" strokeLinejoin="round"
                                  d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"/>
                        </svg>
                    </button>
                    {isRestMode ? (
                        <h1 className="text-sm font-semibold tracking-wide text-gray-700">Paradoc Reader</h1>
                    ) : (
                        <WebsocketStatusMenu
                            connected={connected}
                            frontendId={frontendId}
                            processInfo={processInfo}
                            connectedFrontends={connectedFrontends}
                            logFilePath={logFilePath}
                            workerRef={workerRef}
                        />
                    )}
                    {headerLinks.length > 0 && (
                        <nav className="hidden sm:flex items-center gap-2 ml-2 pl-3 border-l border-gray-200">
                            {headerLinks.map((link, i) => (
                                <a
                                    key={`${link.href}-${i}`}
                                    href={link.href}
                                    target={link.target}
                                    rel={link.rel ?? (link.target === '_blank' ? 'noopener noreferrer' : undefined)}
                                    className="text-xs font-medium text-blue-600 hover:text-blue-800 hover:underline"
                                >
                                    {link.label}
                                </a>
                            ))}
                        </nav>
                    )}
                </div>
                <div className="flex items-center gap-2 sm:gap-3 min-w-0">
                    <button
                        className={`hidden sm:inline-flex cursor-pointer text-xs font-medium px-3 py-1.5 rounded-md transition items-center ${
                            sourceDisplayEnabled
                                ? 'bg-blue-600 text-white hover:bg-blue-700'
                                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                        }`}
                        onClick={toggleSourceDisplay}
                        title={sourceDisplayEnabled ? 'Hide source file locations' : 'Show source file locations'}
                    >
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth="1.5"
                            stroke="currentColor"
                            className="w-4 h-4 inline-block mr-1"
                        >
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                        </svg>
                        Source
                    </button>
                    <div className="hidden sm:block">
                        <DocSwitcher currentDocId={docId} onSelect={onSelectDoc} />
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
