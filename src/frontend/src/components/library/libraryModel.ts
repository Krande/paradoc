// Library data model shared by the landing page and the Library view: the
// flat doc list, search ranking, and the "Recent" merge of locally opened
// docs with server publish times.
//
// Pure functions with no imports, so `npm test` (Node's type-stripping test
// runner) can load this file directly.

export type ScopeKind = 'personal' | 'shared' | 'project'

export interface LibraryScope {
  /** URL-form scope: `shared`, `user:me`, `project:<slug>`. */
  ref: string
  kind: ScopeKind
  name: string
  /** Whether the UI offers delete for docs in this scope (the server enforces it regardless). */
  canDelete: boolean
}

export interface LibraryDoc {
  id: string
  /** Display title derived from the id (`load-case-summary` -> `Load case summary`). */
  title: string
  scopeRef: string
  scopeKind: ScopeKind
  scopeName: string
  publishedAt?: string
  /** `publishedAt` as epoch ms; undefined when missing or unparseable. */
  updatedMs?: number
  size?: number
  fileCount?: number
  branch?: string
  commit?: string
  dirty?: boolean
  paradocVersion?: string
}

export interface LibraryData {
  docs: LibraryDoc[]
  scopes: LibraryScope[]
  isAdmin: boolean
}

/** Stable key for a doc: the same id may exist in several scopes. */
export function docKey(d: { id: string; scopeRef: string }): string {
  return `${d.scopeRef}/${d.id}`
}

/**
 * Display title for a doc id. Separators become spaces one-for-one (so a match
 * found in the normalised title maps to the same character range in the display
 * title) and the first letter is capitalised. Ids without separators are kept.
 */
