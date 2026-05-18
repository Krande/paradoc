// Static-web `AssetTransport`.
//
// Used when the paradoc bundle is served as plain static files (no WS,
// no REST server). Tables/plots are seeded into IndexedDB by
// `loadStaticData()` during App boot; 3D assets are fetched here on
// demand from `${basePath}assets/3d/<key>.glb` with metadata loaded
// once from `${basePath}three_d.json`.

import { dbGet, dbPut, getPlotData, getStaticBasePath, getTableData } from '../sections/store'
import type { PlotData, TableData } from '../sections/store'
import type {
  AssetTransport,
  BinaryFetchProgress,
  ThreeDMeta,
  ThreeDPayload,
} from './base'

interface StaticThreeDEntry {
  key: string
  format?: string
  camera_pos?: string
  caption?: string
  sha256?: string
  size?: number
  source_type?: string
  image_path?: string
}

export class StaticTransport implements AssetTransport {
  readonly kind = 'static'

  private _metaIndex: Promise<Record<string, ThreeDMeta>> | null = null

  private url(relative: string): string {
    return getStaticBasePath().replace(/\/?$/, '/') + relative.replace(/^\.?\//, '')
  }

  async getTableData(docId: string, key: string): Promise<TableData | undefined> {
    // Tables are seeded into IndexedDB at boot; `getTableData` is the
    // canonical IndexedDB read. We re-export it via the transport so
    // components stay backend-agnostic.
    return await getTableData(docId, key)
  }

  async getPlotData(docId: string, key: string): Promise<PlotData | undefined> {
    return await getPlotData(docId, key)
  }

  private async loadMetaIndex(): Promise<Record<string, ThreeDMeta>> {
    if (this._metaIndex) return this._metaIndex
    this._metaIndex = (async () => {
      try {
        const res = await fetch(this.url('three_d.json'), { cache: 'no-store' })
        if (!res.ok) {
          if (res.status !== 404) {
            console.warn(`[paradoc] three_d.json fetch failed: ${res.status}`)
          }
          return {}
        }
        const raw = (await res.json()) as Record<string, StaticThreeDEntry>
        const out: Record<string, ThreeDMeta> = {}
        for (const [k, v] of Object.entries(raw)) {
          out[k] = {
            key: v.key || k,
            format: v.format || 'glb',
            cameraPos: v.camera_pos || 'iso_3',
            caption: v.caption || '',
            sha256: v.sha256 || '',
            size: typeof v.size === 'number' ? v.size : 0,
            imageUrl: v.image_path ? this.url(v.image_path) : undefined,
          }
        }
        return out
      } catch (err) {
        console.warn('[paradoc] failed to load three_d.json', err)
        return {}
      }
    })()
    return this._metaIndex
  }

  async getThreeDMeta(docId: string, key: string): Promise<ThreeDMeta | undefined> {
    const idx = await this.loadMetaIndex()
    const meta = idx[key]
    if (!meta) return undefined
    // Mirror into IndexedDB the same way the WS / REST transports do, so
    // subsequent reads (and the cache-aware fetchBinary path) line up.
    await dbPut('three_d_meta' as any, `${docId}:${key}`, meta).catch(() => {})
    return meta
  }

  async fetchBinary(
    docId: string,
    key: string,
    options?: { sha256Hint?: string; onProgress?: (p: BinaryFetchProgress) => void },
  ): Promise<ThreeDPayload> {
    const requestId = `static_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    const onProgress = options?.onProgress
    const cacheKey = `${docId}:${key}`

    const meta = (await this.getThreeDMeta(docId, key)) || {
      key,
      format: 'glb',
      cameraPos: 'iso_3',
      caption: '',
      sha256: '',
      size: 0,
    }

    // Use cached blob if the manifest sha256 matches what's in IndexedDB.
    if (meta.sha256) {
      const cached = await dbGet<ArrayBuffer>('three_d_blob' as any, meta.sha256)
      if (cached) {
        return { ...meta, bytes: new Uint8Array(cached) }
      }
    }

    const url = this.url(`assets/3d/${encodeURIComponent(key)}.glb`)
    const res = await fetch(url, { cache: 'no-store' })
    if (!res.ok) {
      throw new Error(`static GLB fetch ${url} → ${res.status}`)
    }

    const totalSize = Number(res.headers.get('content-length') || meta.size || 0)
    const reader = res.body?.getReader()

    let bytes: Uint8Array
    if (!reader) {
      const ab = await res.arrayBuffer()
      bytes = new Uint8Array(ab)
    } else {
      const chunks: Uint8Array[] = []
      let received = 0
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        if (value) {
          chunks.push(value)
          received += value.byteLength
          if (onProgress) onProgress({ requestId, bytesReceived: received, totalSize })
        }
      }
      bytes = new Uint8Array(received)
      let offset = 0
      for (const c of chunks) {
        bytes.set(c, offset)
        offset += c.byteLength
      }
    }

    const out: ThreeDMeta = { ...meta, size: meta.size || bytes.byteLength }
    if (out.sha256) {
      await dbPut('three_d_blob' as any, out.sha256, bytes.buffer).catch(() => {})
    }
    await dbPut('three_d_meta' as any, cacheKey, out).catch(() => {})
    return { ...out, bytes }
  }
}
