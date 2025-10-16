// Embedded WebSocket listener for development, running inside the browser via mock-socket.
// Initialized from main.tsx so no external Node process is required.

import { Server, WebSocket as MockWebSocket } from 'mock-socket'

const WS_URL = 'ws://localhost:13579'

let started = false
let server: Server | null = null

const WELCOME_HTML = `
  <main>
    <h1>Welcome</h1>
    <p>This content was sent from the in-app WebSocket listener upon connection.</p>
    <h2>Section</h2>
    <p>Use your backend to push real pandoc-converted HTML here.</p>
  </main>
`

export function initWsListener() {
  if (started || !import.meta.env.DEV) return
  started = true

  // Patch global WebSocket with the mock implementation in dev so the app connects locally.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(globalThis as any).WebSocket = MockWebSocket

  server = new Server(WS_URL)

  server.on('connection', (socket) => {
    try {
      socket.send(WELCOME_HTML)
    } catch {}

    socket.on('message', (data) => {
      const html = typeof data === 'string' ? data : data?.toString?.() ?? ''
      // Broadcast to all connected clients
      server?.clients().forEach((client) => {
        try {
          client.send(html)
        } catch {}
      })
    })
  })

  server.on('error', (err) => {
    // eslint-disable-next-line no-console
    console.error('[ws-listener] error:', err)
  })

  // eslint-disable-next-line no-console
  console.log(`[ws-listener] In-app WebSocket listener active at ${WS_URL}`)
}

export function stopWsListener() {
  if (server) {
    server.stop()
    server = null
    started = false
  }
}
