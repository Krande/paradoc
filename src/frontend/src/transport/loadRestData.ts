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

  const sections: SectionBundle[] = []
  for (const sectionMeta of manifest.sections) {
    const idx = sectionMeta.index
    const res = await fetch(joinUrl(apiBase, `${docPath}/sections/${idx}`), {
      cache: 'no-store',
    })
    if (!res.ok) {
      console.warn(`[paradoc] section ${idx} fetch failed: HTTP ${res.status}`)
      continue
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
