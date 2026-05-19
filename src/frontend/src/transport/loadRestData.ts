// REST-backed analogue of `loadStaticData()`. Hits the paradoc-serve
// endpoints `/api/docs/{id}/manifest`, `/api/docs/{id}/sections/{idx}`,
// and the bulk `/plots` `/tables` `/images` endpoints (same shape as
// the static-mode `plots.json` / `tables.json` / `images.json` dumps)
// to assemble the same structure the static loader returns. 3D blobs
// continue to flow through `RESTTransport` lazily.

import type { DocManifest, SectionBundle } from '../ast/types'
import type { PlotData, TableData } from '../sections/store'

export interface LoadRestResult {
  manifest: DocManifest
  sections: SectionBundle[]
  images: Record<string, { data: string; mimeType: string }>
  plots: Record<string, PlotData>
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
    const res = await fetch(url, { cache: 'no-store' })
    if (!res.ok) return fallback
    return (await res.json()) as T
  } catch {
    return fallback
  }
}

export async function loadRestData(apiBase: string, docId: string): Promise<LoadRestResult> {
  const docPath = `/api/docs/${encodeURIComponent(docId)}`

  const manifestRes = await fetch(joinUrl(apiBase, `${docPath}/manifest`), {
    cache: 'no-store',
  })
  if (!manifestRes.ok) {
    throw new Error(`manifest fetch failed: HTTP ${manifestRes.status}`)
  }
  const manifest = (await manifestRes.json()) as DocManifest

  // `manifest.sections` is every header H1..H6 (for outline / TOC),
  // but only H1s get their own `sections/<idx>.json` bundle on disk
  // — paradoc splits content by H1 only and numbers those bundles
  // 0..N-1 contiguously. Static mode iterates by H1 count
  // (`loadStaticData`); REST mode used to iterate every header's
  // index, hitting a 404 on every nested H2/H3 in the doc.
  const sections: SectionBundle[] = []
  const h1Count = manifest.sections.filter((s) => (s.level ?? 1) === 1).length
  const numBundles = Math.max(h1Count, 1)
  for (let idx = 0; idx < numBundles; idx += 1) {
    const res = await fetch(joinUrl(apiBase, `${docPath}/sections/${idx}`), {
      cache: 'no-store',
    })
    if (!res.ok) {
      console.warn(`[paradoc] section ${idx} fetch failed: HTTP ${res.status}`)
      break
    }
    sections.push((await res.json()) as SectionBundle)
  }

  // Pull plots/tables/images as bulk dicts in parallel — same shape as
  // static mode's plots.json/tables.json/images.json. Without this seed,
  // InteractiveFigure/InteractiveTable look for IndexedDB entries that
  // never get written and silently fall back to non-interactive renders.
  const [plots, tables, images] = await Promise.all([
    fetchOptionalJson<Record<string, PlotData>>(joinUrl(apiBase, `${docPath}/plots`), {}),
    fetchOptionalJson<Record<string, TableData>>(joinUrl(apiBase, `${docPath}/tables`), {}),
    fetchOptionalJson<Record<string, { data: string; mimeType: string }>>(
      joinUrl(apiBase, `${docPath}/images`),
      {},
    ),
  ])

  return { manifest, sections, images, plots, tables }
}
