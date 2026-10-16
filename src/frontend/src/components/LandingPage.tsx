import React from 'react'
import { useLibrary } from './library/useLibrary'
import {
  docKey,
  formatRelative,
  mergeRecents,
  rankDocs,
  readHistory,
  type LibraryDoc,
} from './library/libraryModel'
import { BrandMark } from './BrandMark'
import { GitRef, Highlight, Icon, ScopeLabel } from './library/ui'

// Landing page: one centred search field over the docs the user can read,
// "Recent" underneath, and the way into the Library.
//
// Recent = local open-history merged with server publish times (see
// mergeRecents). While the user types, ranked search results replace it;
// arrows move the highlight and Enter opens it (the top hit by default).
// Deleting lives in the Library view, not here.

type SelectDoc = (docId: string, scope?: string) => void

interface LandingPageProps {
  onSelect: SelectDoc
  onOpenLibrary: () => void
}

function readLocalHistory() {
  try {
    return readHistory(window.localStorage)
  } catch {
    return []
  }
}

interface Row {
  doc: LibraryDoc
  ranges: [number, number][]
  when: string
}

function ResultRow({
  row,
  active,
  index,
  onOpen,
  onHover,
}: {
  row: Row
  active: boolean
  index: number
  onOpen: () => void
  onHover: () => void
}) {
  const { doc } = row
  return (
    <li role="option" id={`landing-opt-${index}`} aria-selected={active}>
      <button
        type="button"
        tabIndex={-1}
        onClick={onOpen}
        onMouseMove={onHover}
        data-testid="landing-row"
        className={
          'w-full text-left flex items-center gap-3 px-3 sm:px-4 py-2.5 cursor-pointer transition-colors ' +
          (active ? 'bg-gray-100 dark:bg-gray-800/80' : 'hover:bg-gray-50 dark:hover:bg-gray-800/40')
        }
      >
        <span className="hidden sm:inline-flex items-center justify-center w-8 h-8 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 shrink-0">
          <Icon.Doc />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[15px] text-gray-900 dark:text-gray-100">
            <Highlight text={doc.title} ranges={row.ranges} />
          </span>
          <span className="mt-0.5 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 min-w-0">
            <ScopeLabel doc={doc} className="shrink-0 max-w-full sm:max-w-[60%]" />
            {(doc.branch || doc.commit) && (
              <span className="hidden sm:contents">
                <span className="text-gray-300 dark:text-gray-700">·</span>
                <GitRef doc={doc} />
              </span>
            )}
          </span>
        </span>
        <span className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap shrink-0 tabular-nums">{row.when}</span>
        <Icon.ArrowRight
          className={'hidden sm:block w-4 h-4 shrink-0 transition ' + (active ? 'text-gray-500 dark:text-gray-400' : 'text-transparent')}
        />
      </button>
    </li>
  )
}

