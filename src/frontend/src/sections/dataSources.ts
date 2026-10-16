// In-memory sources for a document's plot and table data (static and REST modes).
//
// Plots used to arrive as one bulk dict (`plots.json` / `GET <doc>/plots`, megabytes of Plotly
// JSON) that was parsed and written into IndexedDB, plot by plot, before the reader settled --
// although every plot first shows as its static image. Now the loader registers a small index
// (which keys have interactive data) and a fetcher, and a plot's figure is fetched only when the
// reader asks for it. Bundles that have only the bulk file register it through `bulkPlotSource`
// and are served from memory the same way.
//
// Tables are small and stay bulk-loaded, but they are kept in memory here rather than written to
// IndexedDB one by one. The WebSocket live view still stores both in IndexedDB (see store.ts),
// which is what the components fall back to when no source is registered for a document.
//
// No DOM or IndexedDB imports: this module is unit-tested under plain Node.

export interface PlotIndexEntry {
  /** Bundle-relative path of the plot's own JSON file (static exports). */
  file?: string
  caption?: string
  width?: number | null
  height?: number | null
  plot_type?: string | null
}

export type PlotFetcher = (key: string, entry: PlotIndexEntry) => Promise<any | undefined>

interface DocPlots {
  index: Map<string, PlotIndexEntry>
  fetch: PlotFetcher
  loaded: Map<string, any>
  inflight: Map<string, Promise<any | undefined>>
}

const plotSources = new Map<string, DocPlots>()
const tableSources = new Map<string, Map<string, any>>()

function notify(name: string, detail: Record<string, unknown>) {
  if (typeof window === 'undefined' || typeof CustomEvent === 'undefined') return
  window.dispatchEvent(new CustomEvent(name, { detail }))
}

/**
 * The key a figure or table id refers to: the exact key, or -- for an id carrying a numeric
 * suffix (`key_1`, `key_2`, a plot used more than once) -- the key without it.
 */
export function resolveKey(key: string, has: (k: string) => boolean): string | undefined {
  if (has(key)) return key
  const i = key.lastIndexOf('_')
  if (i > 0 && /^\d+$/.test(key.substring(i + 1))) {
    const base = key.substring(0, i)
    if (has(base)) return base
  }
  return undefined
}

/** Register a document's plot index and the fetcher that loads one plot's data. */
export function registerPlotSource(docId: string, index: Record<string, PlotIndexEntry>, fetch: PlotFetcher) {
  plotSources.set(docId, {
    index: new Map(Object.entries(index || {})),
    fetch,
    loaded: new Map(),
    inflight: new Map(),
  })
  notify('paradoc:plot-data-stored', { docId, plotKey: '*' })
}

/** Where a document's interactive plot data comes from: an index of keys, and a per-key fetcher. */
export interface PlotSourceSpec {
  index: Record<string, PlotIndexEntry>
  fetch: PlotFetcher
}

/** Legacy bundles: the whole `plots.json` dict is already in hand; serve plots out of it. */
export function bulkPlotSource(bulk: Record<string, any>): PlotSourceSpec {
  const all = bulk || {}
  const index: Record<string, PlotIndexEntry> = {}
  for (const [k, v] of Object.entries(all)) {
    index[k] = { caption: v?.caption, width: v?.width, height: v?.height, plot_type: v?.plot_type }
  }
  return { index, fetch: async (key) => all[key] }
}

export function hasPlotSource(docId: string): boolean {
  return plotSources.has(docId)
}

/** The registered key a figure's plot key resolves to, or undefined when it has no plot data. */
export function findPlot(docId: string, key: string): string | undefined {
  const src = plotSources.get(docId)
  if (!src) return undefined
  return resolveKey(key, (k) => src.index.has(k))
}

/** Load one plot's data: fetched once, on first request, then served from memory. */
export function loadPlot(docId: string, key: string): Promise<any | undefined> {
  const src = plotSources.get(docId)
  if (!src) return Promise.resolve(undefined)
  const k = resolveKey(key, (x) => src.index.has(x))
  if (!k) return Promise.resolve(undefined)
  if (src.loaded.has(k)) return Promise.resolve(src.loaded.get(k))
  const pending = src.inflight.get(k)
  if (pending) return pending
  const p = src
    .fetch(k, src.index.get(k) || {})
    .then((data) => {
      if (data !== undefined) src.loaded.set(k, data)
      return data
    })
    .finally(() => src.inflight.delete(k))
  src.inflight.set(k, p)
  return p
}

export function registerTables(docId: string, tables: Record<string, any>) {
  tableSources.set(docId, new Map(Object.entries(tables || {})))
  notify('paradoc:table-data-stored', { docId, tableKey: '*' })
}

export function hasTableSource(docId: string): boolean {
  return tableSources.has(docId)
}

export function findTable(docId: string, key: string): string | undefined {
  const t = tableSources.get(docId)
  if (!t) return undefined
  return resolveKey(key, (k) => t.has(k))
}

export function getTable(docId: string, key: string): any | undefined {
  const t = tableSources.get(docId)
  if (!t) return undefined
  const k = resolveKey(key, (x) => t.has(x))
  return k ? t.get(k) : undefined
}

/**
 * Fetch JSON documents `0..n-1` in parallel and keep the leading run that loaded: the old serial
 * loop stopped at the first failure, and a gap must still end the list there.
 */
export async function fetchSectionRun<T>(n: number, load: (idx: number) => Promise<T | undefined>): Promise<T[]> {
  const results = await Promise.all(
    Array.from({ length: n }, (_, idx) => load(idx).catch(() => undefined)),
  )
  const out: T[] = []
  for (const r of results) {
    if (r === undefined) break
    out.push(r)
  }
  return out
}

/** Drop a document's registered sources (doc switch, tests). */
export function clearDataSources(docId?: string) {
  if (docId === undefined) {
    plotSources.clear()
    tableSources.clear()
  } else {
    plotSources.delete(docId)
    tableSources.delete(docId)
  }
}
