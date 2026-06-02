import { ref, computed, watch } from 'vue'
import type { Ref } from 'vue'
import type { DashboardWidget } from '~/types/dashboard'
import { useApi } from '~/composables/useApi'
import { useDashboardStore } from '~/stores/dashboard'

export function useWidgetData(widget: Ref<DashboardWidget>) {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const store = useDashboardStore()
  let refreshSeq = 0

  const hasDataSource = computed(() => !!widget.value.dataSource)
  const lastRefreshedAt = computed(() => widget.value.dataSource?.lastRefreshedAt ?? null)
  const servedFrom = computed(() => widget.value.dataSource?.servedFrom ?? null)

  async function refresh() {
    const ds = widget.value.dataSource
    if (!ds) return

    const seq = ++refreshSeq
    loading.value = true
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
      }) as { config: Record<string, any>; refreshed_at: string; served_from?: 'data_plane' | 'cache' | 'source' }

      if (seq !== refreshSeq) return
      // For table widgets, preserve editor-only column fields (aggregation,
      // align, displayType, comparisonCalc, runningCalc, etc.) that the
      // backend transform doesn't know about. Merge by column key.
      if (widget.value.widget.type === 'table' && Array.isArray(response.config?.columns)) {
        const existingByKey = new Map<string, any>(
          ((widget.value.widget.config as any)?.columns ?? []).map((c: any) => [c.key, c]),
        )
        response.config.columns = response.config.columns.map((rc: any) => {
          const existing = existingByKey.get(rc.key)
          return existing ? { ...rc, ...existing, key: rc.key, label: rc.label ?? existing.label } : rc
        })
      }
      Object.assign(widget.value.widget.config, response.config)
      ds.lastRefreshedAt = response.refreshed_at
      ds.servedFrom = response.served_from
    } catch (err: any) {
      if (seq !== refreshSeq) return
      error.value = err?.data?.detail ?? err?.message ?? 'Refresh failed'
    } finally {
      if (seq === refreshSeq) loading.value = false
    }
  }

  // Refresh on mount and whenever active filters change (SQL-backed widgets).
  // immediate: true triggers the initial fetch so widgets always render filtered,
  // fresh data instead of the unfiltered snapshot baked into widget.config at
  // generation time. refreshSeq inside refresh() discards stale responses if
  // activeFilters changes before the in-flight request returns.
  watch(
    () => JSON.stringify(store.activeFilters),
    () => {
      if (hasDataSource.value) refresh()
    },
    { immediate: true },
  )

  return { loading, error, lastRefreshedAt, servedFrom, hasDataSource, refresh }
}
