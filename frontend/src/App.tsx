import React, { useEffect, useRef, useState } from 'react'
import { Topbar } from './components/Topbar'
import { Navbar, TocItem } from './components/Navbar'

// WebSocket management is delegated to a Web Worker that reconnects and forwards messages
// Vite will inline the worker into the single-file build
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
const WorkerCtor = (URL as any) ? (url: string) => new Worker(new URL(url, import.meta.url), { type: 'module' }) : null

import { useSectionStore, fetchManifest, fetchSection } from './sections/store'
import type { DocManifest, SectionBundle } from './ast/types'
import { VirtualReader } from './components/VirtualReader'

export default function App() {
  const [connected, setConnected] = useState<boolean>(false)
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false)
  const workerRef = useRef<Worker | null>(null)

  // AST/Sections store
  const { state, setManifest, upsertSection } = useSectionStore()
  const [docId, setDocId] = useState<string>('demo')

  const [toc, setToc] = useState<TocItem[]>([])

  useEffect(() => {
    if (state.manifest) {
      const items: TocItem[] = state.manifest.sections.map((s) => ({ id: s.id, text: s.title, level: Math.max(0, s.level - 1) }))
      setToc(items)
    } else {
      setToc([])
    }
  }, [state.manifest])

  useEffect(() => {
    // Start the WS worker (runs in a dedicated thread)
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore
    const worker: Worker = new Worker(new URL('./ws/worker.ts', import.meta.url), { type: 'module' })
    workerRef.current = worker

    const onMessage = (event: MessageEvent) => {
      const msg = event.data
      if (!msg) return
      if (msg.type === 'status') {
        setConnected(!!msg.connected)
      } else if (msg.type === 'manifest' && msg.manifest) {
        const man = msg.manifest as DocManifest
        setManifest(man)
        try {
          if (man.assetBase) {
            // Expose to renderer for resolving relative asset URLs
            ;(window as any).__PARADOC_ASSET_BASE = man.assetBase
          }
          if ((man as any).httpDocBase) {
            ;(window as any).__PARADOC_HTTP_DOC_BASE = (man as any).httpDocBase
          }
        } catch {}
      } else if (msg.type === 'ast_section' && msg.bundle) {
        upsertSection(msg.bundle as SectionBundle)
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

  // Resolve docId from URL (?doc=...) or hash (#doc=...)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const q = params.get('doc')
    if (q) setDocId(q)
    else {
      const m = /doc=([^&]+)/.exec(window.location.hash)
      if (m) setDocId(decodeURIComponent(m[1]))
    }
  }, [])

  // Fetch manifest on first load if not received via WS
  useEffect(() => {
    if (!docId) return
    if (state.manifest) return
    fetchManifest(docId).then((m) => {
      setManifest(m)
      // Eagerly load first section
      if (m.sections.length > 0) void fetchSection(docId, m.sections[0].id, m.sections[0].index).then(upsertSection).catch(() => {})
    }).catch(() => {})
  }, [docId, state.manifest])

  return (
    <div className="flex min-h-screen">
      <Navbar toc={toc} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 flex flex-col">
        <Topbar connected={connected} onSendMock={() => {
          // Build and broadcast a minimal AST manifest + section over WS for demo purposes
          const manifest = {
            docId: 'mock-doc',
            sections: [{ id: 'intro', title: 'Mock Document', level: 1, index: 0 }]
          }
          const section = {
            section: manifest.sections[0],
            doc: {
              blocks: [
                { t: 'Header', c: [1, { id: 'intro', classes: [], attributes: {} }, [{ t: 'Str', c: 'Mock' }, { t: 'Space' }, { t: 'Str', c: 'Document' }]] },
                { t: 'Para', c: [
                  { t: 'Str', c: 'This' }, { t: 'Space' }, { t: 'Str', c: 'is' }, { t: 'Space' }, { t: 'Str', c: 'a' }, { t: 'Space' },
                  { t: 'Str', c: 'mock' }, { t: 'Space' }, { t: 'Str', c: 'section' }, { t: 'Str', c: '.' }
                ]}
              ]
            }
          }

          // Update local store so it works even without WS connectivity
          setManifest(manifest as DocManifest)
          upsertSection(section as SectionBundle)

          // Broadcast over WS so other connected clients receive it
          try {
            const w = workerRef.current
            if (w) {
              w.postMessage({ type: 'send', html: JSON.stringify({ kind: 'manifest', manifest }) })
              w.postMessage({ type: 'send', html: JSON.stringify({ kind: 'ast_section', section: section.section, doc: section.doc }) })
            }
          } catch {}
        }} onToggleSidebar={() => setSidebarOpen((v) => !v)} />
        {state.manifest ? (
          <VirtualReader docId={docId} manifest={state.manifest} sections={state.sections} />
        ) : (
          <div className="flex-1 overflow-auto p-6">
            <div className="text-sm text-gray-500">Waiting for document manifest…</div>
          </div>
        )}
      </div>
    </div>
  )
}
