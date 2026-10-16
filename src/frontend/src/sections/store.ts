import { useState } from 'react'
import type { DocManifest, SectionBundle } from '../ast/types'
import {
  findPlot,
  findTable,
  getTable,
  hasPlotSource,
  hasTableSource,
  loadPlot,
  resolveKey,
} from './dataSources'
import { bulkPlotSource, fetchSectionRun } from './dataSources'
import type { PlotIndexEntry, PlotSourceSpec } from './dataSources'

// Very small IndexedDB helper. Bump the version when adding stores.
type StoreName =
  | 'sections'
  | 'manifests'
  | 'images'
  | 'plots'
  | 'tables'
  | 'three_d_meta'   // map ${docId}:${key} -> ThreeDMeta
  | 'three_d_blob'   // map sha256 -> ArrayBuffer (deduped by content hash)

// Bump on any schema change OR when we want to force-evict every
// client's cached data (the cache has no per-entry version key, so
// `fetchManifest` / `fetchSection` cheerfully return stale content
// after a bundle rebuild — this version bump is the only handle we
// have today to wipe everyone's IndexedDB without asking them to
// hit the Clear-cache button in the settings menu).
// v6: images are no longer bulk-preloaded into the `images` store —
// resolveAssetUrl resolves to a direct HTTP URL (static / REST) or
// reads from the `images` store only as the WS fallback. Bumping the
// version evicts any stale base64 entries the legacy bulk fetch wrote,
// so the new direct URL takes priority.
const DB_VERSION = 6
const STORE_NAMES: StoreName[] = [
  'sections',
  'manifests',
  'images',
  'plots',
  'tables',
  'three_d_meta',
  'three_d_blob',
]

function withDb<T>(fn: (db: IDBDatabase) => Promise<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('paradoc-cache', DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      // On upgrade — delete every existing store and recreate it
      // empty. Cheap one-line "wipe everyone's stale cache" knob:
      // bump DB_VERSION and the next visit clears its own state.
      for (const name of STORE_NAMES) {
        if (db.objectStoreNames.contains(name)) db.deleteObjectStore(name)
        db.createObjectStore(name)
      }
    }
    req.onerror = () => reject(req.error)
    req.onsuccess = () => {
      const db = req.result
      fn(db).then((r) => { db.close(); resolve(r) }, (e) => { db.close(); reject(e) })
    }
  })
}

/**
 * Wipe every entry across every store whose key is prefixed with
 * ``${docId}:``. Used by `fetchManifest` when the freshly-fetched
 * DocManifest's `published_at` differs from the one cached for this
 * docId — i.e. the bundle has been rebuilt since we last saw it, so
 * everything we have cached about its sections / images / plots /
 * tables / 3D-meta is stale.
 *
 * The `manifests` store keys by raw docId (no prefix) and gets a
 * direct delete. Other stores key by `${docId}:${specificKey}` so
 * we walk and prune.
 */
export async function invalidateDocCache(docId: string): Promise<void> {
  return withDb<void>((db) => new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAMES, 'readwrite')
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
    tx.onabort = () => reject(tx.error)

    // Top-level manifest is keyed exactly by docId.
    tx.objectStore('manifests').delete(docId)

    // Other stores are keyed `${docId}:${rest}`. Walk with a cursor
    // and delete matching entries; `IDBKeyRange.bound` would also
    // work for sorted string keys but cursors are clearer when the
    // key shape isn't strictly typed.
    const prefix = `${docId}:`
    const upper = `${docId};`  // ':' + 1; bounds the scan
    for (const name of STORE_NAMES) {
      if (name === 'manifests') continue
      const os = tx.objectStore(name)
      const range = IDBKeyRange.bound(prefix, upper, false, true)
      const req = os.openCursor(range)
      req.onsuccess = () => {
        const cur = req.result
        if (!cur) return
        cur.delete()
        cur.continue()
      }
    }
  }))
}

/**
 * Drop the entire `paradoc-cache` IndexedDB database. Used by the
 * "Clear cache" button in the settings menu when a user has stale
 * data after a bundle rebuild and the version-bump auto-wipe didn't
 * fire (e.g. someone manually skipped a release). The page is
 * expected to be reloaded immediately after.
 */
export async function clearAllCache(): Promise<void> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.deleteDatabase('paradoc-cache')
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
    req.onblocked = () => {
      // Some other tab still holds an open handle. Resolve anyway —
      // the delete will complete once that tab closes. Reload on
      // the caller side surfaces the lingering issue if any.
      resolve()
    }
  })
}

export async function dbPut(store: StoreName, key: string, value: unknown): Promise<void> {
  return withDb<void>((db) => new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readwrite')
    const os = tx.objectStore(store)
    const req = os.put(value, key)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  }))
}

