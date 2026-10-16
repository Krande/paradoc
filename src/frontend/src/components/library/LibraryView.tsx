import React from 'react'
import { useLibrary } from './useLibrary'
import {
  docKey,
  formatRelative,
  formatSize,
  rankDocs,
  sortDocs,
  type LibraryDoc,
  type LibraryScope,
  type SortKey,
} from './libraryModel'
import { DocActions, GitRef, Highlight, Icon, ScopeDot } from './ui'

// Library: every doc the user can read, by scope (Personal, Shared, each
// Project), with a filter field, sort (updated / name) and a grid / list
// toggle. View state lives in the URL (`?view=library&in=<scope>&sort=name&
// layout=list&q=...`) so it survives reloads and the back button; the layout
// choice is also remembered per browser.

type SelectDoc = (docId: string, scope?: string) => void
type Layout = 'grid' | 'list'

const LAYOUT_KEY = 'paradoc-library-layout'

function readParams() {
  const p = new URLSearchParams(window.location.search)
  let storedLayout: string | null = null
  try {
    storedLayout = localStorage.getItem(LAYOUT_KEY)
  } catch {}
  const layout = (p.get('layout') || storedLayout) === 'list' ? 'list' : 'grid'
  return {
    scope: p.get('in') || 'all',
    sort: (p.get('sort') === 'name' ? 'name' : 'updated') as SortKey,
    layout: layout as Layout,
    q: p.get('q') || '',
  }
}

function writeParams(next: { scope: string; sort: SortKey; layout: Layout; q: string }) {
  try {
    const url = new URL(window.location.href)
    const set = (k: string, v: string, dflt: string) => (v && v !== dflt ? url.searchParams.set(k, v) : url.searchParams.delete(k))
    set('in', next.scope, 'all')
    set('sort', next.sort, 'updated')
    set('layout', next.layout, 'grid')
    set('q', next.q, '')
    window.history.replaceState(window.history.state, '', url.toString())
  } catch {}
}

