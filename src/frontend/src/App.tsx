import React, { useEffect, useRef } from 'react'
import { useAppStore } from './store/appStore'
import { Topbar } from './components/Topbar'
import { Navbar, TocItem } from './components/Navbar'
import { SearchBar } from './components/SearchBar'

// Inline the worker so it's embedded in the bundle
import InlineWorker from './ws/worker.ts?worker&inline'

import { useSectionStore, storeEmbeddedImage, storePlotData, storeTableData, isStaticMode, detectStaticMode, loadStaticData } from './sections/store'
import { initTransport } from './transport'
import type { DocManifest, SectionBundle } from './ast/types'
import { VirtualReader } from './components/VirtualReader'
import { calculateHeadingNumbers } from './ast/headingNumbers'
import { SourceDisplayProvider } from './store/sourceDisplayStore'

function AppContent() {
  const {
    connected, setConnected,
    sidebarOpen, setSidebarOpen, toggleSidebar,
    searchBarOpen, setSearchBarOpen,
    processInfo, setProcessInfo,
    frontendId, setFrontendId,
    connectedFrontends, setConnectedFrontends,
    logFilePath, setLogFilePath,
    docId, setDocId,
    toc, setToc
  } = useAppStore()
  const workerRef = useRef<Worker | null>(null)

  // AST/Sections store
  const { state, setManifest, upsertSection } = useSectionStore()

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

  // Load frontend ID from localStorage on mount
  useEffect(() => {
    const storedId = localStorage.getItem('paradoc_frontend_id')
    if (storedId) {
      setFrontendId(storedId)
    }
  }, [])

  // Set initial sidebar state based on screen size
  useEffect(() => {
    if (window.innerWidth < 768) {
      setSidebarOpen(false)
    }
  }, [])

  useEffect(() => {
    // Use inline worker for single-file builds that work from filesystem
    const worker = new InlineWorker()
    workerRef.current = worker
    // Initialize the AssetTransport so 3D figures can fetch glb bytes.
    initTransport(worker).catch((err) => {
      console.warn('[App] failed to init AssetTransport:', err)
    })

    // Track the current docId from manifest
    let currentDocId = 'demo'

    const onMessage = (event: MessageEvent) => {
      const msg = event.data
      if (!msg) return
      if (msg.type === 'status') {
        setConnected(!!msg.connected)
        // Store and update frontend ID when we get it from worker
        if (msg.frontendId && typeof msg.frontendId === 'string') {
          setFrontendId(msg.frontendId)
          localStorage.setItem('paradoc_frontend_id', msg.frontendId)
        }
        // Clear process info when disconnected
        if (!msg.connected) {
          setProcessInfo(null)
        }
      } else if (msg.type === 'frontend_id' && msg.frontendId) {
        setFrontendId(msg.frontendId)
        localStorage.setItem('paradoc_frontend_id', msg.frontendId)
      } else if (msg.type === 'frontend_id_updated' && msg.frontendId) {
        setFrontendId(msg.frontendId)
        localStorage.setItem('paradoc_frontend_id', msg.frontendId)
      } else if (msg.type === 'connected_frontends') {
        setConnectedFrontends(msg.frontendIds || [])
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
      } else if (msg.type === 'log_file_path' && msg.path) {
        setLogFilePath(msg.path)
      }
    }

    worker.addEventListener('message', onMessage)

    // Request frontend ID from worker
    worker.postMessage({ type: 'get_frontend_id' })

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

  // Static mode: Load data from static JSON files if available
  // This enables hosting the paradoc frontend on static web servers without WebSocket
  useEffect(() => {
    // Skip if we already have a manifest (e.g., from WebSocket)
    if (state.manifest) return

    // Check if we're in explicit static mode or auto-detect it
    const tryStaticLoad = async () => {
      const isStatic = isStaticMode()
      const detected = !isStatic ? await detectStaticMode() : false

      if (!isStatic && !detected) {
        // Not in static mode, let WebSocket handle data loading
        return
      }

      console.log('Paradoc: Loading document from static files...')
      try {
        const data = await loadStaticData()
        const currentDocId = (data.manifest as any).docId || 'static-doc'

        // Set manifest
        setManifest(data.manifest)
        setDocId(currentDocId)

        // Load all sections
        for (const bundle of data.sections) {
          upsertSection(bundle)
        }

        // Store images in IndexedDB
        for (const [path, imgData] of Object.entries(data.images)) {
          await storeEmbeddedImage(currentDocId, path, imgData.data, imgData.mimeType).catch(err => {
            console.warn(`Failed to store embedded image ${path}:`, err)
          })
        }

        // Store plots in IndexedDB
        for (const [plotKey, plotData] of Object.entries(data.plots)) {
          await storePlotData(currentDocId, plotKey, plotData).catch(err => {
            console.warn(`Failed to store plot data ${plotKey}:`, err)
          })
        }

        // Store tables in IndexedDB
        for (const [tableKey, tableData] of Object.entries(data.tables)) {
          await storeTableData(currentDocId, tableKey, tableData).catch(err => {
            console.warn(`Failed to store table data ${tableKey}:`, err)
          })
        }

        console.log('Paradoc: Successfully loaded static document')
      } catch (err) {
        console.log('Paradoc: Static mode not available, waiting for WebSocket data', err)
      }
    }

    tryStaticLoad()
  }, [state.manifest])

  // Handle global keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+F or Cmd+F to open search
      if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault()
        setSearchBarOpen(true)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  return (
    <div className="flex min-h-screen">
      <Navbar toc={toc} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 flex flex-col">
        <Topbar
          connected={connected}
          frontendId={frontendId}
          connectedFrontends={connectedFrontends}
          processInfo={processInfo}
          logFilePath={logFilePath}
          workerRef={workerRef}
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
        }} onToggleSidebar={toggleSidebar} />
        {state.manifest ? (
          <VirtualReader docId={docId} manifest={state.manifest} sections={state.sections} />
        ) : (
          <div className="flex-1 overflow-auto p-6">
            <div className="text-sm text-gray-500">Waiting for document manifest…</div>
          </div>
        )}
      </div>
      <SearchBar isOpen={searchBarOpen} onClose={() => setSearchBarOpen(false)} />
    </div>
  )
}
export default function App() {
  return (
    <SourceDisplayProvider>
      <AppContent />
    </SourceDisplayProvider>
  )
}