export function prettyTitle(id: string): string {
  if (!/[-_]/.test(id)) return id
  const spaced = id.replace(/[-_]/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

function parseMs(iso?: string): number | undefined {
  if (!iso) return undefined
  const t = Date.parse(iso)
  return Number.isNaN(t) ? undefined : t
}

function scopeKindOf(ref: string): ScopeKind {
  if (ref === 'user:me') return 'personal'
  if (ref.startsWith('project:')) return 'project'
  return 'shared'
}

/** Raw doc entry as sent by `/api/library` and `/api/landing`. */
export interface RawDoc {
  id: string
  scope?: string
  scope_ref?: string
  scope_name?: string
  published_at?: string
  updated_at?: string
  paradoc_version?: string
  size?: number
  file_count?: number
  git?: { short_commit?: string; branch?: string; is_dirty?: boolean } | null
}

function toDoc(raw: RawDoc, scopeRef: string, scopeName: string): LibraryDoc {
  const publishedAt = raw.published_at || raw.updated_at || undefined
  return {
    id: raw.id,
    title: prettyTitle(raw.id),
    scopeRef,
    scopeKind: scopeKindOf(scopeRef),
    scopeName,
    publishedAt,
    updatedMs: parseMs(publishedAt),
    size: typeof raw.size === 'number' ? raw.size : undefined,
    fileCount: typeof raw.file_count === 'number' ? raw.file_count : undefined,
    branch: raw.git?.branch || undefined,
    commit: raw.git?.short_commit || undefined,
    dirty: raw.git?.is_dirty || undefined,
    paradocVersion: raw.paradoc_version || undefined,
  }
}

/** Normalise a `/api/library` response. */
export function fromLibraryResponse(body: {
  is_admin?: boolean
  scopes?: { ref: string; kind?: string; name?: string; can_delete?: boolean }[]
  docs?: RawDoc[]
}): LibraryData {
  const scopes: LibraryScope[] = (body.scopes || []).map((s) => ({
    ref: s.ref,
    kind: scopeKindOf(s.ref),
    name: s.name || s.ref,
    canDelete: !!s.can_delete,
  }))
  const names = new Map(scopes.map((s) => [s.ref, s.name]))
  const docs = (body.docs || []).map((d) => {
    const ref = d.scope_ref || 'shared'
    return toDoc(d, ref, d.scope_name || names.get(ref) || ref)
  })
  return { docs, scopes, isAdmin: !!body.is_admin }
}

/**
 * Normalise an older server's `/api/landing` response (no `/api/library`).
 * `canDelete(ref)` decides the per-scope delete flag client-side.
 */
export function fromLandingResponse(
  body: {
    personal?: RawDoc[]
    shared?: RawDoc[]
    projects?: { slug: string; name: string; docs: RawDoc[] }[]
  },
  isAdmin: boolean,
  canDelete: (ref: string) => boolean,
): LibraryData {
  const scopes: LibraryScope[] = []
  const docs: LibraryDoc[] = []
  const add = (ref: string, name: string, raw: RawDoc[] | undefined, always: boolean) => {
    if (!always && !(raw && raw.length)) return
    scopes.push({ ref, kind: scopeKindOf(ref), name, canDelete: canDelete(ref) })
    for (const d of raw || []) docs.push(toDoc(d, ref, name))
  }
  add('user:me', 'Personal', body.personal, false)
  add('shared', 'Shared', body.shared, true)
  for (const p of body.projects || []) add(`project:${p.slug}`, p.name, p.docs, true)
  return { docs, scopes, isAdmin }
}

// ── Search ────────────────────────────────────────────────────────────────

/** Lower-case and turn separators into spaces, one character for one. */
export function normalizeText(s: string): string {
  return s.toLowerCase().replace(/[-_./:]/g, ' ')
}

export interface SearchHit {
  doc: LibraryDoc
  score: number
  /** [start, end) character ranges of the query terms in `doc.title`. */
  titleRanges: [number, number][]
}

function wordStarts(text: string, term: string): boolean {
  let i = text.indexOf(term)
  while (i !== -1) {
    if (i === 0 || text[i - 1] === ' ') return true
    i = text.indexOf(term, i + 1)
  }
  return false
}

function isSubsequence(text: string, term: string): boolean {
  let j = 0
  for (let i = 0; i < text.length && j < term.length; i++) if (text[i] === term[j]) j++
  return j === term.length
}

function termScore(doc: LibraryDoc, title: string, term: string): number {
  if (title.startsWith(term)) return 100
  if (wordStarts(title, term)) return 70
  if (title.includes(term)) return 40
  const scope = normalizeText(doc.scopeName)
  if (wordStarts(scope, term)) return 25
  if (scope.includes(term) || normalizeText(doc.scopeRef).includes(term)) return 15
  if (doc.branch && normalizeText(doc.branch).includes(term)) return 10
  if (term.length >= 3 && isSubsequence(title.replace(/ /g, ''), term)) return 5
  return 0
}

function mergeRanges(ranges: [number, number][]): [number, number][] {
  const sorted = [...ranges].sort((a, b) => a[0] - b[0])
  const out: [number, number][] = []
  for (const r of sorted) {
    const last = out[out.length - 1]
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1])
    else out.push([r[0], r[1]])
  }
  return out
}

/**
 * Rank `docs` against `query`. Every term must match the title, scope or
 * branch; title-prefix beats word-prefix beats substring beats scope /
 * branch matches. Ties go to the most recently updated doc, then by title.
 * An empty query returns no hits.
 */
export function rankDocs(query: string, docs: LibraryDoc[]): SearchHit[] {
  const q = normalizeText(query).trim().replace(/\s+/g, ' ')
  if (!q) return []
  const terms = q.split(' ')
  const hits: SearchHit[] = []
  for (const doc of docs) {
    const title = normalizeText(doc.title)
    let score = 0
    let ok = true
    for (const t of terms) {
      const s = termScore(doc, title, t)
      if (s === 0) {
        ok = false
        break
      }
      score += s
    }
    if (!ok) continue
    if (title === q) score += 50
    else if (terms.length > 1 && title.includes(q)) score += 30
    const ranges: [number, number][] = []
    for (const t of terms) {
      let i = title.indexOf(t)
      while (i !== -1) {
        ranges.push([i, i + t.length])
        i = title.indexOf(t, i + t.length)
      }
    }
    hits.push({ doc, score, titleRanges: mergeRanges(ranges) })
  }
  hits.sort(
    (a, b) =>
      b.score - a.score ||
      (b.doc.updatedMs || 0) - (a.doc.updatedMs || 0) ||
      a.doc.title.localeCompare(b.doc.title),
  )
  return hits
}

