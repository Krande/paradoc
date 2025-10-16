import React from 'react'

export function Topbar({ connected, onSendMock }: { connected: boolean; onSendMock: () => void }) {
  return (
    <header className="sticky top-0 z-10 bg-white/80 backdrop-blur border-b border-gray-200">
      <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
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
