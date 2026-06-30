import { describe, it, expect } from 'vitest'
import { mergeRefreshedConfig } from '~/utils/widgetMerge'
import type { DashboardWidget } from '~/types/dashboard'

function w(type: string, config: Record<string, any>): DashboardWidget {
  return { id: 'x', position: { x: 0, y: 0, w: 3, h: 2 }, widget: { type, config } } as any
}

describe('mergeRefreshedConfig — data-only merge', () => {
  it('table: keeps saved column order/rename/width, updates rows only', () => {
    const widget = w('table', {
      title: 'My edited title',
      // user reordered (b before a), renamed a, set a width
      columns: [
        { key: 'b', label: 'B' },
        { key: 'a', label: 'Renamed A', width: 240 },
      ],
      rows: [{ a: 1, b: 2 }],
    })
    // backend regenerated config: original order, original label, no width, new rows
    const refreshed = {
      columns: [
        { key: 'a', label: 'A' },
        { key: 'b', label: 'B' },
      ],
      rows: [{ a: 9, b: 8 }],
    }
    const out = mergeRefreshedConfig(widget, refreshed)
    expect(out.columns.map((c: any) => c.key)).toEqual(['b', 'a']) // saved order
    expect(out.columns.find((c: any) => c.key === 'a').label).toBe('Renamed A')
    expect(out.columns.find((c: any) => c.key === 'a').width).toBe(240)
    expect(out.rows).toEqual([{ a: 9, b: 8 }]) // data refreshed
    expect('title' in out).toBe(false) // title untouched (Object.assign preserves it)
  })

  it('table: appends new columns and drops removed ones (real schema change)', () => {
    const widget = w('table', { columns: [{ key: 'a', label: 'A' }, { key: 'gone', label: 'Gone' }], rows: [] })
    const refreshed = { columns: [{ key: 'a', label: 'A' }, { key: 'new', label: 'New' }], rows: [] }
    const out = mergeRefreshedConfig(widget, refreshed)
    expect(out.columns.map((c: any) => c.key)).toEqual(['a', 'new'])
  })

  it('chart: keeps dataset order/style, updates data values', () => {
    const widget = w('chart', {
      type: 'bar',
      title: 'Edited',
      data: {
        labels: ['Jan'],
        datasets: [
          { label: 'Revenue', data: [1], borderColor: '#f00', seriesType: 'line' },
        ],
      },
    })
    const refreshed = {
      data: { labels: ['Jan', 'Feb'], datasets: [{ label: 'Revenue', data: [10, 20] }] },
    }
    const out = mergeRefreshedConfig(widget, refreshed)
    expect(out.data.labels).toEqual(['Jan', 'Feb'])
    expect(out.data.datasets[0].data).toEqual([10, 20]) // refreshed values
    expect(out.data.datasets[0].borderColor).toBe('#f00') // saved style kept
    expect(out.data.datasets[0].seriesType).toBe('line')
    expect('type' in out).toBe(false) // chart type untouched
  })

  it('kpi: updates value, preserves label/format', () => {
    const widget = w('kpi', { value: 1, label: 'My label', prefix: '$', format: 'currency' })
    const out = mergeRefreshedConfig(widget, { value: 999, label: 'regenerated' })
    expect(out.value).toBe(999)
    expect('label' in out).toBe(false) // label untouched → user's label survives
  })

  it('pivot_table: pass-through (structural keys not emitted survive via Object.assign)', () => {
    const widget = w('pivot_table', { rows: [], columnWidths: { rowHeader: 200 } })
    const refreshed = { rows: [{ x: 1 }], columns: [{ key: 'x', label: 'X' }] }
    const out = mergeRefreshedConfig(widget, refreshed)
    expect(out).toBe(refreshed) // unchanged pass-through; columnWidths preserved by Object.assign
  })
})
