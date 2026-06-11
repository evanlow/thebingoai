import { defineStore } from 'pinia'
import type { Dashboard, DashboardWidget, FilterControl, GridPosition, WidgetDataSource, WidgetType } from '~/types/dashboard'
import { WIDGET_DEFAULTS } from '~/types/dashboard'
import { useApi } from '~/composables/useApi'
import { mergeRefreshedConfig } from '~/utils/widgetMerge'

export interface ActiveFilter {
  column: string
  dimension?: string  // References data_context.dimensions key
  op: 'eq' | 'neq' | 'gt' | 'gte' | 'lt' | 'lte' | 'ilike' | 'in'
  value: any
}

interface DashboardState {
  dashboards: Dashboard[]
  currentDashboardId: number | null
  editMode: boolean
  loading: boolean
  saving: boolean
  refreshing: boolean
  dirty: boolean
  filterValues: Record<string, any>  // control key → value (string | {from, to} | null)
  connectionTypes: Record<number, string>  // connectionId → db_type
  // Bulk widget loading (per-Org flag): stale-response bookkeeping.
  widgetSeq: Record<string, number>        // widget id → seq, bumped per single-widget refresh
  refreshingWidgets: Record<string, boolean>  // widget id → bulk refresh in flight
  bulkSeq: number                          // newer bulk beats older bulk
  bulkKeyInFlight: string | null           // dedup concurrent identical bulk requests
}

