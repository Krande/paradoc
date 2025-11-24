import React, { useState, RefObject } from 'react'

interface WebsocketStatusMenuProps {
    connected: boolean
    frontendId: string
    workerRef: RefObject<Worker | null>
    processInfo: { pid: number; thread_id: number } | null
    connectedFrontends: string[]
    logFilePath: string
}

export function WebsocketStatusMenu({
    connected,
    frontendId,
    workerRef,
    processInfo,
    connectedFrontends,
    logFilePath
}: WebsocketStatusMenuProps) {
    const [menuOpen, setMenuOpen] = useState(false)
    const [editingId, setEditingId] = useState(false)
    const [tempId, setTempId] = useState('')
    const [showFrontendsList, setShowFrontendsList] = useState(false)

    const onRequestProcessInfo = () => {
        if (workerRef.current && connected) {
            workerRef.current.postMessage({ type: 'get_process_info' })
        }
    }

    const onRequestConnectedFrontends = () => {
        if (workerRef.current && connected) {
            workerRef.current.postMessage({ type: 'get_connected_frontends' })
        }
    }

    const onRequestLogFilePath = () => {
        if (workerRef.current && connected) {
            workerRef.current.postMessage({ type: 'get_log_file_path' })
        }
    }

    const onKillServer = () => {
        if (workerRef.current && connected) {
            workerRef.current.postMessage({ type: 'shutdown' })
        }
    }

    const onSetFrontendId = (newId: string) => {
        if (workerRef.current) {
            workerRef.current.postMessage({ type: 'set_frontend_id', frontendId: newId })
        }
    }

    const handleInfoClick = () => {
        if (!menuOpen && connected) {
            onRequestProcessInfo()
            onRequestConnectedFrontends()
            onRequestLogFilePath()
        }
        setMenuOpen(!menuOpen)
    }

    const handleEditId = () => {
        setTempId(frontendId)
        setEditingId(true)
    }

    const handleSaveId = () => {
        if (tempId && tempId !== frontendId) {
            onSetFrontendId(tempId)
        }
        setEditingId(false)
    }

    const handleCancelEdit = () => {
        setEditingId(false)
        setTempId('')
    }

    return (
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
                        className="absolute top-full left-0 mt-2 w-80 bg-white border border-gray-200 rounded-lg shadow-lg z-30 p-3">
                        <div className="text-sm font-semibold text-gray-700 mb-2">Paradoc Reader Info</div>
                        <div className="text-xs text-gray-600 space-y-2 mb-3">
                            <div className="border-b border-gray-200 pb-2">
                                <div className="font-medium text-gray-700 mb-1">Frontend Instance</div>
                                {!editingId ? (
                                    <div className="flex items-center justify-between gap-2">
                                        <span className="font-mono text-xs truncate flex-1" title={frontendId}>
                                            {frontendId || 'Loading...'}
                                        </span>
                                        <button
                                            className="cursor-pointer text-xs px-2 py-1 rounded bg-blue-100 text-blue-700 hover:bg-blue-200"
                                            onClick={handleEditId}
                                        >
                                            Edit
                                        </button>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        <input
                                            type="text"
                                            className="w-full text-xs font-mono px-2 py-1 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            value={tempId}
                                            onChange={(e) => setTempId(e.target.value)}
                                            placeholder="Enter frontend ID"
                                        />
                                        <div className="flex gap-2">
                                            <button
                                                className="cursor-pointer flex-1 text-xs px-2 py-1 rounded bg-green-600 text-white hover:bg-green-700"
                                                onClick={handleSaveId}
                                            >
                                                Save
                                            </button>
                                            <button
                                                className="cursor-pointer flex-1 text-xs px-2 py-1 rounded bg-gray-300 text-gray-700 hover:bg-gray-400"
                                                onClick={handleCancelEdit}
                                            >
                                                Cancel
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>

                            <div className="border-b border-gray-200 pb-2">
                                <div className="font-medium text-gray-700 mb-1">WebSocket Server</div>
                                <div className="flex justify-between">
                                    <span className="font-medium">Status:</span>
                                    <span className={connected ? 'text-green-600' : 'text-red-600'}>
                                        {connected ? 'Connected' : 'Disconnected'}
                                    </span>
                                </div>
                                {connected && (
                                    <div className="flex justify-between items-center mt-1">
                                        <span className="font-medium">Connected Frontends:</span>
                                        <button
                                            className="cursor-pointer text-blue-600 hover:text-blue-800 font-medium"
                                            onClick={() => setShowFrontendsList(!showFrontendsList)}
                                            title="Click to show/hide frontend list"
                                        >
                                            {connectedFrontends.length}
                                            <span className="ml-1 text-xs">
                                                {showFrontendsList ? '▼' : '▶'}
                                            </span>
                                        </button>
                                    </div>
                                )}
                                {showFrontendsList && connectedFrontends.length > 0 && (
                                    <div className="mt-2 pl-2 border-l-2 border-blue-200">
                                        <div className="text-xs text-gray-500 mb-1">Frontend Instances:</div>
                                        {connectedFrontends.map((fid) => (
                                            <div
                                                key={fid}
                                                className={`text-xs font-mono px-2 py-1 rounded mb-1 ${
                                                    fid === frontendId
                                                        ? 'bg-blue-100 text-blue-900 font-semibold'
                                                        : 'bg-gray-50 text-gray-700'
                                                }`}
                                                title={fid}
                                            >
                                                {fid === frontendId && (
                                                    <span className="text-blue-600 mr-1">●</span>
                                                )}
                                                {fid.length > 30 ? fid.substring(0, 30) + '...' : fid}
                                            </div>
                                        ))}
                                    </div>
                                )}
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
                            <div className="border-b border-gray-200 pb-2">
                                <div className="font-medium text-gray-700 mb-1">Log File Path</div>
                                <div className="text-xs font-mono text-gray-600 break-words">
                                    {logFilePath || 'N/A'}
                                </div>
                            </div>
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
    )
}
