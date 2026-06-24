import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, onMounted } from 'vue'

// BriefingWidgetEmbed fetches the (data-less) widget shell on mount, then either
// merges a generation-time snapshot (no SQL) or — for pre-rollout briefings —
// falls back to a live refresh. @loaded must always fire so the PDF wait clears.

vi.stubGlobal('ref', ref)
vi.stubGlobal('onMounted', onMounted)

const mockFetch = vi.fn()
vi.stubGlobal('useApi', () => ({ fetchWithRefresh: mockFetch }))

const mockRefresh = vi.fn()
vi.stubGlobal('useWidgetData', () => ({ refresh: mockRefresh }))

import BriefingWidgetEmbed from '~/components/briefings/BriefingWidgetEmbed.vue'

// onMounted awaits a dynamic import('~/utils/widgetMerge'); a couple flushes
// aren't enough to settle it. Tick microtasks until emitted('loaded') fires.
async function settle(wrapper: any) {
  for (let i = 0; i < 10 && !wrapper.emitted('loaded'); i++) {
    await flushPromises()
    await new Promise((r) => setTimeout(r))
  }
}

const shell = () => ({
  id: 'w1',
  widget: { type: 'bar', config: { type: 'bar' } },
  dataSource: { connectionId: 1, sql: 'select 1', mapping: {} },
})

const mountEmbed = (props: Record<string, any>) =>
  mount(BriefingWidgetEmbed, {
    props: { widgetId: 'w1', dashboardId: 10, ...props },
    global: { stubs: { DashboardWidget: true } },
  })

describe('BriefingWidgetEmbed', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    mockRefresh.mockReset()
  })

  it('merges the snapshot and skips the live refresh when a snapshot is present', async () => {
    mockFetch.mockResolvedValue(shell())
    const wrapper = mountEmbed({ snapshot: { series: [1, 2, 3] } })
    await settle(wrapper)

    expect(mockRefresh).not.toHaveBeenCalled()
    expect((wrapper.vm as any).widget.widget.config.series).toEqual([1, 2, 3])
    expect(wrapper.emitted('loaded')).toHaveLength(1)
  })

  it('falls back to a live refresh when no snapshot is given', async () => {
    mockFetch.mockResolvedValue(shell())
    const wrapper = mountEmbed({})
    await settle(wrapper)

    expect(mockRefresh).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('loaded')).toHaveLength(1)
  })

  it('still emits loaded when the widget fetch fails (deleted widget)', async () => {
    mockFetch.mockRejectedValue(new Error('404'))
    const wrapper = mountEmbed({ snapshot: { series: [1] } })
    await settle(wrapper)

    expect(mockRefresh).not.toHaveBeenCalled()
    expect((wrapper.vm as any).widget).toBeNull()
    expect(wrapper.emitted('loaded')).toHaveLength(1)
  })
})
