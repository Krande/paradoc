import React from 'react'
import { Modal } from '../Modal'
import type { LibraryDoc, ScopeKind } from './libraryModel'

// Small building blocks shared by the landing page, the Library view and the
// app shell: icons, scope markers, title highlighting, popovers and the
// delete confirmation.

type IconProps = { className?: string }

const stroke = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
}

export const Icon = {
  Search: ({ className = 'w-4 h-4' }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className} {...stroke}>
      <circle cx="11" cy="11" r="6.5" />
      <path d="M20 20l-4.2-4.2" />
    </svg>
  ),
  Library: ({ className = 'w-4 h-4' }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className} {...stroke}>
      <path d="M4 4.5h3v15H4zM9 4.5h3v15H9z" />
      <path d="M14.2 5.4l2.9-.8 3.9 14.5-2.9.8z" />
    </svg>
  ),
  Doc: ({ className = 'w-4 h-4' }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className} {...stroke}>
      <path d="M6.5 3h7.5l4.5 4.5V20a1 1 0 01-1 1h-11a1 1 0 01-1-1V4a1 1 0 011-1z" />
      <path d="M13.5 3v5h5M9 12.5h6M9 16h6" />
    </svg>
  ),
  Grid: ({ className = 'w-4 h-4' }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className} {...stroke}>
      <rect x="4" y="4" width="6.5" height="6.5" rx="1" />
      <rect x="13.5" y="4" width="6.5" height="6.5" rx="1" />
      <rect x="4" y="13.5" width="6.5" height="6.5" rx="1" />
      <rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1" />
    </svg>
  ),
  List: ({ className = 'w-4 h-4' }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className} {...stroke}>
      <path d="M8.5 6.5H20M8.5 12H20M8.5 17.5H20M4 6.5h.01M4 12h.01M4 17.5h.01" />
    </svg>
  ),
  Dots: ({ className = 'w-4 h-4' }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
      <circle cx="5.5" cy="12" r="1.6" />
      <circle cx="12" cy="12" r="1.6" />
      <circle cx="18.5" cy="12" r="1.6" />
    </svg>
  ),
  ArrowRight: ({ className = 'w-4 h-4' }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className} {...stroke}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  ),
  Close: ({ className = 'w-4 h-4' }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className} {...stroke}>
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  ),
  ChevronDown: ({ className = 'w-4 h-4' }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className} {...stroke}>
      <path d="M6.5 9.5L12 15l5.5-5.5" />
    </svg>
  ),
  Trash: ({ className = 'w-4 h-4' }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className} {...stroke}>
      <path d="M4.5 6.5h15M9.5 6.5V4.5h5v2M6.5 6.5l.8 13a1 1 0 001 .9h7.4a1 1 0 001-.9l.8-13M10 10.5v6M14 10.5v6" />
    </svg>
  ),
  Link: ({ className = 'w-4 h-4' }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className} {...stroke}>
      <path d="M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1" />
      <path d="M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1" />
    </svg>
  ),
  Open: ({ className = 'w-4 h-4' }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className} {...stroke}>
      <path d="M13.5 4.5H19.5V10.5M19.5 4.5l-8 8M17 14v4.5a1 1 0 01-1 1H5.5a1 1 0 01-1-1V8a1 1 0 011-1H10" />
    </svg>
  ),
}

const SCOPE_DOT: Record<ScopeKind, string> = {
  personal: 'bg-violet-500 dark:bg-violet-400',
  shared: 'bg-sky-500 dark:bg-sky-400',
  project: 'bg-emerald-500 dark:bg-emerald-400',
}

export function ScopeDot({ kind, className = '' }: { kind: ScopeKind; className?: string }) {
  return <span aria-hidden="true" className={`inline-block w-2 h-2 rounded-full shrink-0 ${SCOPE_DOT[kind]} ${className}`} />
}

