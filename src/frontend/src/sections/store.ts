import { useState } from 'react'
import type { DocManifest, SectionBundle } from '../ast/types'

// Very small IndexedDB helper. Bump the version when adding stores.
type StoreName =
  | 'sections'
  | 'manifests'
  | 'images'
  | 'plots'
  | 'tables'
  | 'three_d_meta'   // map ${docId}:${key} -> ThreeDMeta
  | 'three_d_blob'   // map sha256 -> ArrayBuffer (deduped by content hash)

function withDb<T>(fn: (db: IDBDatabase) => Promise<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('paradoc-cache', 4)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains('sections')) db.createObjectStore('sections')
      if (!db.objectStoreNames.contains('manifests')) db.createObjectStore('manifests')
      if (!db.objectStoreNames.contains('images')) db.createObjectStore('images')
      if (!db.objectStoreNames.contains('plots')) db.createObjectStore('plots')
      if (!db.objectStoreNames.contains('tables')) db.createObjectStore('tables')
      if (!db.objectStoreNames.contains('three_d_meta')) db.createObjectStore('three_d_meta')
      if (!db.objectStoreNames.contains('three_d_blob')) db.createObjectStore('three_d_blob')
    }
    req.onerror = () => reject(req.error)
    req.onsuccess = () => {
      const db = req.result
      fn(db).then((r) => { db.close(); resolve(r) }, (e) => { db.close(); reject(e) })
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
  if (cached) return cached

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

  const res = await fetch(url, { cache: 'no-store' })
  if (!res.ok) throw new Error(`manifest fetch failed: ${res.status} ${res.statusText}`)
  const ct = res.headers.get('content-type') || ''
  const text = await res.text()
  try {
    const m = JSON.parse(text) as DocManifest
    await dbPut('manifests', docId, m)
    return m
  } catch (e) {
    if (/^\s*<!doctype/i.test(text) || ct.includes('text/html')) {
      throw new Error('manifest fetch returned HTML instead of JSON. Ensure you are serving the JSON from the Paradoc HTTP server (default http://localhost:13580).')
    }
    throw e
  }
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
  const key = `${docId}:${plotKey}`
  return await dbGet<PlotData>('plots', key)
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
  const key = `${docId}:${tableKey}`
  return await dbGet<TableData>('tables', key)
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
 * Load all static data files and return the loaded data.
 * This is the main entry point for static mode.
 */
export async function loadStaticData(): Promise<{
  manifest: DocManifest
  sections: SectionBundle[]
  images: Record<string, { data: string; mimeType: string }>
  plots: Record<string, PlotData>
  tables: Record<string, TableData>
}> {
  const basePath = getStaticBasePath()

  // Load manifest
  const manifestRes = await fetch(`${basePath}manifest.json`, { cache: 'no-store' })
  if (!manifestRes.ok) {
    throw new Error(`Failed to load manifest: ${manifestRes.status} ${manifestRes.statusText}`)
  }
  const manifest = await manifestRes.json() as DocManifest

  // Load all sections
  const sections: SectionBundle[] = []
  for (const sectionMeta of manifest.sections) {
    const idx = sectionMeta.index
    const sectionRes = await fetch(`${basePath}sections/${idx}.json`, { cache: 'no-store' })
    if (sectionRes.ok) {
      const bundle = await sectionRes.json() as SectionBundle
      sections.push(bundle)
    } else {
      console.warn(`Failed to load section ${idx}: ${sectionRes.status}`)
    }
  }

  // Load images (optional)
  let images: Record<string, { data: string; mimeType: string }> = {}
  try {
    const imagesRes = await fetch(`${basePath}images.json`, { cache: 'no-store' })
    if (imagesRes.ok) {
      images = await imagesRes.json()
    }
  } catch {
    // images.json is optional
  }

  // Load plots (optional)
  let plots: Record<string, PlotData> = {}
  try {
    const plotsRes = await fetch(`${basePath}plots.json`, { cache: 'no-store' })
    if (plotsRes.ok) {
      plots = await plotsRes.json()
    }
  } catch {
    // plots.json is optional
  }

  // Load tables (optional)
  let tables: Record<string, TableData> = {}
  try {
    const tablesRes = await fetch(`${basePath}tables.json`, { cache: 'no-store' })
    if (tablesRes.ok) {
      tables = await tablesRes.json()
    }
  } catch {
    // tables.json is optional
  }

  return { manifest, sections, images, plots, tables }
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
