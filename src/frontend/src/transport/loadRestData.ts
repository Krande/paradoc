// REST-backed analogue of `loadStaticData()`. Hits the paradoc-serve
// endpoints `<doc>/manifest`, `<doc>/sections/{idx}` (where `<doc>` is
// `/api/docs/{id}` or `/api/scopes/{scope}/docs/{id}`, see docScope.ts),
// the bulk `/tables` endpoint, and `/plots-index` -- the keys that have
// interactive plot data. A plot's figure is fetched from
// `/plots/{key}/figure` only when a reader switches it to interactive.
// 3D blobs continue to flow through `RESTTransport` lazily.

import type { DocManifest, SectionBundle } from '../ast/types'
import type { TableData } from '../sections/store'
import { bulkPlotSource, fetchSectionRun } from '../sections/dataSources'
import type { PlotIndexEntry, PlotSourceSpec } from '../sections/dataSources'
import { authedFetch } from '../services/auth/oidc'
import { docApiPath } from './docScope'

export interface LoadRestResult {
  manifest: DocManifest
  sections: SectionBundle[]
  images: Record<string, { data: string; mimeType: string }>
  plots: PlotSourceSpec
  tables: Record<string, TableData>
}

function joinUrl(base: string, path: string): string {
  return base.replace(/\/?$/, '') + path
}

async function fetchOptionalJson<T>(url: string, fallback: T): Promise<T> {
  // Bulk plots/tables/images endpoints return `{}` when the bundle has
  // none, but a deployment with an older paradoc-serve will 404. Treat
  // any non-2xx as the empty fallback rather than failing the doc load.
  try {
    const res = await authedFetch(url, { cache: 'no-store' })
    if (!res.ok) return fallback
    return (await res.json()) as T
  } catch {
    return fallback
  }
}

/** Manifest fetch failure; `status` lets callers distinguish a 404. */
export class RestLoadError extends Error {
  constructor(message: string, readonly status: number) {
    super(message)
    this.name = 'RestLoadError'
  }
}

export async function loadRestData(apiBase: string, docId: string): Promise<LoadRestResult> {
  const docPath = docApiPath(docId)

  const manifestRes = await authedFetch(joinUrl(apiBase, `${docPath}/manifest`), {
    cache: 'no-store',
  })
  if (!manifestRes.ok) {
    throw new RestLoadError(`manifest fetch failed: HTTP ${manifestRes.status}`, manifestRes.status)
  }
  const manifest = (await manifestRes.json()) as DocManifest

  // `manifest.sections` is every header H1..H6 (for outline / TOC),
  // but only H1s get their own `sections/<idx>.json` bundle on disk
  // — paradoc splits content by H1 only and numbers those bundles
  // 0..N-1 contiguously. Fetched in parallel; a failure ends the run.
  const h1Count = manifest.sections.filter((s) => (s.level ?? 1) === 1).length
  const numBundles = Math.max(h1Count, 1)
  const [sections, plots, tables] = await Promise.all([
    fetchSectionRun<SectionBundle>(numBundles, async (idx) => {
      const res = await authedFetch(joinUrl(apiBase, `${docPath}/sections/${idx}`), {
        cache: 'no-store',
      })
      if (!res.ok) {
        console.warn(`[paradoc] section ${idx} fetch failed: HTTP ${res.status}`)
        return undefined
      }
      return (await res.json()) as SectionBundle
    }),
    loadRestPlotSource(apiBase, docPath),
    fetchOptionalJson<Record<string, TableData>>(joinUrl(apiBase, `${docPath}/tables`), {}),
  ])

  // Images are NOT bulk-fetched anymore. resolveAssetUrl routes each
  // `<img src>` through `<doc>/files/<path>` for lazy fetching. The
  // empty seed keeps the return shape stable.
  const images: Record<string, { data: string; mimeType: string }> = {}

  return { manifest, sections, images, plots, tables }
}

/**
 * The plot index, with a fetcher for one plot's figure. A server that predates the index endpoint
 * 404s on it; fall back to the bulk `/plots` dict there, as the reader used to load it.
 */
async function loadRestPlotSource(apiBase: string, docPath: string): Promise<PlotSourceSpec> {
  try {
    const res = await authedFetch(joinUrl(apiBase, `${docPath}/plots-index`), { cache: 'no-store' })
    if (res.ok) {
      const index = (await res.json()) as Record<string, PlotIndexEntry>
      return {
        index,
        fetch: async (key) => {
          const r = await authedFetch(joinUrl(apiBase, `${docPath}/plots/${encodeURIComponent(key)}/figure`))
          if (r.status === 404) return undefined
          if (!r.ok) throw new Error(`plot ${key}: HTTP ${r.status}`)
          return await r.json()
        },
      }
    }
  } catch {
    // fall through to the bulk endpoint
  }
  return bulkPlotSource(await fetchOptionalJson<Record<string, any>>(joinUrl(apiBase, `${docPath}/plots`), {}))
}
