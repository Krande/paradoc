// Backend-neutral transport for paradoc doc data.
//
// The frontend talks to *this* interface, never to a specific backend.
// Phase 6 ships `WSTransport`. Phase 10 (REST follow-up) adds a
// `RESTTransport` that hits a paradoc HTTP server backed by S3.
//
// Boot-time selection lives in `transport/index.ts`.

import type { PlotData, TableData } from '../sections/store'

export interface ThreeDMeta {
  key: string
  format: string
  cameraPos: string
  caption: string
  sha256: string
  size: number
  /** Optional URL of a raster preview (e.g. `assets/3d/<key>.png`) the
   *  frontend can show as a poster before mounting the live viewer. */
  imageUrl?: string
}

export interface ThreeDPayload extends ThreeDMeta {
  bytes: Uint8Array
}

export interface BinaryFetchProgress {
  requestId: string
  bytesReceived: number
  totalSize: number
}

export interface AssetTransport {
  /** Identifier used in logs / diagnostics. */
  readonly kind: string

  getTableData(docId: string, key: string): Promise<TableData | undefined>
  getPlotData(docId: string, key: string): Promise<PlotData | undefined>
  getThreeDMeta(docId: string, key: string): Promise<ThreeDMeta | undefined>

  /**
   * Fetch the binary payload for a 3D asset, with content-hash short-circuit.
   *
   * If `sha256Hint` matches what the server has, no transfer happens; the
   * cached bytes from IndexedDB are returned. Otherwise streams the bytes
   * over the wire (chunked transparently to the caller) and stores them
   * by content hash.
   *
   * `onProgress` fires per chunk during transfer.
   */
  fetchBinary(
    docId: string,
    key: string,
    options?: {
      sha256Hint?: string
      onProgress?: (p: BinaryFetchProgress) => void
    },
  ): Promise<ThreeDPayload>
}
