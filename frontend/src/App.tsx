import React, { useEffect, useRef, useState } from 'react'
import { Topbar } from './components/Topbar'
import { Navbar, TocItem } from './components/Navbar'

// Inline the worker so it's embedded in the bundle
import InlineWorker from './ws/worker.ts?worker&inline'

import { useSectionStore, fetchManifest, fetchSection, storeEmbeddedImage, storePlotData, storeTableData } from './sections/store'
import type { DocManifest, SectionBundle } from './ast/types'
import { VirtualReader } from './components/VirtualReader'
import { calculateHeadingNumbers } from './ast/headingNumbers'

export default function App() {
  const [connected, setConnected] = useState<boolean>(false)
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false)
  const [processInfo, setProcessInfo] = useState<{ pid: number; thread_id: number } | null>(null)
  const workerRef = useRef<Worker | null>(null)

  // AST/Sections store
  const { state, setManifest, upsertSection } = useSectionStore()
  const [docId, setDocId] = useState<string>('demo')

  const [toc, setToc] = useState<TocItem[]>([])

  useEffect(() => {
    if (state.manifest) {
      const headingNumbers = calculateHeadingNumbers(state.manifest.sections)
      const items: TocItem[] = state.manifest.sections.map((s) => {
        const numbering = headingNumbers.get(s.id)
        return {
          id: s.id,
          text: s.title,
          level: Math.max(0, s.level - 1),
          number: numbering?.fullText
        }
      })
      setToc(items)
    } else {
      setToc([])
    }
  }, [state.manifest])

  useEffect(() => {
    // Use inline worker for single-file builds that work from filesystem
    const worker = new InlineWorker()
    workerRef.current = worker

    // Track the current docId from manifest
    let currentDocId = 'demo'

    const onMessage = (event: MessageEvent) => {
      const msg = event.data
      if (!msg) return
      if (msg.type === 'status') {
        setConnected(!!msg.connected)
        // Clear process info when disconnected
        if (!msg.connected) {
          setProcessInfo(null)
        }
      } else if (msg.type === 'manifest' && msg.manifest) {
        const man = msg.manifest as DocManifest
        setManifest(man)
        // Ensure our docId matches the manifest to avoid URL mismatches
        try {
          if (man && (man as any).docId) {
            currentDocId = (man as any).docId
            setDocId(currentDocId)
          }
        } catch {}
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
      } else if (msg.type === 'embedded_images' && msg.images) {
        // Store embedded images in IndexedDB using the current docId from manifest
        const images = msg.images as Record<string, { data: string; mimeType: string }>
        for (const [path, imgData] of Object.entries(images)) {
          storeEmbeddedImage(currentDocId, path, imgData.data, imgData.mimeType).catch(err => {
            console.warn(`Failed to store embedded image ${path} for docId ${currentDocId}:`, err)
          })
        }
      } else if (msg.type === 'plot_data' && msg.plots) {
        // Store plot data in IndexedDB
        const plots = msg.plots as Record<string, any>
        for (const [plotKey, plotData] of Object.entries(plots)) {
          storePlotData(currentDocId, plotKey, plotData).catch(err => {
            console.warn(`Failed to store plot data ${plotKey} for docId ${currentDocId}:`, err)
          })
        }
      } else if (msg.type === 'table_data' && msg.tables) {
        // Store table data in IndexedDB
        const tables = msg.tables as Record<string, any>
        for (const [tableKey, tableData] of Object.entries(tables)) {
          storeTableData(currentDocId, tableKey, tableData).catch(err => {
            console.warn(`Failed to store table data ${tableKey} for docId ${currentDocId}:`, err)
          })
        }
      } else if (msg.type === 'process_info') {
        setProcessInfo({ pid: msg.pid, thread_id: msg.thread_id })
      } else if (msg.type === 'shutdown_ack') {
        console.log('WebSocket server acknowledged shutdown request')
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
      // Align our docId with the manifest to avoid mixing ids in URLs
      try { if ((m as any).docId) setDocId((m as any).docId) } catch {}
      // Eagerly load first section
      if (m.sections.length > 0) void fetchSection((m as any).docId || docId, m.sections[0].id, m.sections[0].index).then(upsertSection).catch(() => {})
    }).catch(() => {})
  }, [docId, state.manifest])

  const handleRequestProcessInfo = () => {
    const worker = workerRef.current
    if (worker && connected) {
      worker.postMessage({ type: 'get_process_info' })
    }
  }

  const handleKillServer = () => {
    const worker = workerRef.current
    if (worker && connected) {
      worker.postMessage({ type: 'shutdown' })
    }
  }

  return (
    <div className="flex min-h-screen">
      <Navbar toc={toc} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 flex flex-col">
        <Topbar
          connected={connected}
          processInfo={processInfo}
          onRequestProcessInfo={handleRequestProcessInfo}
          onKillServer={handleKillServer}
          onSendMock={() => {
          // Build and broadcast a minimal AST manifest + section over WS for demo purposes
          const manifest = {
            docId: 'mock-doc',
            sections: [
              { id: 'h1-intro', title: 'Introduction', level: 1, index: 0 },
              { id: 'h2-goals', title: 'Goals', level: 2, index: 1 },
              { id: 'h2-scope', title: 'Scope', level: 2, index: 2 },
              { id: 'h1-details', title: 'Details', level: 1, index: 3 },
              { id: 'h2-arch', title: 'Architecture', level: 2, index: 4 },
              { id: 'h3-components', title: 'Components', level: 3, index: 5 },
            ]
          }
          const section = {
            section: manifest.sections[0],
            doc: {
              blocks: [
                { t: 'Header', c: [1, { id: 'h1-intro', classes: [], attributes: {} }, [{ t: 'Str', c: 'Introduction' }]] },
                { t: 'Para', c: [ { t: 'Str', c: 'This' }, { t: 'Space' }, { t: 'Str', c: 'is' }, { t: 'Space' }, { t: 'Str', c: 'intro' }, { t: 'Str', c: '.' } ] },
                { t: 'Header', c: [2, { id: 'h2-goals', classes: [], attributes: {} }, [{ t: 'Str', c: 'Goals' }]] },
                { t: 'Para', c: [ { t: 'Str', c: 'Goals' }, { t: 'Space' }, { t: 'Str', c: 'content' } ] },
                { t: 'Header', c: [2, { id: 'h2-scope', classes: [], attributes: {} }, [{ t: 'Str', c: 'Scope' }]] },
                { t: 'Para', c: [ { t: 'Str', c: 'Scope' }, { t: 'Space' }, { t: 'Str', c: 'content' } ] },
                { t: 'Header', c: [1, { id: 'h1-details', classes: [], attributes: {} }, [{ t: 'Str', c: 'Details' }]] },
                { t: 'Para', c: [ { t: 'Str', c: 'Details' }, { t: 'Space' }, { t: 'Str', c: 'content' } ] },
                { t: 'Header', c: [2, { id: 'h2-arch', classes: [], attributes: {} }, [{ t: 'Str', c: 'Architecture' }]] },
                { t: 'Para', c: [ { t: 'Str', c: 'Arch' }, { t: 'Space' }, { t: 'Str', c: 'content' } ] },
                { t: 'Header', c: [3, { id: 'h3-components', classes: [], attributes: {} }, [{ t: 'Str', c: 'Components' }]] },
                { t: 'Para', c: [ { t: 'Str', c: 'Components' }, { t: 'Space' }, { t: 'Str', c: 'content' } ] },
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
