import type { DashboardWidget } from '~/types/dashboard'

/**
 * Per-dataset style fields the user edits in the chart editor. The backend
 * refresh transform doesn't know about these (they live in config.data.datasets,
 * not in the mapping), so they must be preserved across a data refresh.
 * Single source of truth — also imported by WidgetEditorChartStyle.vue.
 */
export const DATASET_STYLE_KEYS = [
  'seriesType', 'lineWeight', 'lineStyle', 'showPoints', 'pointRadius',
  'stepped', 'gradient', 'cumulative', 'showDataLabels', 'yAxisID',
  'trendline', 'borderColor', 'backgroundColor', 'borderWidth', 'fill', 'tension',
] as const

/**
 * Merge a refresh response config into a widget, preserving editor-only fields
 * that the backend transform doesn't know about: table column fields
 * (aggregation, align, displayType, comparisonCalc, runningCalc, etc.) merged by
 * column key, and chart per-dataset style fields merged by dataset index.
 * Mutates and returns `config`.
 */
export function mergeRefreshedConfig(
  widget: DashboardWidget,
  config: Record<string, any>,
): Record<string, any> {
  if (widget.widget.type === 'table' && Array.isArray(config?.columns)) {
    const existingByKey = new Map<string, any>(
      ((widget.widget.config as any)?.columns ?? []).map((c: any) => [c.key, c]),
    )
    config.columns = config.columns.map((rc: any) => {
      const existing = existingByKey.get(rc.key)
      return existing ? { ...rc, ...existing, key: rc.key, label: rc.label ?? existing.label } : rc
    })
  }
  if (widget.widget.type === 'chart' && Array.isArray(config?.data?.datasets)) {
    const existing = (widget.widget.config as any)?.data?.datasets ?? []
    config.data.datasets = config.data.datasets.map((rc: any, i: number) => {
      const prev = existing[i]
      if (!prev) return rc
      const merged: any = { ...rc }
      for (const k of DATASET_STYLE_KEYS) if (k in prev) merged[k] = prev[k]
      return merged
    })
  }
  return config
}