export const useDashboardStore = defineStore('dashboard', {
  state: (): DashboardState => ({
    dashboards: [],
    currentDashboardId: null,
    editMode: false,
    loading: false,
    saving: false,
    refreshing: false,
    dirty: false,
    filterValues: {},
    connectionTypes: {},
    widgetSeq: {},
    refreshingWidgets: {},
    bulkSeq: 0,
    bulkKeyInFlight: null,
  }),

  getters: {
    currentDashboard(state): Dashboard | null {
      if (!state.currentDashboardId) return null
      return state.dashboards.find(d => d.id === state.currentDashboardId) ?? null
    },

    currentWidgets(): DashboardWidget[] {
      return this.currentDashboard?.widgets ?? []
    },

    /** Per-Org rollout gate: widget data loads via the bulk endpoint. */
    bulkWidgetLoading(): boolean {
      return this.currentDashboard?.bulk_widget_loading === true
    },

    /** Resolve filterValues → ActiveFilter[] by looking up control column mappings */
    activeFilters(state): ActiveFilter[] {
      const dashboard = state.currentDashboardId
        ? state.dashboards.find(d => d.id === state.currentDashboardId)
        : null
      if (!dashboard) return []

      // Collect all filter controls from filter widgets
      const controls: FilterControl[] = []
      for (const dw of dashboard.widgets) {
        if (dw.widget.type === 'filter') {
          controls.push(...(dw.widget.config as any).controls)
        }
      }

      const result: ActiveFilter[] = []
      for (const control of controls) {
        const value = state.filterValues[control.key]
        if (value === null || value === undefined || value === '') continue
        if (!control.column) continue

        const dim = control.dimension || undefined
        if (control.type === 'dropdown') {
          if (Array.isArray(value) && value.length > 0) {
            result.push({ column: control.column, dimension: dim, op: 'in', value })
          } else if (typeof value === 'string' && value) {
            result.push({ column: control.column, dimension: dim, op: 'eq', value })
          }
        } else if (control.type === 'search') {
          result.push({ column: control.column, dimension: dim, op: 'ilike', value: `%${value}%` })
        } else if (control.type === 'date_range') {
          const { from, to } = value as { from?: string; to?: string }
          if (from) result.push({ column: control.column, dimension: dim, op: 'gte', value: from })
          if (to) result.push({ column: control.column, dimension: dim, op: 'lte', value: to })
        }
      }
      return result
    },
  },

  actions: {
    async fetchDashboards() {
      const api = useApi()
      this.loading = true
      try {
        const [data, connections] = await Promise.all([
          api.dashboards.list() as Promise<Dashboard[]>,
          api.connections.list() as Promise<any[]>,
        ])
        this.connectionTypes = Object.fromEntries(connections.map((c: any) => [c.id, c.db_type]))
        this.dashboards = data.map(d => ({
          ...d,
          widgets: (d.widgets ?? []).map(normalizeWidget),
          createdAt: (d as any).created_at,
          updatedAt: (d as any).updated_at,
          orgName: (d as any).org_name ?? null,
          ownerEmail: (d as any).owner_email ?? null,
          isShared: (d as any).is_shared ?? false,
        }))
      } finally {
        this.loading = false
      }
    },

    async fetchDashboard(id: number) {
      const api = useApi()
      this.loading = true
      try {
        // Reuse cached connectionTypes if available; only fetch connections if cache is empty
        const hasConnections = Object.keys(this.connectionTypes).length > 0
        const [data, connections] = await Promise.all([
          api.dashboards.get(id) as Promise<any>,
          hasConnections ? Promise.resolve(null) : api.connections.list() as Promise<any[]>,
        ])
        if (connections) {
          this.connectionTypes = Object.fromEntries(connections.map((c: any) => [c.id, c.db_type]))
        }
        const dashboard: Dashboard = {
          ...data,
          widgets: (data.widgets ?? []).map(normalizeWidget),
          data_context: data.data_context ?? null,
          createdAt: data.created_at,
          updatedAt: data.updated_at,
          // Preserve org/owner/shared metadata (snake→camel) so opening a
          // dashboard doesn't blank the list row's OWNER/WORKSPACE columns
          // (which would fall back to the current viewer = apparent owner change).
          orgName: (data as any).org_name ?? null,
          ownerEmail: (data as any).owner_email ?? null,
          isShared: (data as any).is_shared ?? false,
        }
        const idx = this.dashboards.findIndex(d => d.id === id)
        if (idx >= 0) {
          this.dashboards[idx] = dashboard
        } else {
          this.dashboards.push(dashboard)
        }
        this.dirty = false
      } finally {
        this.loading = false
      }
    },

    async createDashboard(title: string) {
      const api = useApi()
      const data = await api.dashboards.create({ title }) as any
      const dashboard: Dashboard = {
        ...data,
        createdAt: data.created_at,
        updatedAt: data.updated_at,
      }
      this.dashboards.push(dashboard)
      return dashboard
    },

    async saveDashboard() {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      const api = useApi()
      this.saving = true
      try {
        await api.dashboards.update(dashboard.id, {
          title: dashboard.title,
          description: dashboard.description,
          widgets: dashboard.widgets,
        })
        this.dirty = false
      } catch (err: any) {
        const detail = err?.data?.detail ?? err?.message ?? 'Save failed'
        // eslint-disable-next-line no-console
        console.error('[saveDashboard] failed:', err)
        if (typeof window !== 'undefined') {
          window.alert(`Save failed: ${detail}`)
        }
        throw err
      } finally {
        this.saving = false
      }
    },

    async duplicateDashboard(id: number) {
      const source = this.dashboards.find(d => d.id === id)
      if (!source) return
      const api = useApi()
      const data = await api.dashboards.create({
        title: `${source.title} (Copy)`,
        description: source.description,
        widgets: JSON.parse(JSON.stringify(source.widgets)),
      }) as any
      const dashboard: Dashboard = {
        ...data,
        widgets: (data.widgets ?? []).map(normalizeWidget),
        createdAt: data.created_at,
        updatedAt: data.updated_at,
      }
      this.dashboards.push(dashboard)
      return dashboard
    },

    async deleteDashboard(id: number) {
      const api = useApi()
      await api.dashboards.delete(id)
      this.dashboards = this.dashboards.filter(d => d.id !== id)
      if (this.currentDashboardId === id) {
        this.currentDashboardId = null
        this.editMode = false
        this.dirty = false
      }
    },

    async openDashboard(id: number) {
      this.currentDashboardId = id
      this.editMode = false
      this.dirty = false
      // Restore persisted filters from localStorage
      try {
        const saved = localStorage.getItem(`bingo:dashboard:${id}:filters`)
        this.filterValues = saved ? JSON.parse(saved) : {}
      } catch {
        this.filterValues = {}
      }
      // Ensure full dashboard data is loaded (saved config already has data)
      await this.fetchDashboard(id)
      // Bulk widget loading (per-Org flag): one batched refresh for the whole
      // dashboard. With the flag off, each widget's useWidgetData watcher
      // fires its own per-widget refresh instead (legacy path).
      if (this.bulkWidgetLoading) {
        void this.refreshAllWidgets()
      }
    },

    setFilterValue(key: string, value: any) {
      this.filterValues = { ...this.filterValues, [key]: value }
      if (this.currentDashboardId) {
        try {
          localStorage.setItem(
            `bingo:dashboard:${this.currentDashboardId}:filters`,
            JSON.stringify(this.filterValues),
          )
        } catch { /* quota exceeded — ignore */ }
      }
    },

    clearFilters() {
      this.filterValues = {}
      if (this.currentDashboardId) {
        localStorage.removeItem(`bingo:dashboard:${this.currentDashboardId}:filters`)
      }
    },

    closeDashboard() {
      this.currentDashboardId = null
      this.editMode = false
      this.dirty = false
    },

    async toggleEditMode() {
      if (this.editMode && this.dirty) {
        await this.saveDashboard()
      }
      this.editMode = !this.editMode
    },

    setEditMode(value: boolean) {
      this.editMode = value
    },

    addWidget(type: WidgetType) {
      const dashboard = this.currentDashboard
      if (!dashboard) return

      const id = `widget-${Date.now()}`
      const position = { ...WIDGET_DEFAULTS[type] }

      const maxY = dashboard.widgets.reduce((max, w) => {
        return Math.max(max, w.position.y + w.position.h)
      }, 0)
      position.y = maxY

      const newWidget: DashboardWidget = {
        id,
        position,
        widget: getDefaultWidgetConfig(type),
      }

      dashboard.widgets.push(newWidget)
      this.dirty = true
    },

    removeWidget(widgetId: string) {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      dashboard.widgets = dashboard.widgets.filter(w => w.id !== widgetId)
      this.dirty = true
    },

    duplicateWidget(widgetId: string) {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      const source = dashboard.widgets.find(w => w.id === widgetId)
      if (!source) return
      const clone: DashboardWidget = JSON.parse(JSON.stringify(source))
      clone.id = `widget-${Date.now()}`
      clone.position = { ...clone.position, y: clone.position.y + clone.position.h }
      dashboard.widgets.push(clone)
      this.dirty = true
    },

    updateWidgetPosition(widgetId: string, position: Partial<GridPosition>) {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      const widget = dashboard.widgets.find(w => w.id === widgetId)
      if (!widget) return
      Object.assign(widget.position, position)
      this.dirty = true
    },

    updateWidgetConfig(widgetId: string, widget: DashboardWidget['widget']) {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      const w = dashboard.widgets.find(w => w.id === widgetId)
      if (!w) return
      w.widget = widget
      this.dirty = true
    },

    updateWidgetMeta(widgetId: string, meta: { title?: string; description?: string }) {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      const w = dashboard.widgets.find(w => w.id === widgetId)
      if (!w) return
      if (meta.title !== undefined) w.title = meta.title
      if (meta.description !== undefined) w.description = meta.description
      this.dirty = true
    },

    setWidgetDataSource(widgetId: string, dataSource: WidgetDataSource) {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      const w = dashboard.widgets.find(w => w.id === widgetId)
      if (!w) return
      w.dataSource = dataSource
      this.dirty = true
    },

    updateWidgetSql(widgetId: string, sql: string) {
      const dashboard = this.currentDashboard
      if (!dashboard) return
      const w = dashboard.widgets.find(w => w.id === widgetId)
      if (!w?.dataSource) return
      w.dataSource.sql = sql
      this.dirty = true
    },

    async refreshAllWidgets() {
      const dashboard = this.currentDashboard
      const dashboardId = this.currentDashboardId
      if (!dashboard || dashboardId == null) return
      const api = useApi()

      const filters = this.activeFilters.length > 0 ? this.activeFilters : undefined
      // Dedup concurrent identical bulk requests (e.g. openDashboard's explicit
      // call racing the filter watcher firing for the same restored filters).
      const requestKey = `${dashboardId}:${JSON.stringify(filters ?? [])}`
      if (this.bulkKeyInFlight === requestKey) return
      this.bulkKeyInFlight = requestKey

      const bulkSeq = ++this.bulkSeq
      // Snapshot per-widget seqs: a single-widget refresh issued after this
      // point is newer than the bulk result and must not be overwritten.
      const seqSnapshot: Record<string, number> = { ...this.widgetSeq }
      const sqlWidgetIds = dashboard.widgets.filter(w => w.dataSource).map(w => w.id)
      for (const id of sqlWidgetIds) this.refreshingWidgets[id] = true
      this.refreshing = true

      try {
        // One bulk request for the whole dashboard: the backend reuses a single
        // DuckDB reader + connector across all widgets (vs one connection per
        // widget when refreshing them individually).
        const res = await api.dashboards.refreshAll(dashboardId, filters) as {
          widgets: Record<string, { config?: Record<string, any>; refreshed_at?: string; served_from?: 'data_plane' | 'cache' | 'source'; error?: string }>
        }
        if (bulkSeq !== this.bulkSeq) return // a newer bulk superseded this one
        const widgetsResult = res?.widgets ?? {}

        for (const widget of dashboard.widgets) {
          if (!widget.dataSource) continue
          if ((this.widgetSeq[widget.id] ?? 0) !== (seqSnapshot[widget.id] ?? 0)) continue // newer single-widget refresh wins
          const r = widgetsResult[widget.id]
          if (!r) continue
          if (r.error) {
            console.error(`Widget ${widget.id} refresh failed:`, r.error)
            continue
          }
          if (r.config) Object.assign(widget.widget.config, mergeRefreshedConfig(widget, r.config))
          if (r.refreshed_at) widget.dataSource.lastRefreshedAt = r.refreshed_at
          widget.dataSource.servedFrom = r.served_from
        }
      } catch (e) {
        console.error('Refresh all failed:', e)
      } finally {
        if (bulkSeq === this.bulkSeq) {
          for (const id of sqlWidgetIds) delete this.refreshingWidgets[id]
          this.refreshing = false
        }
        if (this.bulkKeyInFlight === requestKey) this.bulkKeyInFlight = null
      }
    },

    async setSchedule(dashboardId: number, scheduleType: string, scheduleValue: string, timezone?: string) {
      const api = useApi()
      const data = await api.dashboards.setSchedule(dashboardId, {
        schedule_type: scheduleType,
        schedule_value: scheduleValue,
        timezone,
      }) as any
      const dashboard = this.dashboards.find(d => d.id === dashboardId)
      if (dashboard) {
        dashboard.schedule_type = data.schedule_type
        dashboard.schedule_value = data.schedule_value
        dashboard.cron_expression = data.cron_expression
        dashboard.schedule_active = data.schedule_active
        dashboard.timezone = data.timezone
        dashboard.next_run_at = data.next_run_at
        dashboard.last_run_at = data.last_run_at
      }
    },

    async toggleSchedule(dashboardId: number, active: boolean) {
      const api = useApi()
      const data = await api.dashboards.toggleSchedule(dashboardId, active) as any
      const dashboard = this.dashboards.find(d => d.id === dashboardId)
      if (dashboard) {
        dashboard.schedule_active = data.schedule_active
        dashboard.next_run_at = data.next_run_at
      }
    },

    $resetAll() {
      this.dashboards = []
      this.currentDashboardId = null
      this.editMode = false
      this.dirty = false
      this.filterValues = {}
      this.connectionTypes = {}
    },

    async removeSchedule(dashboardId: number) {
      const api = useApi()
      await api.dashboards.removeSchedule(dashboardId)
      const dashboard = this.dashboards.find(d => d.id === dashboardId)
      if (dashboard) {
        dashboard.schedule_type = null
        dashboard.schedule_value = null
        dashboard.cron_expression = null
        dashboard.schedule_active = false
        dashboard.next_run_at = null
      }
    },
  },
})

