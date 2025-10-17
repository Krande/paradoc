import React from 'react'

export function Topbar({ connected, onSendMock, onToggleSidebar }: { connected: boolean; onSendMock: () => void; onToggleSidebar: () => void }) {
  return (
    <header id="paradoc-topbar" className="sticky top-0 z-10 bg-white/70 backdrop-blur border-b border-gray-200">
      <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            className="cursor-pointer -ml-2 md:hidden inline-flex items-center justify-center rounded p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100"
            onClick={onToggleSidebar}
            aria-label="Toggle contents"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" className="w-6 h-6">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>
          <div className="w-2 h-2 rounded-full "
               title={connected ? 'WebSocket connected' : 'WebSocket disconnected'}
               style={{ backgroundColor: connected ? '#22c55e' : '#ef4444' }} />
          <h1 className="text-sm font-semibold tracking-wide text-gray-700">Paradoc Reader</h1>
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
