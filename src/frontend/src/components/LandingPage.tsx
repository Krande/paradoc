import React from 'react'
import { authedFetch } from '../services/auth/oidc'
import { getRuntimeConfig } from '../transport'
import { canDeleteInScope, landingScopeRef } from '../transport/docScope'

// Sectioned landing: Recent strip, Personal, Shared, Projects.
//
// Backend contract (preferred):
//   GET /api/landing → {
//     recent:   LandingDoc[],
//     personal: LandingDoc[],
//     shared:   LandingDoc[],
//     projects: { slug: string, name: string, docs: LandingDoc[] }[],
//   }
//
// Fallback (used until /api/landing ships): hits /api/docs and renders
// every result under "Shared" — that matches the current behavior of
// DocList. Personal/Projects sections stay hidden in fallback mode.

interface GitInfo {
  short_commit: string
  branch: string
  is_dirty: boolean
  remote_url?: string
}

interface LandingDoc {
  id: string
  title?: string
  /** Legacy field kept for backwards-compat with the /api/docs fallback. */
  updated_at?: string
  /** v2 manifest field. The card displays this when present, falling
   *  back to updated_at then to "no timestamp". */
  published_at?: string
  paradoc_version?: string
  git?: GitInfo
  scope?: 'shared' | 'personal' | 'project'
  /** URL-form scope (`shared`, `user:me`, `project:<slug>`) used to
   *  route the doc's REST calls. Older servers omit it; the SPA then
   *  derives it from `scope` (+ the project group's slug). */
  scope_ref?: string
}

interface ProjectGroup {
  slug: string
  name: string
  docs: LandingDoc[]
}

interface LandingResponse {
  recent?: LandingDoc[]
  personal?: LandingDoc[]
  shared?: LandingDoc[]
  projects?: ProjectGroup[]
}

type SelectDoc = (docId: string, scope?: string) => void

/** Deletes a doc; resolves when it is gone, rejects with a message to show on the card. */
type DeleteDoc = (doc: LandingDoc, scopeRef: string) => Promise<void>


interface LandingPageProps {
  onSelect: SelectDoc
}

function joinUrl(base: string, path: string): string {
  return base.replace(/\/?$/, '') + path
}

function formatRelative(iso?: string): string {
  if (!iso) return ''
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return ''
  const diff = Date.now() - t
  if (diff < 0) return ''
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

function ScopeChip({ scope }: { scope?: LandingDoc['scope'] }) {
  if (!scope) return null
  const text = scope === 'personal' ? 'me' : scope === 'project' ? 'project' : 'shared'
  return (
    <span className="inline-flex items-center text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
      {text}
    </span>
  )
}

function GitFooter({ git, ts }: { git?: GitInfo; ts?: string }) {
  const branch = git?.branch || ''
  const sha = git?.short_commit || ''
  const dirty = git?.is_dirty
  const rel = ts ? formatRelative(ts) : ''
  // Footer renders only when we have at least one of git, timestamp.
  if (!branch && !sha && !rel) return null
  return (
    <div className="mt-2 flex items-center gap-1.5 text-[11px] text-gray-500 dark:text-gray-400 font-mono">
      {dirty && (
        <span
          title="Built from a dirty working tree"
          className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500"
        />
      )}
      {(branch || sha) && (
        <span className="truncate min-w-0">
          {branch ? branch : ''}
          {branch && sha ? '@' : ''}
          {sha}
        </span>
      )}
      {(branch || sha) && rel && <span className="text-gray-300 dark:text-gray-700">·</span>}
      {rel && <span className="whitespace-nowrap">{rel}</span>}
    </div>
  )
}

function DocCard({
  doc,
  onSelect,
  onDelete,
  isAdmin = false,
  compact = false,
  projectSlug,
}: {
  doc: LandingDoc
  onSelect: SelectDoc
  onDelete?: DeleteDoc
  isAdmin?: boolean
  compact?: boolean
  projectSlug?: string
}) {
  const ts = doc.published_at || doc.updated_at
  const scopeRef = landingScopeRef(doc, projectSlug) || 'shared'
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const deletable = !!onDelete && canDeleteInScope(scopeRef, isAdmin)

  const remove = async () => {
    if (!onDelete || busy) return
    const where = scopeRef === 'shared' ? 'the shared scope' : scopeRef === 'user:me' ? 'your personal scope' : scopeRef
    if (!window.confirm(`Delete "${doc.title || doc.id}" from ${where}?\n\nThis removes the published report and cannot be undone.`)) return
    setBusy(true)
    setError(null)
    try {
      await onDelete(doc, scopeRef)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'delete failed')
      setBusy(false)
    }
  }

  return (
    // The card holds two sibling buttons -- open (the whole card) and delete (top-right) -- since a
    // button cannot contain another.
    <div className={'relative group ' + (compact ? 'w-56 shrink-0' : '')}>
      <button
        onClick={() => onSelect(doc.id, scopeRef)}
        disabled={busy}
        className={
          'w-full h-full text-left rounded-lg border border-gray-200 dark:border-gray-800 ' +
          'bg-white dark:bg-gray-900 hover:border-gray-400 dark:hover:border-gray-600 ' +
          'hover:shadow-sm transition cursor-pointer disabled:opacity-50 ' +
          (compact ? 'p-3' : 'p-4')
        }
      >
        <div className={'flex items-start justify-between gap-2 mb-2 ' + (deletable ? 'pr-8' : '')}>
          <ScopeChip scope={doc.scope} />
        </div>
        <p className="font-medium text-gray-900 dark:text-gray-100 break-words leading-snug">
          {doc.title || doc.id}
        </p>
        {doc.title && doc.title !== doc.id && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 break-all">{doc.id}</p>
        )}
        <GitFooter git={doc.git} ts={ts} />
        {error && <p className="text-xs text-red-600 dark:text-red-400 mt-2">Could not delete: {error}</p>}
      </button>
      {deletable && (
        <button
          type="button"
          onClick={remove}
          disabled={busy}
          aria-label={`Delete ${doc.title || doc.id}`}
          title="Delete this report"
          className={
            'absolute top-2 right-2 rounded p-1.5 cursor-pointer text-gray-400 ' +
            'hover:text-red-600 hover:bg-red-50 dark:hover:text-red-400 dark:hover:bg-red-950/40 ' +
            // Always visible on touch screens (no hover); on desktop it shows on card hover/focus.
            'sm:opacity-0 sm:group-hover:opacity-100 sm:focus:opacity-100 transition disabled:opacity-50'
          }
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" className="w-4 h-4" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
          </svg>
        </button>
      )}
    </div>
  )
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-xs uppercase tracking-wider font-semibold text-gray-500 dark:text-gray-400 mb-3 mt-8 first:mt-0">
      {children}
    </h2>
  )
}

