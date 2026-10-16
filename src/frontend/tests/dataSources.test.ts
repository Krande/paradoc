// Unit tests for the lazy plot / table sources. Run with `npm test`.
import assert from 'node:assert/strict'
import { beforeEach, describe, it } from 'node:test'

import {
  bulkPlotSource,
  clearDataSources,
  fetchSectionRun,
  findPlot,
  findTable,
  getTable,
  hasPlotSource,
  loadPlot,
  registerPlotSource,
  registerTables,
  resolveKey,
} from '../src/sections/dataSources.ts'

beforeEach(() => clearDataSources())

describe('resolveKey', () => {
  const keys = new Set(['plot_a', 'plot_b_2'])
  const has = (k: string) => keys.has(k)
  it('prefers the exact key', () => {
    assert.equal(resolveKey('plot_a', has), 'plot_a')
    assert.equal(resolveKey('plot_b_2', has), 'plot_b_2')
  })
  it('drops a numeric suffix for a reused plot', () => {
    assert.equal(resolveKey('plot_a_1', has), 'plot_a')
    assert.equal(resolveKey('plot_a_12', has), 'plot_a')
  })
  it('does not strip non-numeric suffixes or invent keys', () => {
    assert.equal(resolveKey('plot_a_x', has), undefined)
    assert.equal(resolveKey('other', has), undefined)
  })
})

describe('plot sources', () => {
  it('knows which figures have data without fetching any', async () => {
    let fetched = 0
    registerPlotSource('doc', { p1: { file: '_plots/p1.json' } }, async () => {
      fetched += 1
      return { key: 'p1' }
    })
    assert.equal(hasPlotSource('doc'), true)
    assert.equal(hasPlotSource('other'), false)
    assert.equal(findPlot('doc', 'p1'), 'p1')
    assert.equal(findPlot('doc', 'p1_3'), 'p1')
    assert.equal(findPlot('doc', 'p2'), undefined)
    assert.equal(fetched, 0)
  })

  it('fetches a plot once, on first request, and passes its index entry', async () => {
    const calls: Array<[string, string | undefined]> = []
    registerPlotSource('doc', { p1: { file: '_plots/p1.json', caption: 'c' } }, async (key, entry) => {
      calls.push([key, entry.file])
      await new Promise((r) => setTimeout(r, 5))
      return { key, figure: { data: [] } }
    })
    const [a, b] = await Promise.all([loadPlot('doc', 'p1'), loadPlot('doc', 'p1_2')])
    assert.deepEqual(a, b)
    assert.deepEqual(await loadPlot('doc', 'p1'), a)
    assert.deepEqual(calls, [['p1', '_plots/p1.json']])
    assert.equal(await loadPlot('doc', 'missing'), undefined)
  })

  it('retries a plot whose fetch failed', async () => {
    let n = 0
    registerPlotSource('doc', { p1: {} }, async () => {
      n += 1
      if (n === 1) throw new Error('offline')
      return { key: 'p1' }
    })
    await assert.rejects(loadPlot('doc', 'p1'))
    assert.deepEqual(await loadPlot('doc', 'p1'), { key: 'p1' })
  })

  it('serves a legacy bulk plots.json from memory', async () => {
    const spec = bulkPlotSource({ p1: { key: 'p1', caption: 'one', width: 640, height: 480, plot_type: 'line' } })
    assert.deepEqual(spec.index.p1, { caption: 'one', width: 640, height: 480, plot_type: 'line' })
    registerPlotSource('doc', spec.index, spec.fetch)
    assert.equal((await loadPlot('doc', 'p1'))?.caption, 'one')
  })
})

describe('table sources', () => {
  it('resolves tables from memory', () => {
    registerTables('doc', { t1: { key: 't1' } })
    assert.equal(findTable('doc', 't1_1'), 't1')
    assert.deepEqual(getTable('doc', 't1'), { key: 't1' })
    assert.equal(getTable('doc', 't2'), undefined)
    assert.equal(findTable('nodoc', 't1'), undefined)
  })
})

describe('fetchSectionRun', () => {
  it('keeps order and stops at the first missing section', async () => {
    const delays = [30, 5, 15, 1]
    const out = await fetchSectionRun(4, async (i) => {
      await new Promise((r) => setTimeout(r, delays[i]))
      return i === 2 ? undefined : `s${i}`
    })
    assert.deepEqual(out, ['s0', 's1'])
  })
  it('treats a failed fetch as the end of the run', async () => {
    const out = await fetchSectionRun(3, async (i) => {
      if (i === 1) throw new Error('boom')
      return i
    })
    assert.deepEqual(out, [0])
  })
})
