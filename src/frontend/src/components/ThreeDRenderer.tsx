import React from 'react'
import { getAssetTransport, getRuntimeConfig } from '../transport'
import { authedFetch } from '../services/auth/oidc'
import { useViewerControlsStore } from '../store/viewerControlsStore'
import type { CameraPreset } from '../../vendor/ada-viewer'

interface ThreeDRendererProps {
  threeDKey: string
  docId: string
  caption?: string
  /** Override the renderer container's inline style. The default
   *  fills the parent with a 4 / 3 aspect ratio; callers that
   *  manage their own sizing (e.g. Interactive3DFigure resizing
   *  the viewer to match the static poster) pass an empty
   *  aspectRatio + explicit height to opt out. */
  style?: React.CSSProperties
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
      const res = await authedFetch(url, { cache: 'no-store' })
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

export function ThreeDRenderer({ threeDKey, docId, caption, style }: ThreeDRendererProps) {
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
        // Look up the asset metadata first so we know whether it's a
        // single-GLB or an FEA artefact bundle. The two paths share
        // the camera preset + caption + showControls plumbing but
        // diverge on what the embed actually mounts.
        const meta = await transport.getThreeDMeta(docId, threeDKey)
        if (canceled) return

        const presets = await loadPresets(docId)
        if (canceled) return
        const camera =
          presets[meta?.cameraPos || 'iso_3'] || Object.values(presets)[0]

        const vendor = await import('../../vendor/ada-viewer')
        if (canceled || !containerRef.current) return
        try {
          viewerRef.current?.dispose()
        } catch {}

        if (meta?.feaManifestUrl && meta?.feaBundleDir) {
          // FEA artefact-bundle path. The embed assembles the
          // consolidated GLB (mesh + morph targets + animation clips
          // + edges) from the manifest + per-filename fetcher; the
          // fetcher resolves manifest-relative filenames against the
          // bundle's directory URL the backend exposes via
          // `/api/docs/{id}/3d/{key}/fea/...`.
          const manifestRes = await authedFetch(meta.feaManifestUrl, {
            cache: 'no-store',
          })
          if (!manifestRes.ok) {
            throw new Error(`fea manifest fetch failed: ${manifestRes.status}`)
          }
          const manifest = await manifestRes.json()
          if (canceled) return

          // The manifest URL ends in `fea.manifest.json`; strip that
          // to get the bundle base URL the fetcher composes against.
          const base = meta.feaManifestUrl.replace(/[^/]+$/, '')
          const fetcher = async (filename: string) => {
            const clean = filename.replace(/^\/+/, '')
            const r = await authedFetch(base + clean)
            if (!r.ok) {
              throw new Error(`fea fetcher: ${r.status} for ${filename}`)
            }
            return r.arrayBuffer()
          }
          viewerRef.current = vendor.mountFeaArtefactViewer(
            containerRef.current,
            {
              manifest,
              fetcher,
              camera,
              caption: caption || meta?.caption,
              showControls,
              onError: (err) => !canceled && setError(err.message),
            },
          )
          return
        }

        // Single-GLB path (CAD figures, legacy FEA mode shapes,
        // anything without a bundle).
        const payload = await transport.fetchBinary(docId, threeDKey, {
          onProgress: (p) =>
            !canceled && setProgress({ received: p.bytesReceived, total: p.totalSize }),
        })
        if (canceled || !containerRef.current) return
        viewerRef.current = vendor.mountViewer(containerRef.current, {
          modelBytes: payload.bytes,
          camera,
          caption: caption || payload.caption,
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
          inside the viewport on mobile.
          `touch-none` tells the browser not to pan/pinch-zoom the page
          on touches that start inside the canvas — without it, a pinch
          on the 3D viewer zoomed the whole page on mobile and the user
          couldn't reach top/bottom afterwards. `overscroll-contain`
          stops wheel/touch from bubbling up to the doc scroll. */}
      <div
        ref={containerRef}
        className="border border-gray-300 rounded bg-white w-full max-w-full overflow-hidden touch-none overscroll-contain"
        style={{ aspectRatio: '4 / 3', ...style }}
      />
      {progress && progress.total > 0 && progress.received < progress.total && (
        <p className="text-xs text-gray-500 mt-1 text-center">
          Loading 3D model: {((progress.received / progress.total) * 100).toFixed(0)}%
        </p>
      )}
    </div>
  )
}
