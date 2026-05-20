import React, { useEffect, useRef } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { useAppStore } from './store/appStore'
import { Topbar } from './components/Topbar'
import { Navbar, TocItem } from './components/Navbar'
import { SearchBar } from './components/SearchBar'
import AdminApp from './components/admin/AdminApp'
import { AuthGate } from './components/auth/AuthGate'
import { AuthCallback } from './components/auth/AuthCallback'

// Inline the worker so it's embedded in the bundle
import InlineWorker from './ws/worker.ts?worker&inline'

import { useSectionStore, storeEmbeddedImage, storePlotData, storeTableData, isStaticMode, detectStaticMode, loadStaticData } from './sections/store'
import { initTransport, getRuntimeConfig } from './transport'
import { loadRestData } from './transport/loadRestData'
import type { DocManifest, SectionBundle } from './ast/types'
import { VirtualReader } from './components/VirtualReader'
import { DocList } from './components/DocList'
import { calculateHeadingNumbers } from './ast/headingNumbers'
import { SourceDisplayProvider } from './store/sourceDisplayStore'
import { ViewerControlsProvider } from './store/viewerControlsStore'

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
  const { state, setManifest, upsertSection, resetSections } = useSectionStore()

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
    // The inline worker exists only to serve the WS live-view loop.
    // Only instantiate it when transport === 'ws'; otherwise the
    // worker would boot, fail to connect to ws://localhost:13579 (the
    // dev WS server isn't reachable from REST/static/embed deployments),
    // and either spam reconnect errors or sit doing nothing useful.
    // Stopping it post-init via postMessage('stop') still let one
    // failed WS connection through before the stop arrived, hence
    // gating the construction itself.
    const _cfg = getRuntimeConfig()
    const needsWorker = _cfg.transport !== 'rest' && _cfg.transport !== 'static'
    const worker = needsWorker ? new InlineWorker() : null
    workerRef.current = worker
    initTransport(worker).catch((err) => {
      console.warn('[App] failed to init AssetTransport:', err)
    })

    // No WS worker in non-ws modes — skip the message-handler wiring
    // and lifecycle entirely. Doc data flows through the REST loader
    // (loadRestData) or the static-files loader instead.
    if (!worker) return

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

    // Check if we're in explicit static mode or auto-detect it. The
    // autodetect HEAD-fetches `./manifest.json`, which 404s when the
    // SPA is hosted by `paradoc-serve` (REST mode) — annoying noise in
    // the console for every page load. Skip the probe when transport
    // is explicitly configured (rest *or* static); only fall back to
    // autodetection when no runtime config is present at all (e.g.
    // when somebody opens the bundled HTML out of an unknown host).
    const tryStaticLoad = async () => {
      const cfg = getRuntimeConfig()
      const isStatic = isStaticMode()
      const detected =
        !isStatic && cfg.transport === undefined ? await detectStaticMode() : false

      if (!isStatic && !detected) {
        // Not in static mode, let WebSocket / REST handle data loading
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

  // REST mode: when paradoc-serve is hosting the SPA, /config.js sets
  // window.__PARADOC_CONFIG__.transport = 'rest'. With a docId in hand
  // we fetch manifest + sections from the REST endpoints; without one
  // we render <DocList> below until the user picks one.
  useEffect(() => {
    if (state.manifest) return
    const cfg = getRuntimeConfig()
    if (cfg.transport !== 'rest' || !docId) return

    let canceled = false
    ;(async () => {
      try {
        const data = await loadRestData(cfg.apiBase || '', docId)
        if (canceled) return
        setManifest(data.manifest)
        for (const bundle of data.sections) upsertSection(bundle)

        // Seed IndexedDB with bulk plots/tables/images so InteractiveFigure
        // and InteractiveTable can detect available data and offer the
        // static/interactive toggle — same flow the static-mode block above
        // uses. Without this, the toggle stays hidden because the IndexedDB
        // probe in those components misses on every island.
        for (const [path, imgData] of Object.entries(data.images)) {
          await storeEmbeddedImage(docId, path, imgData.data, imgData.mimeType).catch((err) => {
            console.warn(`[paradoc] failed to store image ${path}:`, err)
          })
        }
        for (const [plotKey, plotData] of Object.entries(data.plots)) {
          await storePlotData(docId, plotKey, plotData).catch((err) => {
            console.warn(`[paradoc] failed to store plot ${plotKey}:`, err)
          })
        }
        for (const [tableKey, tableData] of Object.entries(data.tables)) {
          await storeTableData(docId, tableKey, tableData).catch((err) => {
            console.warn(`[paradoc] failed to store table ${tableKey}:`, err)
          })
        }
      } catch (err) {
        console.warn('[paradoc] REST load failed', err)
      }
    })()
    return () => {
      canceled = true
    }
  }, [docId, state.manifest])

  const handleSelectDoc = (id: string) => {
    if (id === docId) return
    // Drop the previous doc's manifest + sections so the REST loader's
    // `if (state.manifest) return` short-circuit lifts and we actually
    // refetch for the new doc.
    resetSections()
    setDocId(id)
    try {
      const url = new URL(window.location.href)
      url.searchParams.set('doc', id)
      window.history.pushState({}, '', url.toString())
    } catch {}
  }

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
    // `h-dvh` (dynamic-viewport, not `100vh`) so mobile browsers' URL
    // bar show/hide doesn't leave the layout mis-sized vs the visible
    // viewport — that's the "can't scroll to top after closing a 3D
    // viewer" mobile bug. Keep the bounded-height invariant: the
    // inner `flex-1 overflow-auto` reader still gets a fixed parent
    // and scrolls internally (with `min-h-screen` the root grew to
    // fit content, clientHeight = scrollHeight, wheel was a no-op).
    <div className="flex h-dvh overflow-hidden">
      <Navbar toc={toc} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      {/* `min-w-0` is essential alongside `flex-1`: default flex
          `min-width: auto` lets the column grow to fit content
          (e.g. the 3D viewer's canvas, which is sized from
          `element.clientWidth` at mount), causing runaway expansion
          past the viewport on narrow screens. */}
      <div className="flex-1 flex flex-col min-h-0 min-w-0">
        <Topbar
          connected={connected}
          frontendId={frontendId}
          docId={docId}
          onSelectDoc={handleSelectDoc}
          connectedFrontends={connectedFrontends}
          processInfo={processInfo}
          logFilePath={logFilePath}
          workerRef={workerRef}
          onToggleSidebar={toggleSidebar} />
        {state.manifest ? (
          <VirtualReader docId={docId} manifest={state.manifest} sections={state.sections} />
        ) : (() => {
          const cfg = getRuntimeConfig()
          if (cfg.transport === 'rest' && !docId) {
            return <DocList onSelect={handleSelectDoc} />
          }
          return (
            <div className="flex-1 overflow-auto p-6">
              <div className="text-sm text-gray-500">Waiting for document manifest…</div>
            </div>
          )
        })()}
      </div>
      <SearchBar isOpen={searchBarOpen} onClose={() => setSearchBarOpen(false)} />
    </div>
  )
}
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* OIDC redirect_uri — must NOT be inside AuthGate or the gate
            will redirect back to /auth/callback in an infinite loop
            since isSignedIn() is still false at that point. */}
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route
          path="/admin/*"
          element={
            <AuthGate>
              <AdminApp />
            </AuthGate>
          }
        />
        <Route
          path="*"
          element={
            <AuthGate>
              <SourceDisplayProvider>
                <ViewerControlsProvider>
                  <AppContent />
                </ViewerControlsProvider>
              </SourceDisplayProvider>
            </AuthGate>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

