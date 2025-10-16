// Mock WebSocket server for development, fully inside the frontend (browser) using mock-socket.
// It is initialized from main.tsx so no external Node process is required.

import { Server, WebSocket as MockWebSocket } from 'mock-socket'

const WS_URL = 'ws://localhost:13579'

let started = false
let server: Server | null = null

const MOCK_HTML = `
  <main class="prose mx-auto p-6">
    <h1>Welcome</h1>
    <p>This content was sent from the in-app mock WebSocket server upon connection.</p>
    <h2>Section</h2>
    <p>Use your backend to push real pandoc-converted HTML here.</p>
  </main>
`

export function initMockServer() {
  if (started || !import.meta.env.DEV) return
  started = true

  // Ensure the app's WebSocket uses the mock implementation in dev
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(globalThis as any).WebSocket = MockWebSocket

  server = new Server(WS_URL)

  server.on('connection', (socket) => {
    try {
      socket.send(MOCK_HTML)
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
    console.error('[mock-ws] error:', err)
  })

  // eslint-disable-next-line no-console
  console.log(`[mock-ws] In-app WebSocket server listening at ${WS_URL}`)
}

export function stopMockServer() {
  if (server) {
    server.stop()
    server = null
    started = false
  }
}
