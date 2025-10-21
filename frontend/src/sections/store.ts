import { useState } from 'react'
import type { DocManifest, SectionBundle } from '../ast/types'

// Very small IndexedDB helper
function withDb<T>(fn: (db: IDBDatabase) => Promise<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('paradoc-cache', 3) // Increment version for new stores
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains('sections')) db.createObjectStore('sections')
      if (!db.objectStoreNames.contains('manifests')) db.createObjectStore('manifests')
      if (!db.objectStoreNames.contains('images')) db.createObjectStore('images')
      if (!db.objectStoreNames.contains('plots')) db.createObjectStore('plots')
      if (!db.objectStoreNames.contains('tables')) db.createObjectStore('tables')
    }
    req.onerror = () => reject(req.error)
    req.onsuccess = () => {
      const db = req.result
      fn(db).then((r) => { db.close(); resolve(r) }, (e) => { db.close(); reject(e) })
    }
  })
}

export async function dbPut(store: 'sections' | 'manifests' | 'images' | 'plots' | 'tables', key: string, value: unknown): Promise<void> {
  return withDb<void>((db) => new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readwrite')
    const os = tx.objectStore(store)
    const req = os.put(value, key)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  }))
}

export async function dbGet<T>(store: 'sections' | 'manifests' | 'images' | 'plots' | 'tables', key: string): Promise<T | undefined> {
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

  return { state, setManifest, upsertSection }
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
}

export async function getTableData(docId: string, tableKey: string): Promise<TableData | undefined> {
  const key = `${docId}:${tableKey}`
  return await dbGet<TableData>('tables', key)
}
