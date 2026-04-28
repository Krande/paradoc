import React from 'react'
import { getAssetTransport } from '../transport'
import type { CameraPreset } from '../../vendor/ada-viewer'

interface ThreeDRendererProps {
  threeDKey: string
  docId: string
  caption?: string
}

interface ViewerHandle {
  dispose: () => void
}

// Camera presets are loaded once per page from the bundle's presets.json.
let _presetsPromise: Promise<Record<string, CameraPreset>> | null = null

function loadPresets(): Promise<Record<string, CameraPreset>> {
  if (_presetsPromise) return _presetsPromise
  _presetsPromise = (async () => {
    try {
      const w = window as any
      const base: string =
        w.__PARADOC_HTTP_DOC_BASE ||
        (w.__PARADOC_ASSET_BASE ? `${w.__PARADOC_ASSET_BASE}` : '') ||
        './'
      const url = base.replace(/\/?$/, '/') + 'assets/presets.json'
      const res = await fetch(url, { cache: 'no-store' })
      if (!res.ok) throw new Error(`presets.json HTTP ${res.status}`)
      const raw = (await res.json()) as Record<string, Omit<CameraPreset, 'name'>>
      const out: Record<string, CameraPreset> = {}
      for (const [name, body] of Object.entries(raw)) out[name] = { name, ...body }
      return out
    } catch (e) {
      console.warn('[ThreeDRenderer] failed to load presets.json; using fallback', e)
      return {
        iso_3: { name: 'iso_3', azimuth_deg: -135, elevation_deg: 30 },
      }
    }
  })()
  return _presetsPromise
}

export function ThreeDRenderer({ threeDKey, docId, caption }: ThreeDRendererProps) {
  const containerRef = React.useRef<HTMLDivElement | null>(null)
  const viewerRef = React.useRef<ViewerHandle | null>(null)
  const [progress, setProgress] = React.useState<{ received: number; total: number } | null>(null)
  const [error, setError] = React.useState<string | null>(null)

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
          loadPresets(),
          transport.fetchBinary(docId, threeDKey, {
            onProgress: (p) =>
              !canceled && setProgress({ received: p.bytesReceived, total: p.totalSize }),
          }),
        ])
        if (canceled) return
        const camera = presets[payload.cameraPos] || Object.values(presets)[0]
        if (!containerRef.current) return
        viewerRef.current = mountViewer(containerRef.current, {
          modelBytes: payload.bytes,
          camera,
          caption: caption || payload.caption,
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
  }, [threeDKey, docId, caption])

  if (error) {
    return (
      <div className="my-4 p-4 border border-red-300 rounded bg-red-50">
        <p className="text-red-600 font-semibold">Error loading 3D view: {threeDKey}</p>
        <p className="text-red-500 text-sm">{error}</p>
      </div>
    )
  }

  return (
    <div className="my-4">
      <div ref={containerRef} className="border border-gray-300 rounded bg-white" />
      {progress && progress.total > 0 && progress.received < progress.total && (
        <p className="text-xs text-gray-500 mt-1 text-center">
          Loading 3D model: {((progress.received / progress.total) * 100).toFixed(0)}%
        </p>
      )}
    </div>
  )
}
