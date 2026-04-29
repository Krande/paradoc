// REST-backed analogue of `loadStaticData()`. Hits the paradoc-serve
// endpoints `/api/docs/{id}/manifest` and `/api/docs/{id}/sections/{idx}`
// to assemble the same structure the static loader returns. Tables /
// plots / 3D blobs continue to flow through `RESTTransport` lazily —
// not pre-loaded here.

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

export async function loadRestData(apiBase: string, docId: string): Promise<LoadRestResult> {
  const manifestRes = await fetch(joinUrl(apiBase, `/api/docs/${encodeURIComponent(docId)}/manifest`), {
    cache: 'no-store',
  })
  if (!manifestRes.ok) {
    throw new Error(`manifest fetch failed: HTTP ${manifestRes.status}`)
  }
  const manifest = (await manifestRes.json()) as DocManifest

  const sections: SectionBundle[] = []
  for (const sectionMeta of manifest.sections) {
    const idx = sectionMeta.index
    const res = await fetch(joinUrl(apiBase, `/api/docs/${encodeURIComponent(docId)}/sections/${idx}`), {
      cache: 'no-store',
    })
    if (!res.ok) {
      console.warn(`[paradoc] section ${idx} fetch failed: HTTP ${res.status}`)
      continue
    }
    sections.push((await res.json()) as SectionBundle)
  }

  // tables/plots/images stay lazy; the static-mode store helpers populate
  // them as renderers fetch — same pattern static mode uses for plots
  // when the bundle ships referenced (not embedded) plot data.
  return { manifest, sections, images: {}, plots: {}, tables: {} }
}
