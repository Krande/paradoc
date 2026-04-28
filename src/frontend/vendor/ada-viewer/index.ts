// Vendored adapy viewer entrypoint (placeholder).
//
// Contract (locked in Phase 6 of the plan):
//
//   mountViewer(element, {
//     modelBytes: Uint8Array,
//     camera: CameraPreset,
//     onReady?: () => void,
//     onError?: (err: Error) => void,
//   }): { dispose(): void }
//
// The vendored bundle is a pure component — no globals, no fetches, no
// WebSocket. It receives glb bytes in and renders pixels out.
//
// Until the real adapy viewer ESM ships, this placeholder renders a
// minimal "3D view available" panel using the metadata so the UI flow
// can be exercised end-to-end. Swap with the real bundle by replacing
// this file with the built ESM artifact from `../adapy/dist/viewer/`.

export interface CameraPreset {
  name: string
  azimuth_deg: number
  elevation_deg: number
  roll_deg?: number
  target?: 'bbox_center'
  distance?: 'fit' | number
  fov_deg?: number
  margin?: number
}

export interface MountViewerOptions {
  modelBytes: Uint8Array
  camera: CameraPreset
  caption?: string
  onReady?: () => void
  onError?: (err: Error) => void
}

export interface MountedViewer {
  dispose: () => void
}

export function mountViewer(element: HTMLElement, opts: MountViewerOptions): MountedViewer {
  let disposed = false

  try {
    element.innerHTML = ''
    element.style.minHeight = '400px'
    element.style.display = 'flex'
    element.style.flexDirection = 'column'
    element.style.alignItems = 'center'
    element.style.justifyContent = 'center'
    element.style.background = 'linear-gradient(135deg, #f3f4f6, #e5e7eb)'
    element.style.borderRadius = '8px'
    element.style.padding = '2rem'
    element.style.fontFamily = 'system-ui, sans-serif'

    const title = document.createElement('div')
    title.style.fontWeight = '600'
    title.style.fontSize = '1.05rem'
    title.style.marginBottom = '0.5rem'
    title.textContent = opts.caption || '3D model'

    const meta = document.createElement('div')
    meta.style.fontSize = '0.85rem'
    meta.style.color = '#4b5563'
    meta.textContent =
      `${(opts.modelBytes.byteLength / 1024).toFixed(1)} KB glb · camera: ${opts.camera.name}`

    const note = document.createElement('div')
    note.style.fontSize = '0.75rem'
    note.style.color = '#6b7280'
    note.style.marginTop = '0.75rem'
    note.style.textAlign = 'center'
    note.textContent =
      'Vendored viewer placeholder — replace with the real adapy viewer ESM bundle.'

    element.appendChild(title)
    element.appendChild(meta)
    element.appendChild(note)

    queueMicrotask(() => {
      if (!disposed) opts.onReady?.()
    })
  } catch (err) {
    opts.onError?.(err instanceof Error ? err : new Error(String(err)))
  }

  return {
    dispose() {
      if (disposed) return
      disposed = true
      try {
        element.innerHTML = ''
      } catch {}
    },
  }
}
