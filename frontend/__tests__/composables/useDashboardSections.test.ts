import { describe, it, expect, vi } from 'vitest'
import { ref, computed, watch, nextTick } from 'vue'

// ── Stub Nuxt auto-imports ───────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', watch)
vi.stubGlobal('nextTick', nextTick)
// Lifecycle hooks are no-ops outside a component — DOM measurement isn't under test.
vi.stubGlobal('onMounted', () => {})
vi.stubGlobal('onBeforeUnmount', () => {})

import { useDashboardSections, sectionTitle } from '~/composables/useDashboardSections'
import { isSectionHeader } from '~/types/dashboard'
import type { DashboardWidget } from '~/types/dashboard'

function widget(id: string, y: number, type = 'chart', config: Record<string, any> = {}): DashboardWidget {
  return {
    id,
    position: { x: 0, y, w: 12, h: 3 },
    widget: { type, config } as any,
  }
}

const header = (id: string, y: number, config: Record<string, any>) => widget(id, y, 'text', config)

describe('sectionTitle', () => {
  it('strips heading markers and keeps first line', () => {
    expect(sectionTitle('## Tasks, Phasing, Cost & Milestones')).toBe('Tasks, Phasing, Cost & Milestones')
    expect(sectionTitle('# One\nbody text')).toBe('One')
    expect(sectionTitle('  ### Indented ')).toBe('Indented')
    expect(sectionTitle('')).toBe('')
  })
})

describe('isSectionHeader', () => {
  it('uses the heading heuristic when isSection is undefined', () => {
    expect(isSectionHeader(header('t', 0, { content: '## Trends' }))).toBe(true)
    expect(isSectionHeader(header('t', 0, { content: 'plain narrative' }))).toBe(false)
  })

  it('explicit flag wins over the heuristic', () => {
    expect(isSectionHeader(header('t', 0, { content: '## Trends', isSection: false }))).toBe(false)
    expect(isSectionHeader(header('t', 0, { content: 'no heading', isSection: true }))).toBe(true)
  })

  it('non-text widgets are never headers', () => {
    expect(isSectionHeader(widget('c', 0, 'chart', {}))).toBe(false)
  })
})

describe('useDashboardSections', () => {
  it('derives sections in reading order with default color', () => {
    const widgets = ref<DashboardWidget[]>([
      header('h2', 10, { content: '## Detail & Records' }),
      widget('kpi1', 0, 'kpi'),
      header('h1', 2, { content: '## Trends & Breakdown', sectionColor: 'violet', isSection: true }),
      widget('chart1', 3),
      widget('table1', 11, 'table'),
    ])
    const { sections } = useDashboardSections(widgets, ref(null))
    expect(sections.value).toEqual([
      { id: 'h1', title: 'Trends & Breakdown', color: 'violet' },
      { id: 'h2', title: 'Detail & Records', color: 'default' },
    ])
  })

  it('reacts to position changes (reorder) and content edits', async () => {
    const widgets = ref<DashboardWidget[]>([
      header('a', 0, { content: '## First' }),
      header('b', 5, { content: '## Second' }),
    ])
    const { sections } = useDashboardSections(widgets, ref(null))
    expect(sections.value.map(s => s.id)).toEqual(['a', 'b'])

    widgets.value[0].position.y = 9 // drag "First" below "Second"
    expect(sections.value.map(s => s.id)).toEqual(['b', 'a'])

    widgets.value[1].widget.config = { content: '## Renamed' }
    expect(sections.value.find(s => s.id === 'b')!.title).toBe('Renamed')
  })

  it('ignores narrative text widgets and dashboards without headers', () => {
    const widgets = ref<DashboardWidget[]>([
      widget('kpi1', 0, 'kpi'),
      header('note', 2, { content: 'just a note' }),
    ])
    const { sections } = useDashboardSections(widgets, ref(null))
    expect(sections.value).toEqual([])
  })
})
