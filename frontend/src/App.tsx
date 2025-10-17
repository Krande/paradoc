import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Topbar } from './components/Topbar'
import { Navbar, TocItem } from './components/Navbar'

// WebSocket management is delegated to a Web Worker that reconnects and forwards messages
// Vite will inline the worker into the single-file build
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
const WorkerCtor = (URL as any) ? (url: string) => new Worker(new URL(url, import.meta.url), { type: 'module' }) : null

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
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false)
  const workerRef = useRef<Worker | null>(null)

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
    // Start the WS worker (runs in a dedicated thread)
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore
    const worker: Worker = new Worker(new URL('./ws/worker.ts', import.meta.url), { type: 'module' })
    workerRef.current = worker

    const toBlobUrl = (b64: string, mime: string) => {
      try {
        const byteStr = atob(b64)
        const bytes = new Uint8Array(byteStr.length)
        for (let i = 0; i < byteStr.length; i++) bytes[i] = byteStr.charCodeAt(i)
        const blob = new Blob([bytes], { type: mime || 'application/octet-stream' })
        return URL.createObjectURL(blob)
      } catch {
        return ''
      }
    }

    const rewriteHtmlWithAssets = (html: string, payload: any) => {
      try {
        const parser = new DOMParser()
        const doc = parser.parseFromString(html, 'text/html')

        // Inline styles if provided
        if (Array.isArray(payload?.styles)) {
          payload.styles.forEach((s: any) => {
            if (s && typeof s.text === 'string') {
              const styleEl = document.createElement('style')
              styleEl.setAttribute('data-paradoc-style', s.path || '')
              styleEl.textContent = s.text
              doc.head.appendChild(styleEl)
            }
          })
        }

        // Build a lookup for assets
        const assetMap: Record<string, { mime: string, b64: string }> = {}
        if (Array.isArray(payload?.assets)) {
          payload.assets.forEach((a: any) => {
            if (a && typeof a.path === 'string' && typeof a.b64 === 'string') {
              assetMap[a.path] = { mime: a.mime || 'application/octet-stream', b64: a.b64 }
              // Persist in localStorage (best-effort; may fail if over quota)
              try { localStorage.setItem(`paradoc:asset:${a.path}`, JSON.stringify(assetMap[a.path])) } catch {}
            }
          })
        }

        // Rewrite <img src>
        doc.querySelectorAll('img[src]').forEach((img) => {
          const src = img.getAttribute('src') || ''
          if (!src || src.startsWith('http') || src.startsWith('data:')) return
          const key = src.replace('\\\\', '/').replace('\\\
', '/')
          const a = assetMap[key] || assetMap[src]
          if (a) {
            const url = toBlobUrl(a.b64, a.mime)
            if (url) img.setAttribute('src', url)
          }
        })

        // Remove external stylesheet links we may have inlined
        doc.querySelectorAll('link[rel="stylesheet"][href]').forEach((lnk) => {
          const href = lnk.getAttribute('href') || ''
          if (!href) return
          // If we have this css inlined, drop the link
          if (assetMap[href]) lnk.parentElement?.removeChild(lnk)
        })

        return doc.documentElement.outerHTML
      } catch {
        return html
      }
    }

    const onMessage = (event: MessageEvent) => {
      const msg = event.data
      if (!msg) return
      if (msg.type === 'status') {
        setConnected(!!msg.connected)
      } else if (msg.type === 'html' && typeof msg.html === 'string') {
        if (msg.html.trim()) setDocHtml(msg.html)
      } else if (msg.type === 'bundle' && msg.payload && typeof msg.payload.html === 'string') {
        const transformed = rewriteHtmlWithAssets(msg.payload.html, msg.payload)
        if (transformed.trim()) setDocHtml(transformed)
      }
    }

    worker.addEventListener('message', onMessage)

    return () => {
      try { worker.postMessage({ type: 'stop' }) } catch {}
      worker.removeEventListener('message', onMessage)
      worker.terminate()
      workerRef.current = null
    }
  }, [])

  const sendHtml = (html: string) => {
    if (workerRef.current) {
      workerRef.current.postMessage({ type: 'send', html })
    }
  }

  return (
    <div className="flex min-h-screen">
      <Navbar toc={toc} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 flex flex-col">
        <Topbar connected={connected} onSendMock={() => sendHtml(MOCK_HTML)} onToggleSidebar={() => setSidebarOpen((v) => !v)} />
        <DocumentView html={docHtml} />
      </div>
    </div>
  )
}

function DocumentView({ html }: { html: string }) {
  return (
    <div className="flex-1 overflow-auto p-6">
      <div
        className="prose max-w-none w-full"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  )
}
