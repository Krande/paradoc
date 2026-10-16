import { create } from 'zustand'
import { authedFetch } from '../../services/auth/oidc'
import { getRuntimeConfig } from '../../transport'
import { canDeleteInScope } from '../../transport/docScope'
import { docKey, forgetDoc, fromLandingResponse, fromLibraryResponse, type LibraryData, type LibraryDoc } from './libraryModel'

// One shared copy of the doc list for the landing page, the Library view and
// the topbar's doc switcher, so moving between them doesn't refetch.
//
// Prefers `/api/library`; an older server without it falls back to
// `/api/landing`, then to the flat shared-only `/api/docs`.

function joinUrl(base: string, path: string): string {
  return base.replace(/\/?$/, '') + path
}

async function fetchJson(path: string): Promise<{ status: number; body: any }> {
  const res = await authedFetch(joinUrl(getRuntimeConfig().apiBase || '', path), { cache: 'no-store' })
  if (!res.ok) return { status: res.status, body: null }
  return { status: res.status, body: await res.json() }
}

async function loadLibrary(withSizes: boolean): Promise<LibraryData> {
  const lib = await fetchJson(withSizes ? '/api/library?sizes=1' : '/api/library')
  if (lib.body) return fromLibraryResponse(lib.body)
  if (lib.status !== 404) throw new Error(`HTTP ${lib.status}`)

  let isAdmin = false
  try {
    const me = await fetchJson('/api/me')
    isAdmin = !!me.body?.is_admin
  } catch {}
  const canDelete = (ref: string) => canDeleteInScope(ref, isAdmin)
  const landing = await fetchJson('/api/landing')
  if (landing.body) return fromLandingResponse(landing.body, isAdmin, canDelete)
  if (landing.status !== 404) throw new Error(`HTTP ${landing.status}`)
  const flat = await fetchJson('/api/docs')
  if (!flat.body) throw new Error(`HTTP ${flat.status}`)
  const ids: string[] = flat.body.docs || []
  return fromLandingResponse({ shared: ids.map((id) => ({ id })) }, isAdmin, canDelete)
}

interface LibraryState {
  data: LibraryData | null
  /** Whether `data` carries bundle sizes. */
  hasSizes: boolean
  loading: boolean
  error: string | null
  /** Load once; `sizes` upgrades an earlier sizeless load. */
  ensure: (opts?: { sizes?: boolean }) => void
  /** Delete a doc on the server, then drop it from the list and local history. */
  remove: (doc: LibraryDoc) => Promise<void>
}

let inflight: Promise<void> | null = null

export const useLibrary = create<LibraryState>((set, get) => ({
  data: null,
  hasSizes: false,
  loading: false,
  error: null,
  ensure: (opts) => {
    const sizes = !!opts?.sizes
    const s = get()
    if (getRuntimeConfig().transport !== 'rest') return
    if (s.data && (s.hasSizes || !sizes)) return
    if (inflight && !sizes) return
    set({ loading: !s.data, error: null })
    const p = loadLibrary(sizes)
      .then((data) => set({ data, hasSizes: sizes, loading: false, error: null }))
      .catch((err: unknown) => {
        // Keep showing an earlier (sizeless) list if only the upgrade failed.
        if (get().data) set({ loading: false })
        else set({ loading: false, error: String((err as Error)?.message || err) })
      })
      .finally(() => {
        if (inflight === p) inflight = null
      })
    inflight = p
  },
  remove: async (doc) => {
    const path = `/api/scopes/${encodeURIComponent(doc.scopeRef)}/docs/${encodeURIComponent(doc.id)}`
    const res = await authedFetch(joinUrl(getRuntimeConfig().apiBase || '', path), { method: 'DELETE' })
    if (!res.ok && res.status !== 404) {
      let detail = `HTTP ${res.status}`
      try {
        const body = await res.json()
        if (body?.detail) detail = String(body.detail)
      } catch {}
      throw new Error(detail)
    }
    // Gone (or already gone).
    const key = docKey(doc)
    const data = get().data
    if (data) set({ data: { ...data, docs: data.docs.filter((d) => docKey(d) !== key) } })
    try {
      forgetDoc(window.localStorage, doc.id, doc.scopeRef)
    } catch {}
  },
}))
