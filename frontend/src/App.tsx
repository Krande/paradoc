import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Topbar } from './components/Topbar'
import { Navbar, TocItem } from './components/Navbar'

const WS_URL = 'ws://localhost:13579'

const MOCK_HTML = `
  <main>
    <h1 id="intro">Introduction</h1>
    <p>Welcome to Paradoc. This is a starter document. Use the WebSocket to stream new HTML documents.</p>
    <h2>Background</h2>
    <p>Some background text.</p>
    <h2 id="appendix">Appendix</h2>
    <h3>Extra Material</h3>
    <p>Details in the appendix section.</p>
  </main>
`

export default function App() {
  const [connected, setConnected] = useState<boolean>(false)
  const [docHtml, setDocHtml] = useState<string>(MOCK_HTML)
  const wsRef = useRef<WebSocket | null>(null)

  // Parse HTML into a Document for TOC extraction
  const doc = useMemo(() => {
    const parser = new DOMParser()
    return parser.parseFromString(docHtml, 'text/html')
  }, [docHtml])

  const [toc, setToc] = useState<TocItem[]>([])

  useEffect(() => {
    // Extract appendix start from meta
    const meta = document.querySelector('meta[name="data-appendix-start"]') as HTMLMetaElement | null
    const appendixStartText = (meta?.content || 'Appendix').replace(/\s+/g, '')

    const headers = Array.from(doc.querySelectorAll('h1, h2, h3, h4, h5, h6')) as HTMLHeadingElement[]

    let counters = [0, 0, 0, 0, 0, 0]
    let currentAppendixLetter = 'A'
    let inAppendix = false
    const items: TocItem[] = []

    headers.forEach((header) => {
      const level = parseInt(header.tagName.substring(1)) - 1
      const headerText = (header.textContent || '').replace(/\s+/g, '')

      if (headerText === appendixStartText) {
        inAppendix = true
        counters = [0, 0, 0, 0, 0, 0]
      }

      let number: string
      if (inAppendix) {
        if (level === 0) {
          if (counters[0] > 0) {
            currentAppendixLetter = String.fromCharCode(currentAppendixLetter.charCodeAt(0) + 1)
          }
          counters = [0, 0, 0, 0, 0, 0]
        }
        counters[level]++
        number = (level === 0 ? 'Appendix ' : '') +
          currentAppendixLetter +
          (level > 0 ? '.' + counters.slice(1, level + 1).join('.') : '')
      } else {
        counters[level]++
        number = counters.slice(0, level + 1).join('.')
      }

      for (let i = level + 1; i < counters.length; i++) counters[i] = 0

      if (!header.id) header.id = `heading-${number}`
      header.textContent = `${number} ${header.textContent || ''}`

      items.push({ id: header.id, text: header.textContent || '', level })
    })

    setToc(items)
  }, [doc])

  useEffect(() => {
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws
    ws.addEventListener('open', () => setConnected(true))
    ws.addEventListener('close', () => setConnected(false))
    ws.addEventListener('error', () => setConnected(false))

    ws.addEventListener('message', (event) => {
      const data = typeof event.data === 'string' ? event.data : ''
      if (data.trim()) {
        setDocHtml(data)
      }
    })

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [])

  const sendHtml = (html: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(html)
    }
  }

  return (
    <div className="flex min-h-screen">
      <Navbar toc={toc} />
      <div className="flex-1 flex flex-col">
        <Topbar connected={connected} onSendMock={() => sendHtml(MOCK_HTML)} />
        <DocumentView html={docHtml} />
      </div>
    </div>
  )
}

function DocumentView({ html }: { html: string }) {
  return (
    <div className="flex-1 overflow-auto p-6">
      <div
        className="prose max-w-4xl mx-auto"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  )
}
