import React from 'react'
import { authedFetch } from '../services/auth/oidc'
import { getRuntimeConfig } from '../transport'

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

interface LandingDoc {
  id: string
  title?: string
  updated_at?: string
  scope?: 'shared' | 'personal' | 'project'
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

interface LandingPageProps {
  onSelect: (docId: string) => void
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

function DocCard({
  doc,
  onSelect,
  compact = false,
}: {
  doc: LandingDoc
  onSelect: (id: string) => void
  compact?: boolean
}) {
  return (
    <button
      onClick={() => onSelect(doc.id)}
      className={
        'group text-left rounded-lg border border-gray-200 dark:border-gray-800 ' +
        'bg-white dark:bg-gray-900 hover:border-gray-400 dark:hover:border-gray-600 ' +
        'hover:shadow-sm transition cursor-pointer ' +
        (compact ? 'p-3 w-56 shrink-0' : 'p-4')
      }
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <ScopeChip scope={doc.scope} />
        {doc.updated_at && (
          <span className="text-[11px] text-gray-500 dark:text-gray-400">
            {formatRelative(doc.updated_at)}
          </span>
        )}
      </div>
      <p className="font-medium text-gray-900 dark:text-gray-100 break-words leading-snug">
        {doc.title || doc.id}
      </p>
      {doc.title && doc.title !== doc.id && (
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 break-all">{doc.id}</p>
      )}
    </button>
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
}: {
  group: ProjectGroup
  onSelect: (id: string) => void
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
                <DocCard key={d.id} doc={d} onSelect={onSelect} />
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
                    <DocCard key={d.id} doc={d} onSelect={onSelect} compact />
                  ))}
                </div>
              </section>
            )}

            {personal.length > 0 && (
              <section>
                <SectionHeader>Personal</SectionHeader>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {personal.map((d) => (
                    <DocCard key={d.id} doc={d} onSelect={onSelect} />
                  ))}
                </div>
              </section>
            )}

            {shared.length > 0 && (
              <section>
                <SectionHeader>Shared</SectionHeader>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {shared.map((d) => (
                    <DocCard key={d.id} doc={d} onSelect={onSelect} />
                  ))}
                </div>
              </section>
            )}

            {projects.length > 0 && (
              <section>
                <SectionHeader>Projects</SectionHeader>
                {projects.map((p) => (
                  <ProjectGroupView key={p.slug} group={p} onSelect={onSelect} />
                ))}
              </section>
            )}
          </>
        )}
      </div>
    </div>
  )
}
