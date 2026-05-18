// Transport boot: pick an `AssetTransport` implementation from runtime config.
//
// The HTML hosting paradoc sets `window.__PARADOC_CONFIG__` before the
// app boots. v1 only ships `WSTransport`; the REST follow-up adds a
// REST implementation selected by `transport: 'rest'`.

import type { AssetTransport } from './base'

export type TransportKind = 'ws' | 'rest' | 'static'

export interface ParadocHeaderLink {
  label: string
  href: string
  /** Optional `target` attribute (e.g. `_blank`). Defaults to same-tab navigation. */
  target?: string
  /** Optional `rel` attribute. Auto-set to `noopener noreferrer` when `target === '_blank'`. */
  rel?: string
}

export interface ParadocRuntimeConfig {
  transport?: TransportKind
  apiBase?: string
  docId?: string
  /**
   * Optional links rendered into the Topbar to the left of the title. Used by
   * static-export hosts (Sphinx / standalone sites) to wire a "Back to docs"
   * affordance without owning the frontend.
   */
  headerLinks?: ParadocHeaderLink[]
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
  let kind: TransportKind
  if (config.transport === 'rest') kind = 'rest'
  else if (config.transport === 'static') kind = 'static'
  else kind = 'ws'

  if (kind === 'rest') {
    // Empty apiBase ('') is valid — same-host serving uses current
    // origin via relative URLs. Only `undefined` means missing.
    if (config.apiBase === undefined) {
      console.warn('[paradoc] REST transport requested but apiBase is missing; falling back to WS.')
    } else {
      const { RESTTransport } = await import('./rest')
      _transport = new RESTTransport({ apiBase: config.apiBase })
      return _transport
    }
  }

  if (kind === 'static') {
    // Static-web export: data lives in JSON files served alongside the HTML;
    // GLBs live under `./assets/3d/<key>.glb`. The bundle ships
    // `transport: 'static'` in __PARADOC_CONFIG__ for explicit selection.
    const { StaticTransport } = await import('./static')
    _transport = new StaticTransport()
    return _transport
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
