import React, {useState} from 'react'

export function Topbar({
                           connected,
                           onSendMock,
                           onToggleSidebar,
                           onRequestProcessInfo,
                           onKillServer,
                           processInfo
                       }: {
    connected: boolean
    onSendMock: () => void
    onToggleSidebar: () => void
    onRequestProcessInfo: () => void
    onKillServer: () => void
    processInfo: { pid: number; thread_id: number } | null
}) {
    const [menuOpen, setMenuOpen] = useState(false)

    const handleInfoClick = () => {
        if (!menuOpen && connected) {
            onRequestProcessInfo()
        }
        setMenuOpen(!menuOpen)
    }

    return (
        <header id="paradoc-topbar" className="sticky top-0 z-10 bg-white/70 backdrop-blur border-b border-gray-200">
            <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <button
                        className="cursor-pointer -ml-2 md:hidden inline-flex items-center justify-center rounded p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100"
                        onClick={onToggleSidebar}
                        aria-label="Toggle contents"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5"
                             stroke="currentColor" className="w-6 h-6">
                            <path strokeLinecap="round" strokeLinejoin="round"
                                  d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"/>
                        </svg>
                    </button>
                    <div className="flex items-center gap-2 relative">
                        <div className="w-2 h-2 rounded-full "
                             title={connected ? 'WebSocket connected' : 'WebSocket disconnected'}
                             style={{backgroundColor: connected ? '#22c55e' : '#ef4444'}}/>
                        <h1 className="text-sm font-semibold tracking-wide text-gray-700">Paradoc Reader</h1>
                        <button
                            className="cursor-pointer w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold text-white bg-gray-500 hover:bg-gray-600 transition"
                            onClick={handleInfoClick}
                            title="Server info"
                        >
                            i
                        </button>
                        {menuOpen && (
                            <>
                                <div
                                    className="fixed inset-0 z-20"
                                    onClick={() => setMenuOpen(false)}
                                />
                                <div
                                    className="absolute top-full left-0 mt-2 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-30 p-3">
                                    <div className="text-sm font-semibold text-gray-700 mb-2">WebSocket Server</div>
                                    <div className="text-xs text-gray-600 space-y-1 mb-3">
                                        <div className="flex justify-between">
                                            <span className="font-medium">Status:</span>
                                            <span className={connected ? 'text-green-600' : 'text-red-600'}>
                        {connected ? 'Connected' : 'Disconnected'}
                      </span>
                                        </div>
                                        {processInfo && (
                                            <>
                                                <div className="flex justify-between">
                                                    <span className="font-medium">Process ID:</span>
                                                    <span className="font-mono">{processInfo.pid}</span>
                                                </div>
                                                <div className="flex justify-between">
                                                    <span className="font-medium">Thread ID:</span>
                                                    <span className="font-mono">{processInfo.thread_id}</span>
                                                </div>
                                            </>
                                        )}
                                        {!processInfo && connected && (
                                            <div className="text-gray-400 italic">Loading server info...</div>
                                        )}
                                    </div>
                                    {connected && (
                                        <button
                                            className="cursor-pointer w-full text-xs font-medium px-3 py-2 rounded-md bg-red-600 text-white hover:bg-red-700 transition"
                                            onClick={() => {
                                                onKillServer()
                                                setMenuOpen(false)
                                            }}
                                        >
                                            Kill WS Server
                                        </button>
                                    )}
                                </div>
                            </>
                        )}
                    </div>

                </div>
                <div className="flex items-center gap-3">
                    <button
                        className="cursor-pointer text-xs font-medium px-3 py-1.5 rounded-md bg-gray-900 text-white hover:bg-gray-800 transition"
                        onClick={onSendMock}
                    >
                        Send Mock
                    </button>
                </div>
            </div>
        </header>
    )
}