export function LandingPage({ onSelect, onOpenLibrary }: LandingPageProps) {
  const { data, loading, error, ensure } = useLibrary()
  const [query, setQuery] = React.useState('')
  const [active, setActive] = React.useState(-1)
  const [history] = React.useState(readLocalHistory)
  const inputRef = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => ensure(), [ensure])

  // "/" focuses the search from anywhere on the page.
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      e.preventDefault()
      inputRef.current?.focus()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const docs = React.useMemo(() => data?.docs || [], [data])
  const searching = query.trim().length > 0
  const rows: Row[] = React.useMemo(() => {
    if (searching) {
      return rankDocs(query, docs)
        .slice(0, 12)
        .map((h) => ({ doc: h.doc, ranges: h.titleRanges, when: formatRelative(h.doc.updatedMs) }))
    }
    return mergeRecents(docs, history, 8).map((r) => ({
      doc: r.doc,
      ranges: [],
      when: (r.reason === 'opened' ? 'opened ' : '') + formatRelative(r.at),
    }))
  }, [searching, query, docs, history])

  // A query highlights its top hit, so Enter opens it.
  React.useEffect(() => setActive(searching ? 0 : -1), [query, searching])

  const open = (doc: LibraryDoc) => onSelect(doc.id, doc.scopeRef)

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (rows.length) setActive((i) => (i + 1) % rows.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (rows.length) setActive((i) => (i <= 0 ? rows.length - 1 : i - 1))
    } else if (e.key === 'Enter') {
      const row = rows[active]
      if (row) {
        e.preventDefault()
        open(row.doc)
      }
    } else if (e.key === 'Escape') {
      if (query) {
        e.preventDefault()
        setQuery('')
      } else inputRef.current?.blur()
    }
  }

  const total = docs.length
  const scopeCount = data?.scopes.length || 0

  return (
    <div className="flex-1 overflow-auto overscroll-contain bg-gray-50 dark:bg-gray-950" data-testid="landing">
      <div className="mx-auto w-full max-w-2xl px-4 sm:px-6 pt-[8vh] sm:pt-[13vh] pb-16">
        <div className="flex flex-col items-center text-center">
          <div className="inline-flex items-center gap-2.5 text-gray-900 dark:text-gray-100">
            <BrandMark className="w-6 h-6 sm:w-7 sm:h-7" />
            <h1 className="font-mono text-2xl sm:text-3xl font-medium uppercase tracking-[0.22em] text-gray-900 dark:text-gray-100">
              paradoc
            </h1>
          </div>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            {data && total > 0
              ? `${total} document${total === 1 ? '' : 's'} in progress across ${scopeCount} scope${scopeCount === 1 ? '' : 's'}`
              : 'Documents in progress'}
          </p>
        </div>

        <div className="mt-7 sm:mt-9">
          <label htmlFor="landing-search" className="sr-only">
            Search documents
          </label>
          <div
            className={
              'flex items-center gap-2.5 rounded-full border bg-white dark:bg-gray-900 px-4 sm:px-5 h-12 shadow-sm transition ' +
              'border-gray-200 dark:border-gray-800 focus-within:border-gray-400 dark:focus-within:border-gray-600 focus-within:shadow-md'
            }
          >
            <Icon.Search className="w-[18px] h-[18px] text-gray-400 dark:text-gray-500 shrink-0" />
            <input
              id="landing-search"
              ref={inputRef}
              type="search"
              autoComplete="off"
              spellCheck={false}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Search documents"
              role="combobox"
              aria-expanded={rows.length > 0}
              aria-controls="landing-list"
              aria-activedescendant={active >= 0 && rows[active] ? `landing-opt-${active}` : undefined}
              className="flex-1 min-w-0 bg-transparent text-[16px] text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 outline-none [&::-webkit-search-cancel-button]:hidden"
            />
            {query ? (
              <button
                type="button"
                onClick={() => {
                  setQuery('')
                  inputRef.current?.focus()
                }}
                aria-label="Clear search"
                className="cursor-pointer -mr-1 p-1 rounded-full text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
              >
                <Icon.Close />
              </button>
            ) : (
              <kbd className="hidden sm:inline-flex items-center justify-center h-6 min-w-6 px-1.5 rounded border border-gray-200 dark:border-gray-700 text-[11px] font-mono text-gray-400 dark:text-gray-500">
                /
              </kbd>
            )}
          </div>

          <div className="mt-4 flex justify-center">
            <button
              type="button"
              onClick={onOpenLibrary}
              data-testid="open-library"
              className={
                'cursor-pointer inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition ' +
                'text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-gray-800 bg-white/70 dark:bg-gray-900/70 ' +
                'hover:border-gray-400 dark:hover:border-gray-600 hover:text-gray-900 dark:hover:text-white'
              }
            >
              <Icon.Library />
              Library
              {total > 0 && <span className="text-gray-400 dark:text-gray-500 font-normal tabular-nums">{total}</span>}
            </button>
          </div>
        </div>

        <section className="mt-10 sm:mt-12" aria-live="polite">
          <div className="flex items-baseline justify-between px-1 mb-2">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-gray-500 dark:text-gray-400">
              {searching ? 'Results' : 'Recent'}
            </h2>
            {searching && rows.length > 0 && (
              <span className="hidden sm:inline text-xs text-gray-400 dark:text-gray-500">↑↓ to move · Enter to open</span>
            )}
          </div>

          {loading && !data ? (
            <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 divide-y divide-gray-100 dark:divide-gray-800">
              {[0, 1, 2].map((i) => (
                <div key={i} className="px-4 py-3.5">
                  <div className="h-3.5 w-1/2 rounded bg-gray-100 dark:bg-gray-800 animate-pulse" />
                  <div className="mt-2 h-2.5 w-1/4 rounded bg-gray-100 dark:bg-gray-800 animate-pulse" />
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="rounded-xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/30 px-4 py-3">
              <p className="text-sm font-medium text-red-700 dark:text-red-300">Could not load documents</p>
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            </div>
          ) : rows.length > 0 ? (
            <ul
              id="landing-list"
              role="listbox"
              aria-label={searching ? 'Search results' : 'Recent documents'}
              className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 divide-y divide-gray-100 dark:divide-gray-800 overflow-hidden"
            >
              {rows.map((row, i) => (
                <ResultRow
                  key={docKey(row.doc)}
                  row={row}
                  index={i}
                  active={i === active}
                  onOpen={() => open(row.doc)}
                  onHover={() => active !== i && setActive(i)}
                />
              ))}
            </ul>
          ) : (
            <EmptyState searching={searching} query={query} hasDocs={total > 0} onOpenLibrary={onOpenLibrary} />
          )}
        </section>
      </div>
    </div>
  )
}

function EmptyState({
  searching,
  query,
  hasDocs,
  onOpenLibrary,
}: {
  searching: boolean
  query: string
  hasDocs: boolean
  onOpenLibrary: () => void
}) {
  return (
    <div className="rounded-xl border border-dashed border-gray-300 dark:border-gray-700 px-5 py-8 text-center">
      {searching ? (
        <>
          <p className="text-sm text-gray-700 dark:text-gray-300">No documents match “{query.trim()}”.</p>
          <button
            type="button"
            onClick={onOpenLibrary}
            className="cursor-pointer mt-2 text-sm text-sky-700 dark:text-sky-400 hover:underline"
          >
            Browse the library instead
          </button>
        </>
      ) : hasDocs ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">Documents you open will show up here.</p>
      ) : (
        <>
          <p className="text-sm text-gray-700 dark:text-gray-300">Nothing published yet.</p>
          <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
            Publish a document with{' '}
            <code className="font-mono rounded bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5">paradoc publish &lt;doc_dir&gt;</code>{' '}
            and it appears here.
          </p>
        </>
      )}
    </div>
  )
}
