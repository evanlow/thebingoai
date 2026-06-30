import type { DashboardWidget } from '~/types/dashboard'

/**
 * Whether a widget's stored config already holds renderable data.
 *
 * Used for stale-while-revalidate painting: when a refresh is in flight,
 * widgets with existing data keep showing it (with a spinner) instead of
 * being hidden behind the loading skeleton.
 */
export function hasRenderableData(widget: DashboardWidget): boolean {
  const { type, config } = widget.widget
  switch (type) {
    case 'kpi': {
      const value = (config as { value?: number | string }).value
      return value !== undefined && value !== null && value !== ''
    }
    case 'chart': {
      const data = (config as { type?: string; data?: { datasets?: unknown[]; rows?: unknown[] } }).data
      // Timeline charts carry their data as rows, not datasets.
      if ((config as { type?: string }).type === 'timeline') return (data?.rows?.length ?? 0) > 0
      return (data?.datasets?.length ?? 0) > 0
    }
    case 'table':
    case 'pivot_table': {
      const rows = (config as { rows?: unknown[] }).rows
      return (rows?.length ?? 0) > 0
    }
    // text / filter widgets have no fetched data; never skeleton them
    default:
      return true
  }
}
