// Unit tests for the reader's progressive-mount helpers. Run with `npm test`.
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { collectIds, estimatePages, mountTarget } from '../src/components/progressiveMount.ts'

const str = (s: string) => ({ t: 'Str', c: s })
const attr = (id: string) => [id, [], []]

describe('mountTarget', () => {
  it('keeps the count when the next section is out of reach', () => {
    assert.equal(mountTarget(3, [120]), 3)
    assert.equal(mountTarget(3, []), 3)
  })
  it('mounts every section that starts inside the covered area, in order', () => {
    assert.equal(mountTarget(1, [-500, -20, 10]), 3)
    assert.equal(mountTarget(0, [-1]), 1)
  })
})

describe('estimatePages', () => {
  it('is at least one page', () => {
    assert.equal(estimatePages([]), 1)
    assert.equal(estimatePages([{ t: 'Para', c: [str('short')] }]), 1)
  })
  it('grows with figures, tables and text', () => {
    const fig = { t: 'Figure', c: [attr('fig:a'), [null, []], []] }
    const many = Array.from({ length: 10 }, () => fig)
    assert.ok(estimatePages(many) >= 4)
    const rows = Array.from({ length: 200 }, () => [attr(''), []])
    const table = { t: 'Table', c: [attr('tbl:x'), [null, []], [], [attr(''), []], [[attr(''), 0, [], rows]], [attr(''), []]] }
    assert.ok(estimatePages([table]) >= 5)
    const long = { t: 'Para', c: Array.from({ length: 4000 }, () => str('word')) }
    assert.ok(estimatePages([long]) >= 5)
  })
})

describe('collectIds', () => {
  it('finds header, figure, table and span anchors at any depth', () => {
    const blocks = [
      { t: 'Header', c: [2, attr('sub-heading'), [str('Sub')]] },
      { t: 'Figure', c: [attr('fig:plot_a'), [null, []], [{ t: 'Plain', c: [{ t: 'Image', c: [attr(''), [], ['a.png', '']] }] }]] },
      { t: 'Div', c: [attr('tbl:results'), [{ t: 'Table', c: [attr(''), [null, []], [], [attr(''), []], [], [attr(''), []]] }]] },
      { t: 'Para', c: [{ t: 'Span', c: [attr('eq:energy'), [str('E')]] }] },
    ]
    const ids = collectIds(blocks)
    for (const id of ['sub-heading', 'fig:plot_a', 'tbl:results', 'eq:energy']) assert.ok(ids.has(id), id)
    assert.ok(!ids.has(''))
  })
})
