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
  const res = await fetch(`/doc/${encodeURIComponent(docId)}/manifest.json`, { cache: 'no-store' })
  if (!res.ok) throw new Error('manifest fetch failed')
  const m = await res.json() as DocManifest
  await dbPut('manifests', docId, m)
  return m
}

export async function fetchSection(docId: string, sectionId: string, index?: number): Promise<SectionBundle> {
  const key = `${docId}:${sectionId}`
  const cached = await dbGet<SectionBundle>('sections', key)
  if (cached) return cached
  const path = index != null ? `/doc/${encodeURIComponent(docId)}/section/${index}.json` : `/doc/${encodeURIComponent(docId)}/section/${encodeURIComponent(sectionId)}.json`
  const res = await fetch(path, { cache: 'no-store' })
  if (!res.ok) throw new Error('section fetch failed')
  const b = await res.json() as SectionBundle
  await dbPut('sections', key, b)
  return b
}

export function predictivePrefetch(docId: string, manifest: DocManifest, visibleIndex: number) {
  const next = manifest.sections[visibleIndex + 1]
  const prev = visibleIndex > 0 ? manifest.sections[visibleIndex - 1] : undefined
  if (next) void fetchSection(docId, next.id, next.index)
  if (prev) void fetchSection(docId, prev.id, prev.index)
}
