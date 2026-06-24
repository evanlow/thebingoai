import { describe, it, expect, vi } from 'vitest'
import { ref } from 'vue'

// useWidgetData is called by BriefingWidgetEmbed with ref(null) before the
// widget loads async onMounted. These tests lock in null-safety so the
// briefing view doesn't crash (regression: null.dataSource at setup).

const mockRefreshWidget = vi.fn().mockResolvedValue({ config: {}, refreshed_at: 'now' })
vi.mock('~/composables/useApi', () => ({
  useApi: () => ({
    fetchWithRefresh: vi.fn(),
    dashboards: { refreshWidget: mockRefreshWidget },
  }),
}))
vi.mock('~/stores/dashboard', () => ({
  useDashboardStore: () => ({
    refreshingWidgets: {},
    widgetSeq: {},
    activeFilters: [],
    bulkWidgetLoading: false,
    currentDashboardId: null,
  }),
}))
vi.mock('~/utils/widgetMerge', () => ({
  mergeRefreshedConfig: (a: any) => a,
}))

import { useWidgetData } from '~/composables/useWidgetData'

describe('useWidgetData null-safety', () => {
  it('does not throw when widget.value is null', () => {
    const widget = ref<any>(null)
    expect(() => useWidgetData(widget)).not.toThrow()
  })

  it('computeds return falsy/null for a null widget', () => {
    const widget = ref<any>(null)
    const { hasDataSource, lastRefreshedAt, servedFrom } = useWidgetData(widget)
    expect(hasDataSource.value).toBe(false)
    expect(lastRefreshedAt.value).toBeNull()
    expect(servedFrom.value).toBeNull()
  })

  it('refresh() is a no-op when widget has no dataSource', async () => {
    const widget = ref<any>(null)
    const { refresh } = useWidgetData(widget)
    await expect(refresh()).resolves.toBeUndefined()
  })

  it('reflects dataSource once the widget loads', () => {
    const widget = ref<any>(null)
    const { hasDataSource, servedFrom } = useWidgetData(widget)
    widget.value = { id: 'w1', dataSource: { servedFrom: 'data_plane' } }
    expect(hasDataSource.value).toBe(true)
    expect(servedFrom.value).toBe('data_plane')
  })

  it('auto-refreshes on the immediate watcher when the widget already has a dataSource', async () => {
    mockRefreshWidget.mockClear()
    const widget = ref<any>({ id: 'w1', dataSource: { connectionId: 1, sql: 'select 1', mapping: {} }, widget: { config: {} } })
    useWidgetData(widget) // autoRefresh defaults true
    await Promise.resolve()
    expect(mockRefreshWidget).toHaveBeenCalledTimes(1)
  })

  it('does NOT auto-refresh when autoRefresh is false (briefing snapshot path)', async () => {
    mockRefreshWidget.mockClear()
    const widget = ref<any>({ id: 'w1', dataSource: { connectionId: 1, sql: 'select 1', mapping: {} }, widget: { config: {} } })
    useWidgetData(widget, false)
    await Promise.resolve()
    expect(mockRefreshWidget).not.toHaveBeenCalled()
  })
})
