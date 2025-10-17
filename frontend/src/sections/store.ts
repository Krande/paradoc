import { useEffect, useMemo, useRef, useState } from 'react'
import type { DocManifest, SectionBundle, SectionMeta } from '../ast/types'

// Very small IndexedDB helper
function withDb<T>(fn: (db: IDBDatabase) => Promise<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('paradoc-cache', 1)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains('sections')) db.createObjectStore('sections')
      if (!db.objectStoreNames.contains('manifests')) db.createObjectStore('manifests')
    }
    req.onerror = () => reject(req.error)
    req.onsuccess = () => {
      const db = req.result
      fn(db).then((r) => { db.close(); resolve(r) }, (e) => { db.close(); reject(e) })
    }
  })
}

export async function dbPut(store: 'sections' | 'manifests', key: string, value: unknown): Promise<void> {
  return withDb<void>((db) => new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readwrite')
    const os = tx.objectStore(store)
    const req = os.put(value, key)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  }))
}

export async function dbGet<T>(store: 'sections' | 'manifests', key: string): Promise<T | undefined> {
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

  // Determine base URL: prefer window-provided httpDocBase or assetBase
  let base = ''
  try {
    const w: any = window as any
    if (w.__PARADOC_HTTP_DOC_BASE) {
      base = String(w.__PARADOC_HTTP_DOC_BASE)
    } else if (w.__PARADOC_ASSET_BASE) {
      base = String(w.__PARADOC_ASSET_BASE).replace(/\/?$/, '/') + `doc/${encodeURIComponent(docId)}/`
    }
  } catch {}
  const url = `${base || ''}doc/${encodeURIComponent(docId)}/manifest.json`.replace(/doc\/([^/]+)\/doc\//, 'doc/$1/')

  const res = await fetch(base ? url : `/doc/${encodeURIComponent(docId)}/manifest.json`, { cache: 'no-store' })
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

  // Determine base URL similar to fetchManifest
  let base = ''
  try {
    const w: any = window as any
    if (w.__PARADOC_HTTP_DOC_BASE) {
      base = String(w.__PARADOC_HTTP_DOC_BASE)
    } else if (w.__PARADOC_ASSET_BASE) {
      base = String(w.__PARADOC_ASSET_BASE).replace(/\/?$/, '/') + `doc/${encodeURIComponent(docId)}/`
    }
  } catch {}

  const relPath = index != null
    ? `doc/${encodeURIComponent(docId)}/section/${index}.json`
    : `doc/${encodeURIComponent(docId)}/section/${encodeURIComponent(sectionId)}.json`

  const full = (base ? (base.endsWith('/') ? base : base + '/') : '') + relPath
  const url = base ? full.replace(/doc\/([^/]+)\/doc\//, 'doc/$1/') : ('/' + relPath)

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

export function predictivePrefetch(docId: string, manifest: DocManifest, visibleIndex: number) {
  const next = manifest.sections[visibleIndex + 1]
  const prev = visibleIndex > 0 ? manifest.sections[visibleIndex - 1] : undefined
  if (next) void fetchSection(docId, next.id, next.index)
  if (prev) void fetchSection(docId, prev.id, prev.index)
}
