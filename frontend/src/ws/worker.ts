// Web Worker to maintain a persistent WebSocket connection and forward HTML to the UI
// Runs in its own thread. Reconnects with backoff and sends heartbeats to keep the connection alive.

// In a worker, self is DedicatedWorkerGlobalScope
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ctx: any = self as any

const WS_URL = 'ws://localhost:13579'

let ws: WebSocket | null = null
let stopped = false
let reconnectAttempts = 0
let heartbeatTimer: number | null = null

function scheduleReconnect() {
  if (stopped) return
  reconnectAttempts++
  const delay = Math.min(30000, 1000 * Math.pow(2, Math.min(5, reconnectAttempts))) // 1s → 32s, capped at 30s
  setTimeout(connect, delay)
}

function clearHeartbeat() {
  if (heartbeatTimer !== null) {
    clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }
}

function startHeartbeat() {
  clearHeartbeat()
  // Send a ping every 20s to keep NATs/IDS from closing idle connections
  heartbeatTimer = setInterval(() => {
    try {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send('') // empty ping
      }
    } catch {
      // ignore
    }
  }, 20000) as unknown as number
}

function connect() {
  if (stopped) return

  try {
    ws = new WebSocket(WS_URL)
  } catch (e) {
    // Unable to construct; try again later
    scheduleReconnect()
    return
  }

  ws.addEventListener('open', () => {
    reconnectAttempts = 0
    startHeartbeat()
    ctx.postMessage({ type: 'status', connected: true })
  })

  ws.addEventListener('close', () => {
    ctx.postMessage({ type: 'status', connected: false })
    clearHeartbeat()
    scheduleReconnect()
  })

  ws.addEventListener('error', () => {
    ctx.postMessage({ type: 'status', connected: false })
  })

  ws.addEventListener('message', (event: MessageEvent) => {
    const raw = event.data
    if (typeof raw !== 'string') return
    const data = raw.trim()
    if (!data) return

    // Try to detect JSON bundle first
    if (data.startsWith('{')) {
      try {
        const obj = JSON.parse(data)
        if (obj && obj.kind === 'html_bundle' && typeof obj.html === 'string') {
          ctx.postMessage({ type: 'bundle', payload: obj })
          return
        }
        // New: AST streaming support
        if (obj && obj.kind === 'manifest' && obj.manifest) {
          ctx.postMessage({ type: 'manifest', manifest: obj.manifest })
          return
        }
        if (obj && obj.kind === 'ast_section' && obj.section && obj.doc) {
          ctx.postMessage({ type: 'ast_section', bundle: { section: obj.section, doc: obj.doc } })
          return
        }
        // New: Embedded images support
        if (obj && obj.kind === 'embedded_images' && obj.images) {
          ctx.postMessage({ type: 'embedded_images', images: obj.images })
          return
        }
        // New: Plot data support
        if (obj && obj.kind === 'plot_data' && obj.data) {
          ctx.postMessage({ type: 'plot_data', plots: obj.data })
          return
        }
        // New: Table data support
        if (obj && obj.kind === 'table_data' && obj.data) {
          ctx.postMessage({ type: 'table_data', tables: obj.data })
          return
        }
        // New: Process info response
        if (obj && obj.kind === 'process_info') {
          ctx.postMessage({ type: 'process_info', pid: obj.pid, thread_id: obj.thread_id })
          return
        }
        // New: Shutdown acknowledgment
        if (obj && obj.kind === 'shutdown_ack') {
          ctx.postMessage({ type: 'shutdown_ack' })
          return
        }
      } catch {
        // fall through to plain html
      }
    }
    ctx.postMessage({ type: 'html', html: data })
  })
}

// Allow main thread to forward HTML back to the server if needed
ctx.addEventListener('message', (event: MessageEvent) => {
  const msg = event.data
  if (!msg) return
  if (msg.type === 'stop') {
    stopped = true
    try { ws?.close() } catch {}
    clearHeartbeat()
    return
  }
  if (msg.type === 'send' && typeof msg.html === 'string') {
    try {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(msg.html)
      }
    } catch {}
  }
  // New: Request process info
  if (msg.type === 'get_process_info') {
    try {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ kind: 'get_process_info' }))
      }
    } catch {}
  }
  // New: Send shutdown command
  if (msg.type === 'shutdown') {
    try {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ kind: 'shutdown' }))
      }
    } catch {}
  }
})

connect()
