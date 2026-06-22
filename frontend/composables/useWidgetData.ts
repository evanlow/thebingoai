import { ref, computed, watch } from 'vue'
import type { Ref } from 'vue'
import type { DashboardWidget } from '~/types/dashboard'
import { useApi } from '~/composables/useApi'
import { useDashboardStore } from '~/stores/dashboard'
import { mergeRefreshedConfig } from '~/utils/widgetMerge'

export function useWidgetData(widget: Ref<DashboardWidget>) {
  const localLoading = ref(false)
  const error = ref<string | null>(null)
  const store = useDashboardStore()
  let refreshSeq = 0

  const hasDataSource = computed(() => !!widget.value.dataSource)
  const lastRefreshedAt = computed(() => widget.value.dataSource?.lastRefreshedAt ?? null)
  const servedFrom = computed(() => widget.value.dataSource?.servedFrom ?? null)
  // Also true while a bulk dashboard refresh covering this widget is in flight.
  const loading = computed(() => localLoading.value || !!store.refreshingWidgets[widget.value.id])

  async function refresh() {
    const ds = widget.value.dataSource
    if (!ds) return

    const seq = ++refreshSeq
    // Bump the store-level seq so an in-flight bulk refresh won't overwrite
    // this newer single-widget result.
    store.widgetSeq[widget.value.id] = (store.widgetSeq[widget.value.id] ?? 0) + 1
    localLoading.value = true
    error.value = null

    try {
      const api = useApi()
      const filters = store.activeFilters.length > 0 ? store.activeFilters : undefined
      const chartType = widget.value.widget?.config?.type
      const mapping = chartType
        ? { ...ds.mapping, chartType }
        : ds.mapping
      const response = await api.dashboards.refreshWidget({
        connection_id: ds.connectionId,
        sql: ds.sql,
        mapping: mapping as any,
        filters,
        dashboard_id: store.currentDashboardId ?? undefined,
        widget_sources: widget.value.sources ?? undefined,
      }) as { config: Record<string, any>; refreshed_at: string; served_from?: 'data_plane' | 'cache' | 'source'; source_columns?: string[]; source_rows?: any[][] }

      if (seq !== refreshSeq) return
      Object.assign(widget.value.widget.config, mergeRefreshedConfig(widget.value, response.config))
      ds.lastRefreshedAt = response.refreshed_at
      ds.servedFrom = response.served_from
      // Cache raw columns/rows so the Edit Widget panel opens without re-running SQL.
      if (response.source_columns) {
        store.setWidgetSourceData(widget.value.id, response.source_columns, response.source_rows ?? [])
      }
    } catch (err: any) {
      if (seq !== refreshSeq) return
      error.value = err?.data?.detail ?? err?.message ?? 'Refresh failed'
    } finally {
      if (seq === refreshSeq) localLoading.value = false
    }
  }

  // Refresh on mount and whenever active filters change (SQL-backed widgets).
  // immediate: true triggers the initial fetch so widgets always render filtered,
  // fresh data instead of the unfiltered snapshot baked into widget.config at
  // generation time. refreshSeq inside refresh() discards stale responses if
  // activeFilters changes before the in-flight request returns.
  // With the per-Org bulk_widget_loading flag on, the dashboard orchestrates
  // one bulk refresh instead (openDashboard + the page-level filter watcher),
  // so the per-widget watcher stays quiet.
  watch(
    () => JSON.stringify(store.activeFilters),
    () => {
      if (hasDataSource.value && !store.bulkWidgetLoading) refresh()
    },
    { immediate: true },
  )

  return { loading, error, lastRefreshedAt, servedFrom, hasDataSource, refresh }
}
