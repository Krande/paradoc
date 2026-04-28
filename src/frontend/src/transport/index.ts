// Transport boot: pick an `AssetTransport` implementation from runtime config.
//
// The HTML hosting paradoc sets `window.__PARADOC_CONFIG__` before the
// app boots. v1 only ships `WSTransport`; the REST follow-up adds a
// REST implementation selected by `transport: 'rest'`.

import type { AssetTransport } from './base'

export type TransportKind = 'ws' | 'rest'

export interface ParadocRuntimeConfig {
  transport?: TransportKind
  apiBase?: string
  docId?: string
}

declare global {
  interface Window {
    __PARADOC_CONFIG__?: ParadocRuntimeConfig
  }
}

export function getRuntimeConfig(): ParadocRuntimeConfig {
  return (window.__PARADOC_CONFIG__ || {}) as ParadocRuntimeConfig
}

let _transport: AssetTransport | null = null

export function getAssetTransport(): AssetTransport | null {
  return _transport
}

export async function initTransport(worker: Worker | null): Promise<AssetTransport | null> {
  const config = getRuntimeConfig()
  const kind: TransportKind = config.transport === 'rest' ? 'rest' : 'ws'

  if (kind === 'rest') {
    if (!config.apiBase) {
      console.warn('[paradoc] REST transport requested but apiBase is missing; falling back to WS.')
    } else {
      const { RESTTransport } = await import('./rest')
      _transport = new RESTTransport({ apiBase: config.apiBase })
      return _transport
    }
  }

  if (!worker) {
    console.warn('[paradoc] no worker available; AssetTransport disabled.')
    return null
  }

  const { WSTransport } = await import('./ws')
  _transport = new WSTransport(worker)
  return _transport
}

export type { AssetTransport, ThreeDMeta, ThreeDPayload, BinaryFetchProgress } from './base'
