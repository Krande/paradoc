// Unit tests for the landing / Library data model: search ranking, the Recent
// merge and response normalisation. Run with `npm test`.
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  HISTORY_KEY,
  docKey,
  forgetDoc,
  formatSize,
  fromLandingResponse,
  fromLibraryResponse,
  mergeRecents,
  prettyTitle,
  rankDocs,
  readHistory,
  recordOpen,
  sortDocs,
} from '../src/components/library/libraryModel.ts'

const HOUR = 3600_000
const NOW = Date.parse('2026-06-01T12:00:00Z')

function iso(msAgo: number): string {
  return new Date(NOW - msAgo).toISOString()
}

const data = fromLibraryResponse({
  is_admin: false,
  scopes: [
    { ref: 'user:me', kind: 'personal', name: 'Personal', can_delete: true },
    { ref: 'shared', kind: 'shared', name: 'Shared', can_delete: false },
    { ref: 'project:quay', kind: 'project', name: 'Quay Wall Upgrade', can_delete: true },
  ],
  docs: [
    { id: 'load-case-summary', scope: 'shared', scope_ref: 'shared', published_at: iso(26 * HOUR), git: { branch: 'main', short_commit: 'abc1234' } },
    { id: 'quay-foundation-loads', scope: 'project', scope_ref: 'project:quay', published_at: iso(70 * 24 * HOUR) },
    { id: 'beam-strength-check', scope: 'project', scope_ref: 'project:quay', published_at: iso(2 * HOUR) },
    { id: 'draft-notes', scope: 'personal', scope_ref: 'user:me', published_at: iso(1 * HOUR), git: { branch: 'feat/quays' } },
    { id: 'fatigue-assessment-report', scope: 'shared', scope_ref: 'shared', published_at: iso(40 * 24 * HOUR), size: 2048 },
    { id: 'no-timestamp', scope_ref: 'shared' },
  ],
})

function ids(hits: { doc: { id: string } }[]): string[] {
  return hits.map((h) => h.doc.id)
}

class MemStorage {
  map = new Map<string, string>()
  getItem(k: string) {
    return this.map.has(k) ? (this.map.get(k) as string) : null
  }
  setItem(k: string, v: string) {
    this.map.set(k, v)
  }
}

describe('normalisation', () => {
  it('maps library entries with scope names, delete flags and git info', () => {
    assert.equal(data.docs.length, 6)
    const d = data.docs.find((x) => x.id === 'load-case-summary')!
    assert.equal(d.title, 'Load case summary')
    assert.equal(d.scopeKind, 'shared')
    assert.equal(d.scopeName, 'Shared')
    assert.equal(d.branch, 'main')
    assert.equal(d.commit, 'abc1234')
    assert.equal(data.docs.find((x) => x.id === 'beam-strength-check')!.scopeName, 'Quay Wall Upgrade')
    assert.deepEqual(
      data.scopes.map((s) => [s.ref, s.canDelete]),
      [
        ['user:me', true],
        ['shared', false],
        ['project:quay', true],
      ],
    )
  })

  it('falls back from an /api/landing response', () => {
    const lib = fromLandingResponse(
      {
        personal: [{ id: 'mine', scope: 'personal' }],
        shared: [{ id: 'ours', scope: 'shared' }],
        projects: [{ slug: 'p1', name: 'Project One', docs: [{ id: 'theirs', scope: 'project' }] }],
      },
      true,
      (ref) => ref !== 'shared',
    )
    assert.deepEqual(
      lib.docs.map((d) => [d.id, d.scopeRef, d.scopeName]),
      [
        ['mine', 'user:me', 'Personal'],
        ['ours', 'shared', 'Shared'],
        ['theirs', 'project:p1', 'Project One'],
      ],
    )
    assert.deepEqual(
      lib.scopes.map((s) => [s.ref, s.canDelete]),
      [
        ['user:me', true],
        ['shared', false],
        ['project:p1', true],
      ],
    )
    // No personal docs -> no personal scope (older servers can't tell us it exists).
    assert.equal(fromLandingResponse({ shared: [] }, false, () => false).scopes.length, 1)
  })

  it('prettifies ids', () => {
    assert.equal(prettyTitle('load-case_summary'), 'Load case summary')
    assert.equal(prettyTitle('LazyDoc'), 'LazyDoc')
    assert.equal(prettyTitle('a-b').length, 'a-b'.length)
  })
})

