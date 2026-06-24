import { describe, it, expect, vi } from 'vitest'

// useWidgetData imports these statically, so mock the modules (not globals).
// Only the setup path is exercised here; refresh() (which uses the api) is not
// triggered because the widget ref starts null → hasDataSource is false.
vi.mock('~/composables/useApi', () => ({
  useApi: () => ({ dashboards: { refreshWidget: vi.fn() } }),
}))
vi.mock('~/stores/dashboard', () => ({
  useDashboardStore: () => ({
    activeFilters: [],
    refreshingWidgets: {},
    bulkWidgetLoading: false,
    widgetSeq: {},
    currentDashboardId: null,
    setWidgetSourceData: vi.fn(),
  }),
}))

import { useWidgetData } from '~/composables/useWidgetData'
import { ref } from 'vue'

// Regression: BriefingWidgetEmbed passes a `ref(null)` widget that only resolves
// after an async onMounted fetch. The `immediate: true` watcher evaluates the
// `hasDataSource` computed at setup, which dereferenced `widget.value.dataSource`
// and threw `Cannot read properties of null`, crashing the whole briefing page.
describe('useWidgetData — null widget guard', () => {
  it('does not throw at setup when the widget ref is null', () => {
    const widget = ref<any>(null)
    expect(() => useWidgetData(widget)).not.toThrow()
  })

  it('computeds return safe defaults while the widget is null', () => {
    const widget = ref<any>(null)
    const { hasDataSource, lastRefreshedAt, servedFrom, loading } = useWidgetData(widget)
    expect(hasDataSource.value).toBe(false)
    expect(lastRefreshedAt.value).toBe(null)
    expect(servedFrom.value).toBe(null)
    expect(loading.value).toBe(false)
  })

  it('reflects the widget once the async fetch resolves it', () => {
    const widget = ref<any>(null)
    const { hasDataSource, servedFrom, lastRefreshedAt } = useWidgetData(widget)
    widget.value = {
      id: 7,
      dataSource: { servedFrom: 'data_plane', lastRefreshedAt: '2026-06-23T00:00:00Z' },
    }
    expect(hasDataSource.value).toBe(true)
    expect(servedFrom.value).toBe('data_plane')
    expect(lastRefreshedAt.value).toBe('2026-06-23T00:00:00Z')
  })
})
