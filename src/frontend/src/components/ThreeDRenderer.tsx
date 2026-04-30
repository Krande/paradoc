import React from 'react'
import { getAssetTransport, getRuntimeConfig } from '../transport'
import { useViewerControlsStore } from '../store/viewerControlsStore'
import type { CameraPreset } from '../../vendor/ada-viewer'

interface ThreeDRendererProps {
  threeDKey: string
  docId: string
  caption?: string
}

interface ViewerHandle {
  dispose: () => void
}

// Camera presets are per-doc — adapy stamps them into <bundle>/assets/
// at compile time so the viewer can frame the model the same way the
// static PNG was rendered. We cache a Promise per docId so multiple
// 3D figures inside one doc only fetch once.
const _presetCache = new Map<string, Promise<Record<string, CameraPreset>>>()

function loadPresets(docId: string): Promise<Record<string, CameraPreset>> {
  const cached = _presetCache.get(docId)
  if (cached) return cached
  const p = (async () => {
    const cfg = getRuntimeConfig()
    let url: string
    if (cfg.transport === 'rest') {
      url = (cfg.apiBase || '').replace(/\/?$/, '') +
        `/api/docs/${encodeURIComponent(docId)}/presets`
    } else {
      const w = window as any
      const base: string =
        w.__PARADOC_HTTP_DOC_BASE ||
        (w.__PARADOC_ASSET_BASE ? `${w.__PARADOC_ASSET_BASE}` : '') ||
        './'
      url = base.replace(/\/?$/, '/') + 'assets/presets.json'
    }
    try {
      const res = await fetch(url, { cache: 'no-store' })
      if (!res.ok) throw new Error(`presets HTTP ${res.status}`)
      const raw = (await res.json()) as Record<string, Omit<CameraPreset, 'name'>>
      const out: Record<string, CameraPreset> = {}
      for (const [name, body] of Object.entries(raw)) out[name] = { name, ...body }
      if (Object.keys(out).length === 0) throw new Error('empty presets')
      return out
    } catch (e) {
      console.warn('[ThreeDRenderer] failed to load presets; using fallback', e)
      const fallback: Record<string, CameraPreset> = {
        iso_3: {
          name: 'iso_3',
          azimuth_deg: -135,
          elevation_deg: 30,
          fov_deg: 45,
          distance: 'fit',
          target: 'bbox_center',
          margin: 0.1,
          roll_deg: 0,
        },
      }
      return fallback
    }
  })()
  _presetCache.set(docId, p)
  return p
}

export function ThreeDRenderer({ threeDKey, docId, caption }: ThreeDRendererProps) {
  const containerRef = React.useRef<HTMLDivElement | null>(null)
  const viewerRef = React.useRef<ViewerHandle | null>(null)
  const [progress, setProgress] = React.useState<{ received: number; total: number } | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const { enabled: showControls } = useViewerControlsStore()

  // Re-mount the viewer whenever the global "show adapy controls"
  // toggle flips, so the navbar + selection tree appear/disappear.
  // We refetch presets and binary on every toggle today; once the
  // vendor viewer exposes a runtime-toggle API we can switch to
  // calling that without the remount.
  React.useEffect(() => {
    let canceled = false
    const transport = getAssetTransport()
    if (!transport) {
      setError('asset transport not initialized')
      return
    }

    ;(async () => {
      try {
        const [{ mountViewer }, presets, payload] = await Promise.all([
          import('../../vendor/ada-viewer'),
          loadPresets(docId),
          transport.fetchBinary(docId, threeDKey, {
            onProgress: (p) =>
              !canceled && setProgress({ received: p.bytesReceived, total: p.totalSize }),
          }),
        ])
        if (canceled) return
        const camera = presets[payload.cameraPos] || Object.values(presets)[0]
        if (!containerRef.current) return
        try {
          viewerRef.current?.dispose()
        } catch {}
        viewerRef.current = mountViewer(containerRef.current, {
          modelBytes: payload.bytes,
          camera,
          caption: caption || payload.caption,
          // The vendor build today ignores `showControls`; this becomes
          // live once adapy ships a navbar/tree-aware vendor bundle.
          // Until then, the toggle in the topbar is a no-op visually
          // but the option is plumbed through so we don't have to
          // touch this component again later.
          showControls,
          onError: (err) => !canceled && setError(err.message),
        })
      } catch (err: any) {
        if (canceled) return
        setError(String(err?.message || err))
      }
    })()

    return () => {
      canceled = true
      try {
        viewerRef.current?.dispose()
      } catch {}
      viewerRef.current = null
    }
  }, [threeDKey, docId, caption, showControls])

  if (error) {
    return (
      <div className="my-4 p-4 border border-red-300 rounded bg-red-50">
        <p className="text-red-600 font-semibold">Error loading 3D view: {threeDKey}</p>
        <p className="text-red-500 text-sm">{error}</p>
      </div>
    )
  }

  return (
    <div className="my-4 w-full">
      {/* The vendor viewer reads clientWidth/clientHeight to size its
          canvas. Pinning aspect-ratio + max-w-full keeps the canvas
          inside the viewport on mobile. */}
      <div
        ref={containerRef}
        className="border border-gray-300 rounded bg-white w-full max-w-full overflow-hidden"
        style={{ aspectRatio: '4 / 3' }}
      />
      {progress && progress.total > 0 && progress.received < progress.total && (
        <p className="text-xs text-gray-500 mt-1 text-center">
          Loading 3D model: {((progress.received / progress.total) * 100).toFixed(0)}%
        </p>
      )}
    </div>
  )
}