/** Migrate old flat widget format (no config wrapper) to current schema. */
function normalizeWidget(raw: any): DashboardWidget {
  const w = raw?.widget
  if (!w?.type) return raw as DashboardWidget

  // Step 1: ensure config sub-object exists
  let config = w.config
  if (!config) {
    const { type: _type, ...rest } = w
    config = rest
  }

  // Step 2: normalize old chart format
  // Old: { chartType, title, labels, datasets }
  // New: { type, title, data: { labels, datasets } }
  if (w.type === 'chart') {
    const { chartType, labels, datasets, type: cfgType, data, ...rest } = config
    const resolvedType = cfgType ?? chartType
    const resolvedData = data ?? (labels != null ? { labels, datasets: datasets ?? [] } : { labels: [], datasets: [] })
    config = { ...rest, ...(resolvedType ? { type: resolvedType } : {}), ...(resolvedData ? { data: resolvedData } : {}) }
  }

  // Step 3: ensure pivot_table arrays exist (generated configs may omit empties)
  if (w.type === 'pivot_table') {
    config = {
      ...config,
      rowDimensions: config.rowDimensions ?? [],
      columnDimensions: config.columnDimensions ?? [],
      values: config.values ?? [],
      rows: config.rows ?? [],
    }
  }

  return { ...raw, widget: { type: w.type, config }, dataSource: raw.dataSource } as DashboardWidget
}

function getDefaultWidgetConfig(type: WidgetType): DashboardWidget['widget'] {
  switch (type) {
    case 'kpi':
      return {
        type: 'kpi',
        config: { value: 0, label: 'New Score Chart' },
      }
    case 'chart':
      return {
        type: 'chart',
        config: {
          type: 'bar',
          title: 'New Chart',
          data: { labels: ['A', 'B', 'C'], datasets: [{ label: 'Series 1', data: [10, 20, 30] }] },
        },
      }
    case 'table':
      return {
        type: 'table',
        config: {
          columns: [{ key: 'name', label: 'Name' }, { key: 'value', label: 'Value' }],
          rows: [],
        },
      }
    case 'pivot_table':
      return {
        type: 'pivot_table',
        config: {
          rowDimensions: [],
          columnDimensions: [],
          values: [],
          rows: [],
          expandCollapse: true,
          showRowTotals: true,
          showColumnTotals: true,
        },
      }
    case 'text':
      return {
        type: 'text',
        config: { content: 'Enter your text here...' },
      }
    case 'filter':
      return {
        type: 'filter',
        config: { controls: [] },
      }
  }
}
