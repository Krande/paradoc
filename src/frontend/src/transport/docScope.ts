// Doc scope routing for REST mode.
//
// paradoc-serve stores bundles per scope: `shared` (the legacy
// unscoped `/api/docs/{id}/...` routes), `user:me` (the signed-in
// user's personal scope) and `project:<slug>`. Non-shared docs are
// only reachable through `/api/scopes/{scope}/docs/{id}/...`.
//
// The SPA identifies the open doc by id everywhere (transport calls,
// IndexedDB keys, component props), so instead of threading a scope
// argument through every call site we keep a small id → scope registry
// here. App.tsx records the scope when a doc is selected / resolved
// from the URL, and every REST URL for a doc is built through
// `docApiPath`, which consults the registry.

export const SHARED_SCOPE = 'shared'
export const PERSONAL_SCOPE = 'user:me'

/** Normalise a scope value: empty / missing / `shared` → undefined. */
export function normalizeScope(scope?: string | null): string | undefined {
  const s = (scope || '').trim()
  if (!s || s === SHARED_SCOPE) return undefined
  return s
}

const _docScopes = new Map<string, string>()

/** Record which scope a doc id lives in. Shared (or empty) clears it. */
export function setDocScope(docId: string, scope?: string | null): void {
  if (!docId) return
  const s = normalizeScope(scope)
  if (s) _docScopes.set(docId, s)
  else _docScopes.delete(docId)
}

/** Scope registered for a doc id, or undefined for shared. */
export function getDocScope(docId: string): string | undefined {
  return _docScopes.get(docId)
}

/** Test helper: forget every registered scope. */
export function clearDocScopes(): void {
  _docScopes.clear()
}

/**
 * API path for a doc resource. `suffix` is appended verbatim (it should
 * start with `/` and already be encoded), e.g. `/manifest` or
 * `/3d/<key>/blob`. Uses the scope registered for `docId` unless an
 * explicit `scope` is passed.
 */
export function docApiPath(docId: string, suffix = '', scope?: string | null): string {
  const s = scope === undefined ? getDocScope(docId) : normalizeScope(scope)
  const id = encodeURIComponent(docId)
  if (s) return `/api/scopes/${encodeURIComponent(s)}/docs/${id}${suffix}`
  return `/api/docs/${id}${suffix}`
}

/** True for a path produced by `docApiPath` (scoped or not). */
export function isDocApiPath(url: string): boolean {
  return url.includes('/api/docs/') || url.includes('/api/scopes/')
}

export interface DocSelection {
  docId: string
  scope?: string
}

/**
 * Read `?doc=<id>&scope=<scope>` (or the `#doc=...&scope=...` hash
 * form) from a location. Returns undefined when no doc is selected.
 */
export function readDocSelection(loc: { search: string; hash: string }): DocSelection | undefined {
  const params = new URLSearchParams(loc.search)
  let docId = params.get('doc') || ''
  let scope = params.get('scope') || undefined
  if (!docId) {
    const hashParams = new URLSearchParams(loc.hash.replace(/^#/, ''))
    docId = hashParams.get('doc') || ''
    scope = hashParams.get('scope') || undefined
  }
  if (!docId) return undefined
  return { docId, scope: normalizeScope(scope) }
}

/**
 * Write a doc selection into `url` (mutated and returned). Shared docs
 * omit `scope` so their links stay identical to the pre-scope format;
 * an empty `docId` clears both params (back to the landing page).
 */
export function writeDocSelection(url: URL, docId: string, scope?: string | null): URL {
  const s = normalizeScope(scope)
  if (docId) url.searchParams.set('doc', docId)
  else url.searchParams.delete('doc')
  if (docId && s) url.searchParams.set('scope', s)
  else url.searchParams.delete('scope')
  return url
}

/**
 * URL-form scope for a `/api/landing` entry. Prefers the server's
 * `scope_ref`; otherwise derives it from the coarse `scope` label
 * (`personal` → `user:me`, `project` → `project:<slug>` when the slug
 * of the enclosing project group is known).
 */
export function landingScopeRef(
  doc: { scope?: string; scope_ref?: string },
  projectSlug?: string,
): string | undefined {
  if (doc.scope_ref) return normalizeScope(doc.scope_ref)
  if (doc.scope === 'personal') return PERSONAL_SCOPE
  if (doc.scope === 'project' && projectSlug) return `project:${projectSlug}`
  return undefined
}

/**
 * Whether a signed-in user may delete a doc in `scopeRef` -- only decides if the UI offers it; the
 * server enforces the same rule: the owner deletes personal docs, project members project docs, and
 * only admins shared ones.
 */
export function canDeleteInScope(scopeRef: string | undefined, isAdmin: boolean): boolean {
  const scope = normalizeScope(scopeRef) // undefined = shared
  if (!scope) return isAdmin
  return scope === PERSONAL_SCOPE || scope.startsWith('project:')
}