/** Scope marker: coloured dot + scope name. */
export function ScopeLabel({ doc, className = '' }: { doc: Pick<LibraryDoc, 'scopeKind' | 'scopeName'>; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 min-w-0 ${className}`}>
      <ScopeDot kind={doc.scopeKind} />
      <span className="truncate">{doc.scopeName}</span>
    </span>
  )
}

/** Git provenance in mono: `branch@sha`, with an amber dot when built from a dirty tree. */
export function GitRef({ doc }: { doc: LibraryDoc }) {
  if (!doc.branch && !doc.commit) return null
  return (
    <span className="inline-flex items-center gap-1 font-mono min-w-0">
      {doc.dirty && (
        <span title="Built from a dirty working tree" className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
      )}
      <span className="truncate">
        {doc.branch || ''}
        {doc.branch && doc.commit ? '@' : ''}
        {doc.commit || ''}
      </span>
    </span>
  )
}

/** `text` with the given [start, end) ranges marked. */
export function Highlight({ text, ranges }: { text: string; ranges: [number, number][] }) {
  if (!ranges.length) return <>{text}</>
  const parts: React.ReactNode[] = []
  let at = 0
  ranges.forEach(([s, e], i) => {
    if (s > at) parts.push(text.slice(at, s))
    parts.push(
      <mark key={i} className="bg-transparent text-inherit underline decoration-2 underline-offset-2 decoration-sky-500/70">
        {text.slice(s, e)}
      </mark>,
    )
    at = e
  })
  if (at < text.length) parts.push(text.slice(at))
  return <>{parts}</>
}

/** Close a popover on outside pointer-down and on Escape. */
export function useDismiss(open: boolean, ref: React.RefObject<HTMLElement | null>, close: () => void) {
  React.useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close()
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close()
    }
    document.addEventListener('pointerdown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, ref, close])
}

/** Arrow-key movement between `[role=menuitem]` / `[role=menuitemradio]` / `[role=menuitemcheckbox]` in a menu. */
export function onMenuKeyDown(e: React.KeyboardEvent<HTMLElement>) {
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) return
  const items = Array.from(
    e.currentTarget.querySelectorAll<HTMLElement>('[role=menuitem],[role=menuitemradio],[role=menuitemcheckbox]'),
  ).filter((el) => !el.hasAttribute('disabled'))
  if (!items.length) return
  e.preventDefault()
  const i = items.indexOf(document.activeElement as HTMLElement)
  let next = 0
  if (e.key === 'ArrowDown') next = i < 0 ? 0 : (i + 1) % items.length
  else if (e.key === 'ArrowUp') next = i <= 0 ? items.length - 1 : i - 1
  else if (e.key === 'End') next = items.length - 1
  items[next].focus()
}

export const menuPanel =
  'absolute right-0 top-full mt-1.5 z-30 min-w-48 rounded-lg border border-gray-200 dark:border-gray-800 ' +
  'bg-white dark:bg-gray-900 shadow-lg shadow-gray-900/5 dark:shadow-black/40 py-1 text-sm text-gray-800 dark:text-gray-100'

export const menuItem =
  'w-full flex items-center gap-2.5 px-3 py-2 text-left cursor-pointer no-underline text-gray-800 dark:text-gray-100 ' +
  'hover:bg-gray-100 dark:hover:bg-gray-800 focus-visible:bg-gray-100 dark:focus-visible:bg-gray-800 focus:outline-none'

/** Link to a doc in the reader, for "Copy link". */
export function docLink(doc: LibraryDoc): string {
  const url = new URL(window.location.href)
  url.search = ''
  url.hash = ''
  url.searchParams.set('doc', doc.id)
  if (doc.scopeRef !== 'shared') url.searchParams.set('scope', doc.scopeRef)
  return url.toString()
}

/**
 * The per-doc "…" menu: Open, Copy link, and Delete (only where the user may
 * delete; it asks for confirmation first).
 */
export function DocActions({
  doc,
  canDelete,
  onOpen,
  onDelete,
}: {
  doc: LibraryDoc
  canDelete: boolean
  onOpen: () => void
  onDelete: (doc: LibraryDoc) => Promise<void>
}) {
  const [open, setOpen] = React.useState(false)
  const [confirming, setConfirming] = React.useState(false)
  const [copied, setCopied] = React.useState(false)
  const ref = React.useRef<HTMLDivElement>(null)
  const close = React.useCallback(() => setOpen(false), [])
  useDismiss(open, ref, close)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(docLink(doc))
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {}
    setOpen(false)
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          setOpen((o) => !o)
        }}
        aria-label={`Actions for ${doc.title}`}
        aria-haspopup="menu"
        aria-expanded={open}
        title={copied ? 'Link copied' : 'Actions'}
        className={
          'cursor-pointer inline-flex items-center justify-center w-8 h-8 rounded-md text-gray-400 ' +
          'hover:text-gray-800 hover:bg-gray-100 dark:hover:text-gray-100 dark:hover:bg-gray-800 ' +
          (open ? 'text-gray-800 bg-gray-100 dark:text-gray-100 dark:bg-gray-800' : '')
        }
      >
        <Icon.Dots />
      </button>
      {open && (
        <div role="menu" aria-label={`Actions for ${doc.title}`} className={menuPanel} onKeyDown={onMenuKeyDown}>
          <button role="menuitem" type="button" className={menuItem} onClick={() => (setOpen(false), onOpen())}>
            <Icon.Open className="w-4 h-4 text-gray-400" /> Open
          </button>
          <button role="menuitem" type="button" className={menuItem} onClick={copy}>
            <Icon.Link className="w-4 h-4 text-gray-400" /> Copy link
          </button>
          {canDelete && (
            <>
              <div className="my-1 border-t border-gray-100 dark:border-gray-800" />
              <button
                role="menuitem"
                type="button"
                className={menuItem.replace('text-gray-800 dark:text-gray-100', 'text-red-600 dark:text-red-400')}
                onClick={() => {
                  setOpen(false)
                  setConfirming(true)
                }}
              >
                <Icon.Trash className="w-4 h-4" /> Delete…
              </button>
            </>
          )}
        </div>
      )}
      {confirming && <ConfirmDelete doc={doc} onClose={() => setConfirming(false)} onDelete={onDelete} />}
    </div>
  )
}

function ConfirmDelete({
  doc,
  onClose,
  onDelete,
}: {
  doc: LibraryDoc
  onClose: () => void
  onDelete: (doc: LibraryDoc) => Promise<void>
}) {
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const where = doc.scopeRef === 'user:me' ? 'your personal scope' : doc.scopeRef === 'shared' ? 'the shared scope (for everyone)' : `${doc.scopeName} (for every member)`
  const run = async () => {
    setBusy(true)
    setError(null)
    try {
      await onDelete(doc)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'delete failed')
      setBusy(false)
    }
  }
  return (
    <Modal open title="Delete document?" onClose={busy ? () => {} : onClose}>
      <div onClick={(e) => e.stopPropagation()}>
        <p>
          <span className="font-medium text-gray-900 dark:text-gray-100">{doc.title}</span> will be removed from {where}.
          The published bundle is deleted and this cannot be undone.
        </p>
        {error && <p className="mt-3 text-red-600 dark:text-red-400">Could not delete: {error}</p>}
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="cursor-pointer px-3 py-1.5 rounded-md text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={run}
            disabled={busy}
            autoFocus
            className="cursor-pointer px-3 py-1.5 rounded-md text-sm font-medium bg-red-600 text-white hover:bg-red-700 disabled:opacity-60"
          >
            {busy ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>
    </Modal>
  )
}