export function LibraryView({ onSelect }: { onSelect: SelectDoc }) {
  const { data, loading, error, ensure, remove } = useLibrary()
  const [state, setState] = React.useState(readParams)
  const { scope, sort, layout, q } = state

  React.useEffect(() => ensure({ sizes: true }), [ensure])
  React.useEffect(() => writeParams(state), [state])
  const update = (patch: Partial<typeof state>) => setState((s) => ({ ...s, ...patch }))
  const setLayout = (l: Layout) => {
    update({ layout: l })
    try {
      localStorage.setItem(LAYOUT_KEY, l)
    } catch {}
  }

  const scopes = data?.scopes || []
  const docs = React.useMemo(() => data?.docs || [], [data])
  const counts = React.useMemo(() => {
    const m = new Map<string, number>()
    for (const d of docs) m.set(d.scopeRef, (m.get(d.scopeRef) || 0) + 1)
    return m
  }, [docs])
  const canDelete = (ref: string) => scopes.find((s) => s.ref === ref)?.canDelete || false

  const selectedScope = scope === 'all' ? null : scopes.find((s) => s.ref === scope) || null
  const inScope = selectedScope ? docs.filter((d) => d.scopeRef === selectedScope.ref) : docs
  const filtered = q.trim()
    ? rankDocs(q, inScope)
    : sortDocs(inScope, sort).map((doc) => ({ doc, score: 0, titleRanges: [] as [number, number][] }))
  const ranges = new Map(filtered.map((h) => [docKey(h.doc), h.titleRanges]))
  const visible = q.trim() ? sortDocs(filtered.map((h) => h.doc), sort) : filtered.map((h) => h.doc)

  // "All" groups by scope, in the server's scope order; a single scope is one flat group.
  const groups: { scope: LibraryScope; docs: LibraryDoc[] }[] = selectedScope
    ? [{ scope: selectedScope, docs: visible }].filter((g) => g.docs.length > 0)
    : scopes.map((s) => ({ scope: s, docs: visible.filter((d) => d.scopeRef === s.ref) })).filter((g) => g.docs.length > 0)

  const open = (d: LibraryDoc) => onSelect(d.id, d.scopeRef)

  return (
    <div className="flex-1 overflow-auto overscroll-contain bg-gray-50 dark:bg-gray-950" data-testid="library">
      <div className="mx-auto w-full max-w-6xl px-4 sm:px-6 lg:px-8 py-5 sm:py-8">
        <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-3">
          <div>
            <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">Library</h1>
            <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
              {data ? `${docs.length} document${docs.length === 1 ? '' : 's'} you can open` : 'Every document you can open'}
            </p>
          </div>
          <div className="flex flex-wrap sm:flex-nowrap items-center gap-2 w-full sm:w-auto">
            <div className="flex items-center gap-2 basis-full sm:basis-auto sm:w-64 h-9 rounded-md border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-2.5 focus-within:border-gray-400 dark:focus-within:border-gray-600">
              <Icon.Search className="w-4 h-4 text-gray-400 shrink-0" />
              <input
                type="search"
                value={q}
                onChange={(e) => update({ q: e.target.value })}
                placeholder="Filter"
                aria-label="Filter documents"
                className="flex-1 min-w-0 bg-transparent text-[15px] sm:text-sm outline-none text-gray-900 dark:text-gray-100 placeholder:text-gray-400"
              />
            </div>
            <label className="sr-only" htmlFor="library-sort">
              Sort
            </label>
            <select
              id="library-sort"
              value={sort}
              onChange={(e) => update({ sort: e.target.value as SortKey })}
              className="cursor-pointer flex-1 sm:flex-none h-9 rounded-md border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 pl-2.5 pr-7 text-sm text-gray-700 dark:text-gray-200"
            >
              <option value="updated">Last updated</option>
              <option value="name">Name</option>
            </select>
            <div role="radiogroup" aria-label="Layout" className="inline-flex h-9 rounded-md border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-0.5">
              {(['grid', 'list'] as Layout[]).map((l) => (
                <button
                  key={l}
                  type="button"
                  role="radio"
                  aria-checked={layout === l}
                  aria-label={l === 'grid' ? 'Grid' : 'List'}
                  title={l === 'grid' ? 'Grid' : 'List'}
                  onClick={() => setLayout(l)}
                  className={
                    'cursor-pointer inline-flex items-center justify-center w-8 rounded transition ' +
                    (layout === l
                      ? 'bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900'
                      : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100')
                  }
                >
                  {l === 'grid' ? <Icon.Grid /> : <Icon.List />}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-5 sm:mt-7 md:flex md:gap-8">
          <ScopeNav scopes={scopes} counts={counts} total={docs.length} value={scope} onChange={(s) => update({ scope: s })} />

          <div className="flex-1 min-w-0 mt-4 md:mt-0">
            {loading && !data ? (
              <Skeleton layout={layout} />
            ) : error ? (
              <div className="rounded-xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/30 px-4 py-3">
                <p className="text-sm font-medium text-red-700 dark:text-red-300">Could not load documents</p>
                <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
              </div>
            ) : groups.length === 0 ? (
              <LibraryEmpty scope={selectedScope} filtered={!!q.trim()} onClear={() => update({ q: '' })} />
            ) : (
              groups.map((g) => (
                <section key={g.scope.ref} className="mb-8 last:mb-0" data-testid={`library-group-${g.scope.ref}`}>
                  {!selectedScope && (
                    <h2 className="flex items-center gap-2 mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-gray-500 dark:text-gray-400">
                      <ScopeDot kind={g.scope.kind} />
                      {g.scope.name}
                      <span className="font-normal tabular-nums text-gray-400 dark:text-gray-500">{g.docs.length}</span>
                    </h2>
                  )}
                  {layout === 'grid' ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                      {g.docs.map((d) => (
                        <DocCard
                          key={docKey(d)}
                          doc={d}
                          ranges={ranges.get(docKey(d)) || []}
                          canDelete={canDelete(d.scopeRef)}
                          onOpen={() => open(d)}
                          onDelete={remove}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 divide-y divide-gray-100 dark:divide-gray-800">
                      {g.docs.map((d) => (
                        <DocRow
                          key={docKey(d)}
                          doc={d}
                          ranges={ranges.get(docKey(d)) || []}
                          canDelete={canDelete(d.scopeRef)}
                          onOpen={() => open(d)}
                          onDelete={remove}
                        />
                      ))}
                    </div>
                  )}
                </section>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function ScopeNav({
  scopes,
  counts,
  total,
  value,
  onChange,
}: {
  scopes: LibraryScope[]
  counts: Map<string, number>
  total: number
  value: string
  onChange: (ref: string) => void
}) {
  const personalShared = scopes.filter((s) => s.kind !== 'project')
  const projects = scopes.filter((s) => s.kind === 'project')
  const item = (ref: string, label: React.ReactNode, n: number, kind?: LibraryScope['kind']) => {
    const active = value === ref
    return (
      <button
        key={ref}
        type="button"
        onClick={() => onChange(ref)}
        aria-pressed={active}
        className={
          'cursor-pointer shrink-0 inline-flex items-center gap-2 rounded-full md:rounded-md px-3 py-1.5 text-sm transition md:w-full ' +
          'border md:border-0 ' +
          (active
            ? 'bg-gray-900 text-white border-gray-900 dark:bg-gray-100 dark:text-gray-900 dark:border-gray-100 md:bg-gray-200/70 md:text-gray-900 md:dark:bg-gray-800 md:dark:text-gray-100 md:font-medium'
            : 'border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 md:bg-transparent md:dark:bg-transparent text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white md:hover:bg-gray-100 md:dark:hover:bg-gray-900')
        }
      >
        {kind && <ScopeDot kind={kind} />}
        <span className="truncate md:flex-1 md:text-left">{label}</span>
        <span className={'tabular-nums text-xs ' + (active ? 'opacity-70' : 'text-gray-400 dark:text-gray-500')}>{n}</span>
      </button>
    )
  }
  return (
    <nav aria-label="Scopes" className="md:w-56 md:shrink-0">
      <div className="-mx-4 px-4 md:mx-0 md:px-0 flex md:flex-col gap-1.5 md:gap-0.5 overflow-x-auto pb-1 md:pb-0 [scrollbar-width:none] md:sticky md:top-4">
        {item('all', 'All documents', total)}
        {personalShared.map((s) => item(s.ref, s.name, counts.get(s.ref) || 0, s.kind))}
        {projects.length > 0 && (
          <div className="hidden md:block mt-4 mb-1 px-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-gray-400 dark:text-gray-500">
            Projects
          </div>
        )}
        {projects.map((s) => item(s.ref, s.name, counts.get(s.ref) || 0, s.kind))}
      </div>
    </nav>
  )
}

function Meta({ doc }: { doc: LibraryDoc }) {
  const parts: React.ReactNode[] = []
  if (doc.updatedMs)
    parts.push(
      <span key="t" className="whitespace-nowrap" title={doc.publishedAt}>
        {formatRelative(doc.updatedMs)}
      </span>,
    )
  if (doc.size !== undefined) parts.push(<span key="s" className="whitespace-nowrap">{formatSize(doc.size)}</span>)
  if (doc.branch || doc.commit) parts.push(<GitRef key="g" doc={doc} />)
  return (
    <span className="flex items-center gap-1.5 min-w-0 text-xs text-gray-500 dark:text-gray-400 tabular-nums">
      {parts.map((p, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span className="text-gray-300 dark:text-gray-700">·</span>}
          {p}
        </React.Fragment>
      ))}
    </span>
  )
}

interface DocItemProps {
  doc: LibraryDoc
  ranges: [number, number][]
  canDelete: boolean
  onOpen: () => void
  onDelete: (doc: LibraryDoc) => Promise<void>
}

function DocCard({ doc, ranges, canDelete, onOpen, onDelete }: DocItemProps) {
  return (
    <div
      className="group relative flex flex-col rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 hover:border-gray-300 dark:hover:border-gray-700 hover:shadow-sm transition"
      data-testid="library-doc"
    >
      <button type="button" onClick={onOpen} className="cursor-pointer text-left flex-1 p-3.5 sm:p-4 pr-12 sm:pr-12 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 rounded-xl">
        <span className="block text-[15px] font-medium leading-snug text-gray-900 dark:text-gray-100 break-words">
          <Highlight text={doc.title} ranges={ranges} />
        </span>
        {doc.title !== doc.id && <span className="mt-0.5 block text-xs font-mono text-gray-400 dark:text-gray-500 truncate">{doc.id}</span>}
        <span className="mt-3 sm:mt-4 block">
          <Meta doc={doc} />
        </span>
      </button>
      <div className="absolute top-2.5 right-2.5">
        <DocActions doc={doc} canDelete={canDelete} onOpen={onOpen} onDelete={onDelete} />
      </div>
    </div>
  )
}

function DocRow({ doc, ranges, canDelete, onOpen, onDelete }: DocItemProps) {
  return (
    <div className="flex items-center gap-2 pr-2 hover:bg-gray-50 dark:hover:bg-gray-800/40 first:rounded-t-xl last:rounded-b-xl" data-testid="library-doc">
      <button type="button" onClick={onOpen} className="cursor-pointer flex-1 min-w-0 text-left px-4 py-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 rounded-xl">
        <span className="flex items-center gap-3 min-w-0">
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium text-gray-900 dark:text-gray-100">
              <Highlight text={doc.title} ranges={ranges} />
            </span>
            <span className="mt-0.5 flex sm:hidden items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 min-w-0">
              <ScopeDot kind={doc.scopeKind} />
              <span className="truncate max-w-[40%]">{doc.scopeName}</span>
              {doc.updatedMs && (
                <>
                  <span className="text-gray-300 dark:text-gray-700">·</span>
                  <span className="whitespace-nowrap">{formatRelative(doc.updatedMs)}</span>
                </>
              )}
              {doc.size !== undefined && (
                <>
                  <span className="text-gray-300 dark:text-gray-700">·</span>
                  <span className="whitespace-nowrap">{formatSize(doc.size)}</span>
                </>
              )}
            </span>
            <span className="hidden sm:block mt-0.5 text-xs font-mono text-gray-400 dark:text-gray-500 truncate">
              {doc.title !== doc.id ? doc.id : ''}
              {doc.branch || doc.commit ? (doc.title !== doc.id ? '  ·  ' : '') + `${doc.branch || ''}${doc.branch && doc.commit ? '@' : ''}${doc.commit || ''}` : ''}
            </span>
          </span>
          <span className="hidden sm:inline-flex items-center gap-1.5 w-44 text-xs text-gray-500 dark:text-gray-400 min-w-0">
            <ScopeDot kind={doc.scopeKind} />
            <span className="truncate">{doc.scopeName}</span>
          </span>
          <span className="hidden sm:block w-20 text-right text-xs text-gray-500 dark:text-gray-400 tabular-nums" title={doc.publishedAt}>
            {formatRelative(doc.updatedMs)}
          </span>
          <span className="hidden sm:block w-16 text-right text-xs text-gray-500 dark:text-gray-400 tabular-nums">{formatSize(doc.size)}</span>
        </span>
      </button>
      <DocActions doc={doc} canDelete={canDelete} onOpen={onOpen} onDelete={onDelete} />
    </div>
  )
}

function LibraryEmpty({ scope, filtered, onClear }: { scope: LibraryScope | null; filtered: boolean; onClear: () => void }) {
  return (
    <div className="rounded-xl border border-dashed border-gray-300 dark:border-gray-700 px-6 py-12 text-center">
      <span className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-400">
        {filtered ? <Icon.Search className="w-5 h-5" /> : <Icon.Doc className="w-5 h-5" />}
      </span>
      {filtered ? (
        <>
          <p className="mt-3 text-sm text-gray-700 dark:text-gray-300">No documents match the filter{scope ? ` in ${scope.name}` : ''}.</p>
          <button type="button" onClick={onClear} className="cursor-pointer mt-1 text-sm text-sky-700 dark:text-sky-400 hover:underline">
            Clear filter
          </button>
        </>
      ) : (
        <>
          <p className="mt-3 text-sm text-gray-700 dark:text-gray-300">{scope ? `Nothing in ${scope.name} yet.` : 'Nothing published yet.'}</p>
          <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
            Publish with{' '}
            <code className="font-mono rounded bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5">
              paradoc publish &lt;doc_dir&gt;{scope ? ` --scope ${scope.ref}` : ''}
            </code>
          </p>
        </>
      )}
    </div>
  )
}

function Skeleton({ layout }: { layout: Layout }) {
  const n = layout === 'grid' ? 6 : 5
  return (
    <div className={layout === 'grid' ? 'grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3' : 'space-y-2'}>
      {Array.from({ length: n }, (_, i) => (
        <div key={i} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
          <div className="h-2.5 w-1/4 rounded bg-gray-100 dark:bg-gray-800 animate-pulse" />
          <div className="mt-3 h-3.5 w-2/3 rounded bg-gray-100 dark:bg-gray-800 animate-pulse" />
          {layout === 'grid' && <div className="mt-5 h-2.5 w-1/2 rounded bg-gray-100 dark:bg-gray-800 animate-pulse" />}
        </div>
      ))}
    </div>
  )
}