// ── Recents ───────────────────────────────────────────────────────────────

export const HISTORY_KEY = 'paradoc_recent_docs'
const HISTORY_CAP = 30

export interface HistoryEntry {
  id: string
  /** URL-form scope; `shared` for the shared scope. */
  scope: string
  openedAt: number
}

interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

/** Locally opened docs, newest first. Never throws (private mode, bad JSON). */
export function readHistory(storage: StorageLike | undefined): HistoryEntry[] {
  try {
    const raw = storage?.getItem(HISTORY_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter((e) => e && typeof e.id === 'string' && typeof e.openedAt === 'number')
      .map((e) => ({ id: e.id, scope: typeof e.scope === 'string' && e.scope ? e.scope : 'shared', openedAt: e.openedAt }))
      .sort((a, b) => b.openedAt - a.openedAt)
  } catch {
    return []
  }
}

function writeHistory(storage: StorageLike | undefined, entries: HistoryEntry[]): void {
  try {
    storage?.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, HISTORY_CAP)))
  } catch {
    // Storage full or blocked: recents fall back to server publish times.
  }
}

/** Record that a doc was opened (moves it to the front). */
export function recordOpen(storage: StorageLike | undefined, id: string, scope: string | undefined, now: number): void {
  if (!id) return
  const s = scope || 'shared'
  const rest = readHistory(storage).filter((e) => !(e.id === id && e.scope === s))
  writeHistory(storage, [{ id, scope: s, openedAt: now }, ...rest])
}

/** Drop a doc from local history (after it was deleted). */
export function forgetDoc(storage: StorageLike | undefined, id: string, scope: string): void {
  const all = readHistory(storage)
  const kept = all.filter((e) => !(e.id === id && e.scope === scope))
  if (kept.length !== all.length) writeHistory(storage, kept)
}

export interface RecentItem {
  doc: LibraryDoc
  /** The more recent of "opened here" and "published". */
  at: number
  reason: 'opened' | 'updated'
}

/**
 * Merge local open-history with server publish times. Only docs the server
 * still lists appear (deleted or no-longer-accessible ones drop out); each
 * doc's recency is the later of when it was opened here and when it was
 * last published.
 */
export function mergeRecents(docs: LibraryDoc[], history: HistoryEntry[], limit = 8): RecentItem[] {
  const opened = new Map<string, number>()
  for (const h of history) {
    const k = `${h.scope}/${h.id}`
    opened.set(k, Math.max(opened.get(k) || 0, h.openedAt))
  }
  const items: RecentItem[] = []
  for (const doc of docs) {
    const o = opened.get(docKey(doc)) || 0
    const u = doc.updatedMs || 0
    if (!o && !u) continue
    items.push({ doc, at: Math.max(o, u), reason: o >= u ? 'opened' : 'updated' })
  }
  items.sort((a, b) => b.at - a.at || a.doc.title.localeCompare(b.doc.title))
  return items.slice(0, limit)
}

// ── Library sort ──────────────────────────────────────────────────────────

export type SortKey = 'updated' | 'name'

export function sortDocs(docs: LibraryDoc[], key: SortKey): LibraryDoc[] {
  const out = [...docs]
  if (key === 'name') out.sort((a, b) => a.title.localeCompare(b.title, undefined, { sensitivity: 'base' }))
  else out.sort((a, b) => (b.updatedMs || 0) - (a.updatedMs || 0) || a.title.localeCompare(b.title))
  return out
}

// ── Formatting ────────────────────────────────────────────────────────────

export function formatRelative(ms: number | undefined, now: number = Date.now()): string {
  if (!ms) return ''
  const diff = now - ms
  if (diff < 0) return 'just now'
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return 'just now'
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.floor(hr / 24)
  if (day < 30) return `${day}d ago`
  const mon = Math.floor(day / 30)
  if (mon < 12) return `${mon}mo ago`
  return `${Math.floor(mon / 12)}y ago`
}

export function formatSize(bytes: number | undefined): string {
  if (bytes === undefined || bytes < 0) return ''
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let v = bytes / 1024
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`
}