describe('rankDocs', () => {
  it('returns nothing for an empty query', () => {
    assert.deepEqual(rankDocs('   ', data.docs), [])
  })

  it('ranks title prefix over word prefix over scope match', () => {
    // "quay-foundation-loads" starts with "quay"; the other Quay Wall docs only match by scope name;
    // "draft-notes" matches via its branch.
    assert.deepEqual(ids(rankDocs('quay', data.docs)), [
      'quay-foundation-loads',
      'beam-strength-check',
      'draft-notes',
    ])
  })

  it('prefers word-start over substring and breaks ties by recency', () => {
    // "loads" (word start in quay-foundation-loads) vs "load" prefix of load-case-summary.
    assert.deepEqual(ids(rankDocs('load', data.docs)).slice(0, 2), ['load-case-summary', 'quay-foundation-loads'])
    // Two scope-only matches tie on score: the newer one comes first.
    const hits = rankDocs('wall', data.docs)
    assert.deepEqual(ids(hits), ['beam-strength-check', 'quay-foundation-loads'])
  })

  it('requires every term to match and highlights title ranges', () => {
    assert.deepEqual(ids(rankDocs('case summary', data.docs)), ['load-case-summary'])
    assert.deepEqual(ids(rankDocs('case nothing', data.docs)), [])
    const [hit] = rankDocs('case sum', data.docs)
    assert.deepEqual(hit.titleRanges, [
      [5, 9],
      [10, 13],
    ])
    assert.equal(hit.doc.title.slice(5, 9), 'case')
  })

  it('treats separators in the query like spaces and matches fuzzy subsequences last', () => {
    assert.deepEqual(ids(rankDocs('load-case', data.docs)), ['load-case-summary'])
    assert.deepEqual(ids(rankDocs('ftg', data.docs)), ['fatigue-assessment-report'])
  })
})

describe('recents', () => {
  it('records opens newest-first, dedupes and survives bad storage', () => {
    const s = new MemStorage()
    recordOpen(s, 'a', 'shared', 1)
    recordOpen(s, 'b', 'user:me', 2)
    recordOpen(s, 'a', 'shared', 3)
    assert.deepEqual(
      readHistory(s).map((e) => [e.id, e.scope, e.openedAt]),
      [
        ['a', 'shared', 3],
        ['b', 'user:me', 2],
      ],
    )
    forgetDoc(s, 'a', 'shared')
    assert.deepEqual(readHistory(s).map((e) => e.id), ['b'])
    s.setItem(HISTORY_KEY, '{not json')
    assert.deepEqual(readHistory(s), [])
    assert.deepEqual(readHistory(undefined), [])
  })

  it('merges local opens with server publish times', () => {
    const history = [
      // Opened 30 min ago: newer than its publish time -> first, reason "opened".
      { id: 'fatigue-assessment-report', scope: 'shared', openedAt: NOW - HOUR / 2 },
      // Opened long ago, but published 2h ago -> placed by publish time, reason "updated".
      { id: 'beam-strength-check', scope: 'project:quay', openedAt: NOW - 100 * HOUR },
      // A doc that is no longer accessible drops out.
      { id: 'deleted-doc', scope: 'shared', openedAt: NOW },
      // Same id in another scope does not count for this one.
      { id: 'load-case-summary', scope: 'user:me', openedAt: NOW },
    ]
    const rec = mergeRecents(data.docs, history, 4)
    assert.deepEqual(
      rec.map((r) => [r.doc.id, r.reason]),
      [
        ['fatigue-assessment-report', 'opened'],
        ['draft-notes', 'updated'],
        ['beam-strength-check', 'updated'],
        ['load-case-summary', 'updated'],
      ],
    )
    // Docs with neither an open nor a timestamp never show.
    assert.ok(!mergeRecents(data.docs, [], 100).some((r) => r.doc.id === 'no-timestamp'))
  })
})

describe('sort + format', () => {
  it('sorts by name or by update time', () => {
    assert.equal(sortDocs(data.docs, 'name')[0].id, 'beam-strength-check')
    assert.equal(sortDocs(data.docs, 'updated')[0].id, 'draft-notes')
    assert.equal(sortDocs(data.docs, 'updated').at(-1)!.id, 'no-timestamp')
  })

  it('formats sizes', () => {
    assert.equal(formatSize(undefined), '')
    assert.equal(formatSize(512), '512 B')
    assert.equal(formatSize(2048), '2.0 KB')
    assert.equal(formatSize(12_800_000), '12 MB')
  })

  it('keys docs by scope and id', () => {
    assert.equal(docKey({ id: 'x', scopeRef: 'project:p' }), 'project:p/x')
  })
})
