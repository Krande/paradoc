import React from 'react'
import { useLibrary } from './library/useLibrary'
import { docKey, formatRelative, prettyTitle, rankDocs, sortDocs, type LibraryDoc } from './library/libraryModel'
import { Highlight, Icon, ScopeDot, useDismiss } from './library/ui'

// The reader breadcrumb's document title. Clicking it opens a small switcher:
// a filter field over every doc the user can read (the open doc's scope
// first), arrow keys + Enter to open, and a way into the Library. Outside
// REST mode there is nothing to switch to, so it renders the plain title.

export function DocSwitcher({
  docId,
  scopeRef,
  enabled,
  onSelect,
  onOpenLibrary,
}: {
  docId: string
  scopeRef: string
  enabled: boolean
  onSelect: (docId: string, scope?: string) => void
  onOpenLibrary: () => void
}) {
  const { data, ensure } = useLibrary()
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState('')
  const [active, setActive] = React.useState(0)
  const ref = React.useRef<HTMLDivElement>(null)
  const close = React.useCallback(() => setOpen(false), [])
  useDismiss(open, ref, close)

  React.useEffect(() => {
    if (enabled) ensure()
  }, [enabled, ensure])
  React.useEffect(() => {
    if (open) {
      setQuery('')
      setActive(0)
    }
  }, [open])

  const title = prettyTitle(docId)
  if (!enabled) {
    return <span className="truncate text-sm font-medium text-gray-900 dark:text-gray-100" title={docId}>{title}</span>
  }

  const docs = data?.docs || []
  const items: { doc: LibraryDoc; ranges: [number, number][] }[] = query.trim()
    ? rankDocs(query, docs).map((h) => ({ doc: h.doc, ranges: h.titleRanges }))
    : [
        ...sortDocs(docs.filter((d) => d.scopeRef === scopeRef), 'updated'),
        ...sortDocs(docs.filter((d) => d.scopeRef !== scopeRef), 'updated'),
      ].map((doc) => ({ doc, ranges: [] }))
  const shown = items.slice(0, 50)

  const pick = (d: LibraryDoc) => {
    setOpen(false)
    onSelect(d.id, d.scopeRef)
  }
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => Math.min(shown.length - 1, i + 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => Math.max(0, i - 1))
    } else if (e.key === 'Enter' && shown[active]) {
      e.preventDefault()
      pick(shown[active].doc)
    }
  }

  return (
    <div className="relative min-w-0" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="dialog"
        aria-expanded={open}
        title={`${docId} (switch document)`}
        data-testid="doc-switcher"
        className="cursor-pointer max-w-full inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-sm font-medium text-gray-900 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800"
      >
        <span className="truncate">{title}</span>
        <Icon.ChevronDown className="w-3.5 h-3.5 shrink-0 text-gray-400" />
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Switch document"
          className="fixed sm:absolute left-2 right-2 sm:left-0 sm:right-auto top-14 sm:top-full sm:mt-2 z-40 sm:w-96 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-xl shadow-gray-900/10 dark:shadow-black/50 overflow-hidden"
        >
          <div className="flex items-center gap-2 px-3 h-11 border-b border-gray-100 dark:border-gray-800">
            <Icon.Search className="w-4 h-4 text-gray-400 shrink-0" />
            <input
              autoFocus
              type="search"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setActive(0)
              }}
              onKeyDown={onKeyDown}
              placeholder="Switch to…"
              aria-label="Find a document"
              className="flex-1 min-w-0 bg-transparent text-[15px] sm:text-sm outline-none text-gray-900 dark:text-gray-100 placeholder:text-gray-400"
            />
          </div>
          <ul role="listbox" aria-label="Documents" className="max-h-[min(60vh,24rem)] overflow-y-auto py-1">
            {shown.length === 0 && <li className="px-3 py-3 text-sm text-gray-500 dark:text-gray-400">{data ? 'No matches' : 'Loading…'}</li>}
            {shown.map(({ doc, ranges }, i) => {
              const current = doc.id === docId && doc.scopeRef === scopeRef
              return (
                <li key={docKey(doc)} role="option" aria-selected={i === active}>
                  <button
                    type="button"
                    onClick={() => pick(doc)}
                    onMouseMove={() => setActive(i)}
                    className={
                      'cursor-pointer w-full text-left flex items-center gap-2.5 px-3 py-2 ' +
                      (i === active ? 'bg-gray-100 dark:bg-gray-800' : '')
                    }
                  >
                    <ScopeDot kind={doc.scopeKind} />
                    <span className="min-w-0 flex-1">
                      <span className={'block truncate text-sm ' + (current ? 'font-semibold' : '') + ' text-gray-900 dark:text-gray-100'}>
                        <Highlight text={doc.title} ranges={ranges} />
                      </span>
                      <span className="block truncate text-xs text-gray-500 dark:text-gray-400">{doc.scopeName}</span>
                    </span>
                    <span className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap tabular-nums">
                      {current ? 'open' : formatRelative(doc.updatedMs)}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              onOpenLibrary()
            }}
            className="cursor-pointer w-full flex items-center gap-2 px-3 py-2.5 border-t border-gray-100 dark:border-gray-800 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800/60"
          >
            <Icon.Library className="w-4 h-4 text-gray-400" />
            Browse the library
          </button>
        </div>
      )}
    </div>
  )
}
