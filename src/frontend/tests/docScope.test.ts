// Unit tests for the doc-scope URL helpers. Run with `npm test`
// (Node's built-in test runner; Node >= 22.6 strips the TS types).
import assert from 'node:assert/strict'
import { beforeEach, describe, it } from 'node:test'

import {
  clearDocScopes,
  docApiPath,
  getDocScope,
  isDocApiPath,
  landingScopeRef,
  normalizeScope,
  readDocSelection,
  setDocScope,
  writeDocSelection,
} from '../src/transport/docScope.ts'

beforeEach(() => clearDocScopes())

describe('normalizeScope', () => {
  it('maps empty and shared to undefined', () => {
    assert.equal(normalizeScope(undefined), undefined)
    assert.equal(normalizeScope(null), undefined)
    assert.equal(normalizeScope(''), undefined)
    assert.equal(normalizeScope('shared'), undefined)
    assert.equal(normalizeScope('user:me'), 'user:me')
    assert.equal(normalizeScope('project:demo'), 'project:demo')
  })
})

describe('docApiPath', () => {
  it('uses the legacy unscoped route for shared docs', () => {
    assert.equal(docApiPath('demo-doc', '/manifest'), '/api/docs/demo-doc/manifest')
    setDocScope('demo-doc', 'shared')
    assert.equal(docApiPath('demo-doc', '/manifest'), '/api/docs/demo-doc/manifest')
  })

  it('routes registered personal / project docs through /api/scopes', () => {
    setDocScope('demo-doc', 'user:me')
    assert.equal(
      docApiPath('demo-doc', '/sections/0'),
      '/api/scopes/user%3Ame/docs/demo-doc/sections/0',
    )
    setDocScope('other-doc', 'project:demo-project')
    assert.equal(
      docApiPath('other-doc', '/3d/fig/blob'),
      '/api/scopes/project%3Ademo-project/docs/other-doc/3d/fig/blob',
    )
    // Unregistered ids stay shared.
    assert.equal(docApiPath('third-doc', '/plots'), '/api/docs/third-doc/plots')
  })

  it('honours an explicit scope argument over the registry', () => {
    setDocScope('demo-doc', 'user:me')
    assert.equal(docApiPath('demo-doc', '/manifest', 'shared'), '/api/docs/demo-doc/manifest')
    assert.equal(
      docApiPath('plain-doc', '/manifest', 'user:me'),
      '/api/scopes/user%3Ame/docs/plain-doc/manifest',
    )
  })

  it('encodes the doc id', () => {
    assert.equal(docApiPath('a b/c'), '/api/docs/a%20b%2Fc')
  })

  it('setDocScope(shared) clears a registration', () => {
    setDocScope('demo-doc', 'user:me')
    setDocScope('demo-doc', undefined)
    assert.equal(getDocScope('demo-doc'), undefined)
  })

  it('isDocApiPath recognises both route families', () => {
    assert.ok(isDocApiPath('/api/docs/demo-doc/files/x.png'))
    assert.ok(isDocApiPath('https://reports.example.com/api/scopes/user%3Ame/docs/d/files/x.png'))
    assert.ok(!isDocApiPath('files/x.png'))
  })
})

describe('URL selection round-trip', () => {
  const roundTrip = (docId: string, scope?: string) => {
    const url = writeDocSelection(new URL('https://reports.example.com/?view=page'), docId, scope)
    return { url, sel: readDocSelection({ search: url.search, hash: url.hash }) }
  }

  it('omits scope for shared docs so old links stay identical', () => {
    const { url, sel } = roundTrip('demo-doc', 'shared')
    assert.equal(url.search, '?view=page&doc=demo-doc')
    assert.deepEqual(sel, { docId: 'demo-doc', scope: undefined })
  })

  it('carries personal and project scopes', () => {
    const personal = roundTrip('demo-doc', 'user:me')
    assert.equal(personal.url.searchParams.get('scope'), 'user:me')
    assert.deepEqual(personal.sel, { docId: 'demo-doc', scope: 'user:me' })

    const project = roundTrip('demo-doc', 'project:demo-project')
    assert.deepEqual(project.sel, { docId: 'demo-doc', scope: 'project:demo-project' })
  })

  it('empty doc id clears doc and scope (back to landing)', () => {
    const url = new URL('https://reports.example.com/?doc=demo-doc&scope=user:me')
    writeDocSelection(url, '')
    assert.equal(url.search, '')
    assert.equal(readDocSelection({ search: url.search, hash: url.hash }), undefined)
  })

  it('switching from a scoped doc to a shared one drops scope', () => {
    const url = new URL('https://reports.example.com/?doc=demo-doc&scope=user:me')
    writeDocSelection(url, 'shared-doc')
    assert.equal(url.searchParams.get('scope'), null)
  })

  it('reads legacy query and hash forms', () => {
    assert.deepEqual(readDocSelection({ search: '?doc=demo-doc', hash: '' }), {
      docId: 'demo-doc',
      scope: undefined,
    })
    assert.deepEqual(readDocSelection({ search: '', hash: '#doc=demo%20doc&scope=user:me' }), {
      docId: 'demo doc',
      scope: 'user:me',
    })
  })
})

describe('landingScopeRef', () => {
  it('prefers the server-provided scope_ref', () => {
    assert.equal(landingScopeRef({ scope: 'project', scope_ref: 'project:demo-project' }), 'project:demo-project')
    assert.equal(landingScopeRef({ scope: 'shared', scope_ref: 'shared' }), undefined)
  })

  it('derives from the coarse label on older servers', () => {
    assert.equal(landingScopeRef({ scope: 'personal' }), 'user:me')
    assert.equal(landingScopeRef({ scope: 'project' }, 'demo-project'), 'project:demo-project')
    assert.equal(landingScopeRef({ scope: 'shared' }), undefined)
    assert.equal(landingScopeRef({}), undefined)
  })
})
