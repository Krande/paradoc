// Simple WebSocket server that accepts HTML payloads and broadcasts to all clients
// Starts automatically with `npm run dev`

import { WebSocketServer } from 'ws'

const PORT = 13579
const wss = new WebSocketServer({ port: PORT })

const MOCK_HTML = `
  <main class="prose mx-auto p-6">
    <h1>Welcome</h1>
    <p>This content was sent from the dev WebSocket server upon connection.</p>
    <h2>Section</h2>
    <p>Use your backend to push real pandoc-converted HTML here.</p>
  </main>
`

wss.on('connection', (ws) => {
  try {
    ws.send(MOCK_HTML)
  } catch {}

  ws.on('message', (message) => {
    // Treat messages as HTML content and broadcast to all clients
    const html = message.toString()
    wss.clients.forEach((client) => {
      if (client.readyState === 1) {
        try { client.send(html) } catch {}
      }
    })
  })
})

wss.on('listening', () => {
  console.log(`[ws] WebSocket server listening on ws://localhost:${PORT}`)
})

wss.on('error', (err) => {
  console.error('[ws] error:', err)
})
