import type { DashboardWidget } from '~/types/dashboard'

/**
 * Merge a refresh response config into a widget, preserving editor-only
 * table column fields (aggregation, align, displayType, comparisonCalc,
 * runningCalc, etc.) that the backend transform doesn't know about.
 * Merged by column key. Mutates and returns `config`.
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
  return config
}
