// REST-backed `AssetTransport`.
//
// Used in cloud deployments where a paradoc REST server is up. The
// frontend does not know S3 exists — the server abstracts it via the
// REST API mirroring `DocStore`.

import { dbGet, dbPut } from '../sections/store'
import type { PlotData, TableData } from '../sections/store'
import type {
  AssetTransport,
  BinaryFetchProgress,
  ThreeDMeta,
  ThreeDPayload,
} from './base'

export interface RESTTransportOptions {
  /** Base URL of the paradoc REST server, e.g. https://reports.example.com */
  apiBase: string
}

export class RESTTransport implements AssetTransport {
  readonly kind = 'rest'

  constructor(private readonly opts: RESTTransportOptions) {}

  private url(path: string): string {
    return this.opts.apiBase.replace(/\/?$/, '') + path
  }

  async getTableData(docId: string, key: string): Promise<TableData | undefined> {
    const res = await fetch(this.url(`/api/docs/${encodeURIComponent(docId)}/tables/${encodeURIComponent(key)}`))
    if (res.status === 404) return undefined
    if (!res.ok) throw new Error(`table fetch failed: ${res.status}`)
    return (await res.json()) as TableData
  }

  async getPlotData(docId: string, key: string): Promise<PlotData | undefined> {
    const res = await fetch(this.url(`/api/docs/${encodeURIComponent(docId)}/plots/${encodeURIComponent(key)}`))
    if (res.status === 404) return undefined
    if (!res.ok) throw new Error(`plot fetch failed: ${res.status}`)
    return (await res.json()) as PlotData
  }

  async getThreeDMeta(docId: string, key: string): Promise<ThreeDMeta | undefined> {
    const res = await fetch(this.url(`/api/docs/${encodeURIComponent(docId)}/3d/${encodeURIComponent(key)}/meta`))
    if (res.status === 404) return undefined
    if (!res.ok) throw new Error(`3d meta fetch failed: ${res.status}`)
    const body = await res.json()
    return {
      key: body.key,
      format: body.format,
      cameraPos: body.camera_pos,
      caption: body.caption,
      sha256: body.sha256,
      size: body.size,
    }
  }

  async fetchBinary(
    docId: string,
    key: string,
    options?: { sha256Hint?: string; onProgress?: (p: BinaryFetchProgress) => void },
  ): Promise<ThreeDPayload> {
    const requestId = `rest_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    const onProgress = options?.onProgress
    const cacheKey = `${docId}:${key}`

    let knownSha = options?.sha256Hint
    if (!knownSha) {
      const meta = await this.getThreeDMeta(docId, key)
      knownSha = meta?.sha256
    }

    const url = this.url(`/api/docs/${encodeURIComponent(docId)}/3d/${encodeURIComponent(key)}/blob`)
    const headers: HeadersInit = {}
    if (knownSha) headers['If-None-Match'] = `"${knownSha}"`

    const res = await fetch(url, { headers })

    if (res.status === 304) {
      const cached = await dbGet<ArrayBuffer>('three_d_blob' as any, knownSha!)
      const meta = await this.getThreeDMeta(docId, key)
      if (!cached || !meta) {
        throw new Error('server reported cache hit but local cache is missing')
      }
      return { ...meta, bytes: new Uint8Array(cached) }
    }

    if (!res.ok) throw new Error(`3d blob fetch failed: ${res.status}`)

    const sha256 = (res.headers.get('etag') || '').replace(/"/g, '') ||
      res.headers.get('x-paradoc-sha256') || ''
    const cameraPos = res.headers.get('x-paradoc-camera-pos') || 'iso_3'
    const totalSize = Number(res.headers.get('content-length') || 0)

    const reader = res.body?.getReader()
    if (!reader) {
      const ab = await res.arrayBuffer()
      const meta = await this.getThreeDMeta(docId, key)
      const bytes = new Uint8Array(ab)
      const out: ThreeDMeta = meta || {
        key,
        format: 'glb',
        cameraPos,
        caption: '',
        sha256,
        size: bytes.byteLength,
      }
      await dbPut('three_d_blob' as any, sha256, ab)
      await dbPut('three_d_meta' as any, cacheKey, out)
      return { ...out, bytes }
    }

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

    const merged = new Uint8Array(received)
    let offset = 0
    for (const c of chunks) {
      merged.set(c, offset)
      offset += c.byteLength
    }

    const meta = await this.getThreeDMeta(docId, key)
    const out: ThreeDMeta = meta || {
      key,
      format: 'glb',
      cameraPos,
      caption: '',
      sha256,
      size: received,
    }
    await dbPut('three_d_blob' as any, sha256 || cacheKey, merged.buffer)
    await dbPut('three_d_meta' as any, cacheKey, out)
    window.dispatchEvent(
      new CustomEvent('paradoc:3d-data-stored', { detail: { docId, key, sha256 } }),
    )
    return { ...out, bytes: merged }
  }
}
