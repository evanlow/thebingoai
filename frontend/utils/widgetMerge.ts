import { markRaw } from 'vue'
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
 * Merge a refresh response config into a widget, **data-only**: the user's saved
 * config is the source of truth for structure (column order/visibility, dataset
 * order/style, titles, KPI formatting); the refresh only supplies the values the
 * SQL produced (rows, dataset data arrays, labels, KPI value). Returns a partial
 * config whose keys are then `Object.assign`-ed onto the live widget config — so
 * any key the refresh doesn't supply is left untouched.
 *
 * Schema changes still flow through: a column/dataset the refresh introduces (no
 * saved match) is appended; one the refresh no longer returns is dropped.
 */
export function mergeRefreshedConfig(
  widget: DashboardWidget,
  refreshed: Record<string, any>,
): Record<string, any> {
  const type = widget.widget.type
  const existing = (widget.widget.config ?? {}) as Record<string, any>

  if (type === 'chart') return mergeChart(existing, refreshed)
  if (type === 'table') return mergeTable(existing, refreshed)
  if (type === 'kpi') return mergeKpi(refreshed)

  // pivot_table / text / filter: the refresh transform emits only data keys
  // (rows, granular columns) — structural edits live in keys it never emits, so
  // Object.assign already preserves them. Keep the pass-through.
  // markRaw the row array in place (markRaw returns the same reference): it's
  // read-only display data, so keeping it out of Vue's deep-reactive graph avoids
  // proxy overhead that otherwise scales with retained result-set size. Flagging
  // in place preserves the pass-through identity Object.assign relies on.
  if (Array.isArray((refreshed as any)?.rows)) markRaw((refreshed as any).rows)
  return refreshed
}

function mergeChart(
  existing: Record<string, any>,
  refreshed: Record<string, any>,
): Record<string, any> {
  const rData = refreshed?.data
  if (!rData) return {}
  // Non-Chart.js data shape (no datasets array) — nothing structural to protect.
  if (!Array.isArray(rData.datasets)) return { data: rData }

  const existingDatasets: any[] = existing?.data?.datasets ?? []
  // ponytail: keyed by dataset label; duplicate labels collapse (rare).
  const refreshedByLabel = new Map<string, any>(
    rData.datasets.map((d: any) => [d.label, d]),
  )

  // Structure/order/style from saved config; values from refresh. Drop datasets
  // the refresh no longer returns; append datasets it newly introduced.
  const merged: any[] = []
  const seen = new Set<string>()
  for (const prev of existingDatasets) {
    const rc = refreshedByLabel.get(prev.label)
    if (!rc) continue
    seen.add(prev.label)
    merged.push({ ...prev, data: rc.data })
  }
  for (const rc of rData.datasets) {
    if (!seen.has(rc.label)) merged.push(rc)
  }

  return {
    data: {
      ...(existing?.data ?? {}),
      labels: rData.labels ?? existing?.data?.labels,
      datasets: merged,
    },
  }
}

function mergeTable(
  existing: Record<string, any>,
  refreshed: Record<string, any>,
): Record<string, any> {
  const out: Record<string, any> = {}
  // markRaw the rows: read-only display data (sort/filter operate on copies —
  // see DashboardWidgetTable), so keeping it non-reactive avoids proxy overhead
  // proportional to result-set size. Columns stay reactive (editor mutates them).
  if (Array.isArray(refreshed?.rows)) out.rows = markRaw(refreshed.rows)

  const existingColumns = existing?.columns
  if (Array.isArray(refreshed?.columns)) {
    if (!Array.isArray(existingColumns) || existingColumns.length === 0) {
      out.columns = refreshed.columns // first load — adopt the generated columns
    } else {
      const refreshedByKey = new Map<string, any>(
        refreshed.columns.map((c: any) => [c.key, c]),
      )
      const existingKeys = new Set(existingColumns.map((c: any) => c.key))
      const merged: any[] = []
      // Saved column order/visibility/editor fields win; drop columns no longer
      // in the result, keep the rest in the user's order.
      for (const c of existingColumns) {
        if (!refreshedByKey.has(c.key)) continue
        merged.push({ ...refreshedByKey.get(c.key), ...c, key: c.key })
      }
      // Append columns the refresh newly introduced (real SQL/schema change).
      for (const rc of refreshed.columns) {
        if (!existingKeys.has(rc.key)) merged.push(rc)
      }
      out.columns = merged
    }
  }
  return out
}

function mergeKpi(refreshed: Record<string, any>): Record<string, any> {
  const out: Record<string, any> = {}
  if (refreshed && 'value' in refreshed) out.value = refreshed.value
  if (refreshed && refreshed.trend !== undefined) out.trend = refreshed.trend
  return out
}