function ProjectGroupView({
  group,
  onSelect,
  onDelete,
  isAdmin,
}: {
  group: ProjectGroup
  onSelect: SelectDoc
  onDelete?: DeleteDoc
  isAdmin?: boolean
}) {
  const [open, setOpen] = React.useState(true)
  return (
    <div className="mb-4">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 cursor-pointer mb-2"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className={'w-4 h-4 transition-transform ' + (open ? 'rotate-90' : '')}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        <span>{group.name}</span>
        <span className="text-xs text-gray-400 dark:text-gray-500 ml-1">
          {group.docs.length}
        </span>
      </button>
      {open && (
        <div className="ml-5">
          {group.docs.length === 0 ? (
            <p className="text-sm text-gray-400 dark:text-gray-500 italic">
              No reports yet.
            </p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {group.docs.map((d) => (
                <DocCard key={d.id} doc={d} onSelect={onSelect} onDelete={onDelete} isAdmin={isAdmin} projectSlug={group.slug} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function LandingPage({ onSelect }: LandingPageProps) {
  const [data, setData] = React.useState<LandingResponse | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [isAdmin, setIsAdmin] = React.useState(false)

  // Only decides whether shared cards show a delete button; the server enforces it regardless.
  React.useEffect(() => {
    const apiBase = getRuntimeConfig().apiBase || ''
    let canceled = false
    authedFetch(joinUrl(apiBase, '/api/me'), { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((me) => {
        if (!canceled && me) setIsAdmin(!!me.is_admin)
      })
      .catch(() => {})
    return () => {
      canceled = true
    }
  }, [])

  const deleteDoc: DeleteDoc = React.useCallback(async (doc, scopeRef) => {
    const apiBase = getRuntimeConfig().apiBase || ''
    const res = await authedFetch(
      joinUrl(apiBase, `/api/scopes/${encodeURIComponent(scopeRef)}/docs/${encodeURIComponent(doc.id)}`),
      { method: 'DELETE' },
    )
    if (!res.ok && res.status !== 404) {
      let detail = `HTTP ${res.status}`
      try {
        const body = await res.json()
        if (body?.detail) detail = String(body.detail)
      } catch {}
      throw new Error(detail)
    }
    // Gone (or already gone): drop it from every list, Recent included.
    const keep = (d: LandingDoc, slug?: string) => !(d.id === doc.id && (landingScopeRef(d, slug) || 'shared') === scopeRef)
    setData((prev) =>
      prev && {
        ...prev,
        recent: prev.recent?.filter((d) => keep(d)),
        personal: prev.personal?.filter((d) => keep(d)),
        shared: prev.shared?.filter((d) => keep(d)),
        projects: prev.projects?.map((p) => ({ ...p, docs: p.docs.filter((d) => keep(d, p.slug)) })),
      },
    )
  }, [])

  React.useEffect(() => {
    const cfg = getRuntimeConfig()
    const apiBase = cfg.apiBase || ''
    let canceled = false
    ;(async () => {
      try {
        const res = await authedFetch(joinUrl(apiBase, '/api/landing'), {
          cache: 'no-store',
        })
        if (res.ok) {
          const body = (await res.json()) as LandingResponse
          if (!canceled) {
            setData(body)
            setLoading(false)
          }
          return
        }
        if (res.status !== 404) {
          throw new Error(`HTTP ${res.status}`)
        }
        // Fallback: aggregator not deployed yet → use /api/docs as
        // "Shared". Personal/Projects sections stay hidden.
        const flat = await authedFetch(joinUrl(apiBase, '/api/docs'), {
          cache: 'no-store',
        })
        if (!flat.ok) throw new Error(`HTTP ${flat.status}`)
        const fb = (await flat.json()) as { docs: string[] }
        if (!canceled) {
          setData({
            recent: [],
            personal: [],
            shared: (fb.docs || []).map((id) => ({ id, scope: 'shared' as const })),
            projects: [],
          })
          setLoading(false)
        }
      } catch (err: any) {
        if (canceled) return
        setError(String(err?.message || err))
        setLoading(false)
      }
    })()
    return () => {
      canceled = true
    }
  }, [])

  if (loading) {
    return (
      <div className="flex-1 overflow-auto overscroll-contain px-4 sm:px-8 py-6">
        <p className="text-sm text-gray-500 dark:text-gray-400">Loading reports…</p>
      </div>
    )
  }
  if (error) {
    return (
      <div className="flex-1 overflow-auto overscroll-contain px-4 sm:px-8 py-6">
        <div className="border border-red-300 dark:border-red-800 rounded-lg bg-red-50 dark:bg-red-950/30 p-4 max-w-xl">
          <p className="text-red-700 dark:text-red-300 font-semibold">
            Could not load reports
          </p>
          <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>
        </div>
      </div>
    )
  }
  if (!data) return null

  const recent = data.recent || []
  const personal = data.personal || []
  const shared = data.shared || []
  const projects = data.projects || []
  const everythingEmpty =
    recent.length === 0 &&
    personal.length === 0 &&
    shared.length === 0 &&
    projects.every((p) => p.docs.length === 0)

  return (
    <div className="flex-1 overflow-auto overscroll-contain">
      <div className="max-w-6xl mx-auto px-4 sm:px-8 py-6">
        {everythingEmpty ? (
          <div className="text-sm text-gray-500 dark:text-gray-400 mt-8">
            No reports yet. Publish a paradoc bundle to your shared, personal,
            or project scope and it will show up here.
          </div>
        ) : (
          <>
            {recent.length > 0 && (
              <section>
                <SectionHeader>Recent</SectionHeader>
                <div className="flex gap-3 overflow-x-auto pb-1 -mx-1 px-1">
                  {recent.map((d) => (
                    <DocCard key={`${d.scope_ref || d.scope}:${d.id}`} doc={d} onSelect={onSelect} onDelete={deleteDoc} isAdmin={isAdmin} compact />
                  ))}
                </div>
              </section>
            )}

            {personal.length > 0 && (
              <section>
                <SectionHeader>Personal</SectionHeader>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {personal.map((d) => (
                    <DocCard key={d.id} doc={d} onSelect={onSelect} onDelete={deleteDoc} isAdmin={isAdmin} />
                  ))}
                </div>
              </section>
            )}

            {shared.length > 0 && (
              <section>
                <SectionHeader>Shared</SectionHeader>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {shared.map((d) => (
                    <DocCard key={d.id} doc={d} onSelect={onSelect} onDelete={deleteDoc} isAdmin={isAdmin} />
                  ))}
                </div>
              </section>
            )}

            {projects.length > 0 && (
              <section>
                <SectionHeader>Projects</SectionHeader>
                {projects.map((p) => (
                  <ProjectGroupView key={p.slug} group={p} onSelect={onSelect} onDelete={deleteDoc} isAdmin={isAdmin} />
                ))}
              </section>
            )}
          </>
        )}
      </div>
    </div>
  )
}