export async function dbGet<T>(store: StoreName, key: string): Promise<T | undefined> {
  return withDb<T | undefined>((db) => new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readonly')
    const os = tx.objectStore(store)
    const req = os.get(key)
    req.onsuccess = () => resolve(req.result as T | undefined)
    req.onerror = () => reject(req.error)
  }))
}

export interface SectionState {
  manifest: DocManifest | null
  sections: Record<string, SectionBundle>
  order: string[] // list of section ids in order
}

export function useSectionStore() {
  const [state, setState] = useState<SectionState>({ manifest: null, sections: {}, order: [] })

  const setManifest = (m: DocManifest) => setState((s) => ({ ...s, manifest: m, order: m.sections.map((x) => x.id) }))
  const upsertSection = (b: SectionBundle) => setState((s) => ({ ...s, sections: { ...s.sections, [b.section.id]: b } }))
  // Drop manifest + section cache so the REST loader's `if (state.manifest) return`
  // guard releases and refetches for the newly-selected doc.
  const resetSections = () => setState({ manifest: null, sections: {}, order: [] })

  return { state, setManifest, upsertSection, resetSections }
}

export async function fetchManifest(docId: string): Promise<DocManifest> {
  const cached = await dbGet<DocManifest>('manifests', docId)

  // Build document base URL
  let docBase = ''
  try {
    const w: any = window as any
    if (w.__PARADOC_HTTP_DOC_BASE) {
      // Already something like http://host:13580/doc/{docId}/
      docBase = String(w.__PARADOC_HTTP_DOC_BASE)
    } else if (w.__PARADOC_ASSET_BASE) {
      const assetBase = String(w.__PARADOC_ASSET_BASE)
      docBase = assetBase.replace(/\/?$/, '/') + `doc/${encodeURIComponent(docId)}/`
    }
  } catch {}

  const url = docBase ? (docBase.replace(/\/?$/, '/') + 'manifest.json') : `/doc/${encodeURIComponent(docId)}/manifest.json`

  // Always HEAD-style hit the manifest endpoint so we see fresh
  // `published_at` even when we have a cached copy — that's the
  // hook for per-docId invalidation. The bundle manifest is small
  // (~few KB), so the round-trip is cheap.
  const res = await fetch(url, { cache: 'no-store' })
  if (!res.ok) {
    // Network failure with a cached manifest? Serve the cache —
    // working offline beats a hard failure. (No cached manifest →
    // throw as before.)
    if (cached) return cached
    throw new Error(`manifest fetch failed: ${res.status} ${res.statusText}`)
  }
  const ct = res.headers.get('content-type') || ''
  const text = await res.text()
  let fresh: DocManifest
  try {
    fresh = JSON.parse(text) as DocManifest
  } catch (e) {
    if (/^\s*<!doctype/i.test(text) || ct.includes('text/html')) {
      throw new Error('manifest fetch returned HTML instead of JSON. Ensure you are serving the JSON from the Paradoc HTTP server (default http://localhost:13580).')
    }
    throw e
  }

  // Per-docId auto-invalidation. Bundle exporter stamps the
  // manifest with `published_at` (mirrors BundleManifest); if the
  // value differs from what we have cached, wipe every store entry
  // scoped to this docId before recording the new manifest. Falls
  // back to "keep cache" only when neither side has the field —
  // that's the legacy-bundle case where we have nothing to compare.
  if (cached) {
    const a = cached.published_at
    const b = fresh.published_at
    if (a && b && a !== b) {
      await invalidateDocCache(docId)
    } else if (b && !a) {
      // Cache was written before the field existed — wipe defensively
      // so it can't keep masking a real change after the upgrade.
      await invalidateDocCache(docId)
    }
  }
  await dbPut('manifests', docId, fresh)
  return fresh
}

export async function fetchSection(docId: string, sectionId: string, index?: number): Promise<SectionBundle> {
  const key = `${docId}:${sectionId}`
  const cached = await dbGet<SectionBundle>('sections', key)
  if (cached) return cached

  // Build document base URL (same logic as in fetchManifest)
  let docBase = ''
  try {
    const w: any = window as any
    if (w.__PARADOC_HTTP_DOC_BASE) {
      docBase = String(w.__PARADOC_HTTP_DOC_BASE)
    } else if (w.__PARADOC_ASSET_BASE) {
      const assetBase = String(w.__PARADOC_ASSET_BASE)
      docBase = assetBase.replace(/\/?$/, '/') + `doc/${encodeURIComponent(docId)}/`
    }
  } catch {}

  const rel = index != null
    ? `section/${index}.json`
    : `section/${encodeURIComponent(sectionId)}.json`

  const url = docBase ? (docBase.replace(/\/?$/, '/') + rel) : `/doc/${encodeURIComponent(docId)}/${rel}`

  const res = await fetch(url, { cache: 'no-store' })
  if (!res.ok) throw new Error(`section fetch failed: ${res.status} ${res.statusText}`)
  const ct = res.headers.get('content-type') || ''
  const text = await res.text()
  try {
    const b = JSON.parse(text) as SectionBundle
    await dbPut('sections', key, b)
    return b
  } catch (e) {
    if (/^\s*<!doctype/i.test(text) || ct.includes('text/html')) {
      throw new Error('section fetch returned HTML instead of JSON. Ensure the Paradoc HTTP server is running and the path is correct.')
    }
    throw e
  }
}

