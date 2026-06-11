import { describe, it, expect } from 'vitest'
import { hasRenderableData } from '~/utils/widgetRender'
import type { DashboardWidget } from '~/types/dashboard'

function makeWidget(type: string, config: Record<string, any>): DashboardWidget {
  return {
    id: 'w1',
    layout: { x: 0, y: 0, w: 4, h: 4 },
    widget: { type, config } as any,
  } as DashboardWidget
}

describe('hasRenderableData', () => {
  it('kpi with a value is renderable', () => {
    expect(hasRenderableData(makeWidget('kpi', { value: 42, label: 'Total' }))).toBe(true)
    expect(hasRenderableData(makeWidget('kpi', { value: 0, label: 'Total' }))).toBe(true)
    expect(hasRenderableData(makeWidget('kpi', { value: 'N/A', label: 'Total' }))).toBe(true)
  })

  it('kpi without a value is not renderable', () => {
    expect(hasRenderableData(makeWidget('kpi', { label: 'Total' }))).toBe(false)
    expect(hasRenderableData(makeWidget('kpi', { value: null, label: 'Total' }))).toBe(false)
    expect(hasRenderableData(makeWidget('kpi', { value: '', label: 'Total' }))).toBe(false)
  })

  it('chart with datasets is renderable', () => {
    expect(
      hasRenderableData(makeWidget('chart', { type: 'bar', data: { labels: ['a'], datasets: [{ data: [1] }] } })),
    ).toBe(true)
  })

  it('chart without datasets is not renderable', () => {
    expect(hasRenderableData(makeWidget('chart', { type: 'bar', data: { labels: [], datasets: [] } }))).toBe(false)
    expect(hasRenderableData(makeWidget('chart', { type: 'bar' }))).toBe(false)
  })

  it('table / pivot_table with rows are renderable, without rows are not', () => {
    expect(hasRenderableData(makeWidget('table', { columns: [], rows: [{ a: 1 }] }))).toBe(true)
    expect(hasRenderableData(makeWidget('table', { columns: [], rows: [] }))).toBe(false)
    expect(hasRenderableData(makeWidget('pivot_table', { rows: [{ a: 1 }] }))).toBe(true)
    expect(hasRenderableData(makeWidget('pivot_table', {}))).toBe(false)
  })

  it('text and filter widgets are always renderable (never skeletoned)', () => {
    expect(hasRenderableData(makeWidget('text', { content: '' }))).toBe(true)
    expect(hasRenderableData(makeWidget('filter', { controls: [] }))).toBe(true)
  })
})
