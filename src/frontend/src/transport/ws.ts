// WebSocket-backed `AssetTransport`.
//
// Tables/plots arrive over the existing relay (the worker stores them in
// IndexedDB on receipt). Binary fetches use the protocol implemented by
// `paradoc.frontend.binary_relay` on the server and the `binary_fetch_*`
// message handling in `ws/worker.ts`.

import { dbGet, dbPut, getPlotData, getTableData } from '../sections/store'
import type { PlotData, TableData } from '../sections/store'
import type {
  AssetTransport,
  BinaryFetchProgress,
  ThreeDMeta,
  ThreeDPayload,
} from './base'

let _nextRequestId = 1
function newRequestId(): string {
  _nextRequestId += 1
  return `bf_${Date.now()}_${_nextRequestId}`
}

export class WSTransport implements AssetTransport {
  readonly kind = 'ws'

  constructor(private readonly worker: Worker) {}

  getTableData(docId: string, key: string): Promise<TableData | undefined> {
    return getTableData(docId, key)
  }

  getPlotData(docId: string, key: string): Promise<PlotData | undefined> {
    return getPlotData(docId, key)
  }

  async getThreeDMeta(docId: string, key: string): Promise<ThreeDMeta | undefined> {
    // Cached client-side mirror, populated when fetchBinary completes.
    const cacheKey = `${docId}:${key}`
    return dbGet<ThreeDMeta>('three_d_meta' as any, cacheKey)
  }

  fetchBinary(
    docId: string,
    key: string,
    options?: { sha256Hint?: string; onProgress?: (p: BinaryFetchProgress) => void },
  ): Promise<ThreeDPayload> {
    const requestId = newRequestId()
    const onProgress = options?.onProgress
    const cacheKey = `${docId}:${key}`

    return new Promise<ThreeDPayload>(async (resolve, reject) => {
      let knownSha = options?.sha256Hint
      if (!knownSha) {
        const meta = await this.getThreeDMeta(docId, key)
        knownSha = meta?.sha256
      }

      const handleMessage = async (event: MessageEvent) => {
        const msg = event.data
        if (!msg || typeof msg.type !== 'string') return
        if (msg.requestId && msg.requestId !== requestId) return

        if (msg.type === 'binary_fetch_progress' && onProgress) {
          onProgress({
            requestId,
            bytesReceived: msg.bytesReceived,
            totalSize: msg.totalSize,
          })
          return
        }

        if (msg.type === 'binary_fetch_cached') {
          // Server says our hint was good — pull bytes from IndexedDB.
          const cached = await dbGet<ArrayBuffer>('three_d_blob' as any, knownSha!)
          const meta = await this.getThreeDMeta(docId, key)
          this.worker.removeEventListener('message', handleMessage)
          if (!cached || !meta) {
            reject(new Error(`server reported cache hit but local cache is missing for ${key}`))
            return
          }
          resolve({ ...meta, bytes: new Uint8Array(cached) })
          return
        }

        if (msg.type === 'binary_fetch_error') {
          this.worker.removeEventListener('message', handleMessage)
          reject(new Error(msg.error || 'binary fetch failed'))
          return
        }

        if (msg.type === 'binary_fetch_done') {
          this.worker.removeEventListener('message', handleMessage)
          const bytes = new Uint8Array(msg.bytes as ArrayBuffer)
          const meta: ThreeDMeta = {
            key,
            format: msg.format,
            cameraPos: msg.cameraPos,
            caption: msg.caption,
            sha256: msg.sha256,
            size: bytes.byteLength,
          }
          // Mirror to IndexedDB by content hash so identical bytes shared
          // across docs deduplicate naturally.
          await dbPut('three_d_blob' as any, msg.sha256, bytes.buffer)
          await dbPut('three_d_meta' as any, cacheKey, meta)
          window.dispatchEvent(
            new CustomEvent('paradoc:3d-data-stored', {
              detail: { docId, key, sha256: msg.sha256 },
            }),
          )
          resolve({ ...meta, bytes })
        }
      }

      this.worker.addEventListener(
        'message',
        handleMessage as unknown as EventListener,
      )

      this.worker.postMessage({
        type: 'binary_fetch_request',
        requestId,
        docId,
        key,
        sha256: knownSha,
        chunkSize: 256 * 1024,
      })
    })
  }
}