export function predictivePrefetch(_docId: string, _manifest: DocManifest, _visibleIndex: number) {
  // DISABLED: Only using WebSocket communication, not HTTP/file fetching
  // Sections are delivered via WebSocket, no need for predictive prefetch
}

// Image storage helpers for embedded images
export async function storeEmbeddedImage(docId: string, imagePath: string, data: string, mimeType: string): Promise<void> {
  const key = `${docId}:${imagePath}`
  const dataUrl = `data:${mimeType};base64,${data}`
  await dbPut('images', key, dataUrl)
}

export async function getEmbeddedImage(docId: string, imagePath: string): Promise<string | undefined> {
  // Normalize path: remove leading ./ or /
  const normalizedPath = imagePath.replace(/^\.\//, '').replace(/^\//, '')
  const key = `${docId}:${normalizedPath}`
  return await dbGet<string>('images', key)
}

// Plot data storage helpers
export interface PlotData {
  key: string
  plot_type: string
  data: any
  caption: string
  width?: number
  height?: number
  custom_function_name?: string
  metadata?: Record<string, any>
}

export async function storePlotData(docId: string, plotKey: string, plotData: PlotData): Promise<void> {
  const key = `${docId}:${plotKey}`
  await dbPut('plots', key, plotData)
  // Notify listeners that plot data has been stored
  window.dispatchEvent(new CustomEvent('paradoc:plot-data-stored', { detail: { docId, plotKey } }))
}

export async function getPlotData(docId: string, plotKey: string): Promise<PlotData | undefined> {
  // Static / REST: the registered source fetches the plot on first use.
  if (hasPlotSource(docId)) return (await loadPlot(docId, plotKey)) as PlotData | undefined
  // WebSocket live view: the relay wrote it to IndexedDB.
  const key = `${docId}:${plotKey}`
  return await dbGet<PlotData>('plots', key)
}

/**
 * The plot key a figure's id resolves to (exact, or without a `_N` suffix) when the document has
 * interactive data for it; undefined otherwise. Never loads the plot itself.
 */
export async function resolvePlotKey(docId: string, plotKey: string): Promise<string | undefined> {
  if (hasPlotSource(docId)) return findPlot(docId, plotKey)
  const found = new Set<string>()
  for (const k of [plotKey, plotKey.replace(/_\d+$/, '')]) {
    if (!found.has(k) && (await dbGet<PlotData>('plots', `${docId}:${k}`))) found.add(k)
  }
  return resolveKey(plotKey, (k) => found.has(k))
}

// Table data storage helpers
export interface TableData {
  key: string
  columns: Array<{ name: string; data_type: string }>
  cells: Array<{ row_index: number; column_name: string; value: any }>
  caption: string
  default_sort?: { column_name: string; ascending: boolean }
  default_filter?: { column_name: string; pattern: string; is_regex: boolean }
  show_index_default: boolean
  metadata?: Record<string, any>
}

export async function storeTableData(docId: string, tableKey: string, tableData: TableData): Promise<void> {
  const key = `${docId}:${tableKey}`
  await dbPut('tables', key, tableData)
  // Notify listeners that table data has been stored
  window.dispatchEvent(new CustomEvent('paradoc:table-data-stored', { detail: { docId, tableKey } }))
}

export async function getTableData(docId: string, tableKey: string): Promise<TableData | undefined> {
  if (hasTableSource(docId)) return getTable(docId, tableKey) as TableData | undefined
  const key = `${docId}:${tableKey}`
  return await dbGet<TableData>('tables', key)
}

/** Like `resolvePlotKey`, for a table's interactive data. */
export async function resolveTableKey(docId: string, tableKey: string): Promise<string | undefined> {
  if (hasTableSource(docId)) return findTable(docId, tableKey)
  const found = new Set<string>()
  for (const k of [tableKey, tableKey.replace(/_\d+$/, '')]) {
    if (!found.has(k) && (await dbGet<TableData>('tables', `${docId}:${k}`))) found.add(k)
  }
  return resolveKey(tableKey, (k) => found.has(k))
}

// ========================================
// Static data loading for static web hosting
// ========================================

/**
 * Check if we're in static mode (data files served alongside the HTML)
 */
export function isStaticMode(): boolean {
  const w = window as any
  if (w.__PARADOC_CONFIG__?.transport === 'static') return true
  return !!w.__PARADOC_STATIC_MODE__ || !!w.__PARADOC_STATIC_BASE_PATH__
}

/**
 * Get the base path for static data files.
 * Defaults to './' (same directory as the HTML file)
 */
export function getStaticBasePath(): string {
  const w = window as any
  if (w.__PARADOC_STATIC_BASE_PATH__) {
    return String(w.__PARADOC_STATIC_BASE_PATH__).replace(/\/?$/, '/')
  }
  // Default to current directory
  return './'
}

/**
 * Load the static data files. This is the main entry point for static mode.
 *
 * Plot data is not loaded here: `plots_index.json` names the plots that have interactive data and
 * the file each one's data lives in, fetched when a reader switches that figure to interactive.
 * An export written before the per-plot split has only `plots.json`; it is fetched whole, as
 * before, and served from memory.
 */
export async function loadStaticData(): Promise<{
  manifest: DocManifest
  sections: SectionBundle[]
  images: Record<string, { data: string; mimeType: string }>
  plots: PlotSourceSpec
  tables: Record<string, TableData>
}> {
  const basePath = getStaticBasePath()

  // Start the optional side files with the manifest; none of them depends on it.
  const plotsP = loadStaticPlotSource(basePath)
  const tablesP = (async () => {
    try {
      const res = await fetch(`${basePath}tables.json`, { cache: 'no-store' })
      return res.ok ? ((await res.json()) as Record<string, TableData>) : {}
    } catch {
      return {} // tables.json is optional
    }
  })()

  const manifestRes = await fetch(`${basePath}manifest.json`, { cache: 'no-store' })
  if (!manifestRes.ok) {
    throw new Error(`Failed to load manifest: ${manifestRes.status} ${manifestRes.statusText}`)
  }
  const manifest = await manifestRes.json() as DocManifest

  // `manifest.sections` lists every header H1..H6 for the outline /
  // TOC, but only top-level (H1) headers get a `sections/<i>.json`
  // bundle on disk — paradoc splits content by H1 only and numbers
  // those bundles 0..N-1 contiguously. Fetch by H1 count rather than
  // by manifest index so we don't issue dozens of 404s for every
  // nested H2/H3.
  const h1Count = manifest.sections.filter((s: any) => (s.level ?? 1) === 1).length
  const numBundles = Math.max(h1Count, 1)
  const sections = await fetchSectionRun<SectionBundle>(numBundles, async (idx) => {
    const res = await fetch(`${basePath}sections/${idx}.json`, { cache: 'no-store' })
    if (!res.ok) {
      console.warn(`Failed to load section ${idx}: ${res.status}`)
      return undefined
    }
    return (await res.json()) as SectionBundle
  })

  // Images are no longer bundled into `images.json` (the legacy ~10 MB
  // base64 dict that gated the page render). The static exporter now
  // copies each referenced image file to `<basePath>/<path>` and
  // `resolveAssetUrl` constructs the direct URL on demand, so the
  // browser fetches them lazily via `<img loading="lazy">`. Kept as an
  // empty seed for back-compat with the existing call shape.
  const images: Record<string, { data: string; mimeType: string }> = {}

  const [plots, tables] = await Promise.all([plotsP, tablesP])
  return { manifest, sections, images, plots, tables }
}

async function loadStaticPlotSource(basePath: string): Promise<PlotSourceSpec> {
  try {
    const res = await fetch(`${basePath}plots_index.json`, { cache: 'no-store' })
    if (res.ok) {
      const index = (await res.json()) as Record<string, PlotIndexEntry>
      return {
        index,
        fetch: async (key, entry) => {
          const file = entry.file || `_plots/${encodeURIComponent(key)}.json`
          const r = await fetch(`${basePath}${file.split('/').map(encodeURIComponent).join('/')}`)
          if (!r.ok) throw new Error(`plot ${key}: HTTP ${r.status}`)
          return await r.json()
        },
      }
    }
  } catch {
    // fall through to the bulk file
  }
  // Export written before the per-plot split: only the bulk `plots.json` exists.
  let bulk: Record<string, PlotData> = {}
  try {
    const res = await fetch(`${basePath}plots.json`, { cache: 'no-store' })
    if (res.ok) bulk = await res.json()
  } catch {
    // plots.json is optional
  }
  return bulkPlotSource(bulk)
}

/**
 * Try to detect static mode by checking if manifest.json exists at the default path.
 */
export async function detectStaticMode(): Promise<boolean> {
  try {
    const res = await fetch('./manifest.json', { method: 'HEAD', cache: 'no-store' })
    return res.ok
  } catch {
    return false
  }
}
