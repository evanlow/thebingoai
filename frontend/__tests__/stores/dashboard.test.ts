import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// ── Global mocks ────────────────────────────────────────────────────
vi.stubGlobal('localStorage', {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
})

// Mutable so individual tests can stub api methods (create/get/refreshAll).
const { apiDashboards, apiConnections } = vi.hoisted(() => ({
  apiDashboards: {} as Record<string, any>,
  apiConnections: {} as Record<string, any>,
}))
vi.mock('~/composables/useApi', () => ({
  useApi: () => ({ dashboards: apiDashboards, connections: apiConnections }),
}))

const { trackEventMock } = vi.hoisted(() => ({ trackEventMock: vi.fn() }))
vi.mock('~/utils/analytics', () => ({ trackEvent: trackEventMock }))

import { useDashboardStore } from '~/stores/dashboard'
import type { Dashboard, DashboardWidget } from '~/types/dashboard'

// ── Helpers ─────────────────────────────────────────────────────────
function makeDashboard(overrides: Partial<Dashboard> = {}): Dashboard {
  return {
    id: 1,
    title: 'Test Dashboard',
    widgets: [],
    ...overrides,
  }
}

function makeFilterWidget(controls: any[]): DashboardWidget {
  return {
    id: 'w-filter',
    position: { x: 0, y: 0, w: 12, h: 2 },
    widget: { type: 'filter', config: { controls } },
  }
}

describe('dashboard store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // ── Initial state ──────────────────────────────────────────────────
  it('has correct initial state', () => {
    const store = useDashboardStore()
    expect(store.dashboards).toEqual([])
    expect(store.currentDashboardId).toBeNull()
    expect(store.editMode).toBe(false)
    expect(store.loading).toBe(false)
    expect(store.saving).toBe(false)
    expect(store.dirty).toBe(false)
    expect(store.filterValues).toEqual({})
    expect(store.connectionTypes).toEqual({})
  })

  // ── currentDashboard ──────────────────────────────────────────────
  it('currentDashboard returns null when no id set', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard()]
    expect(store.currentDashboard).toBeNull()
  })

  it('currentDashboard returns matching dashboard', () => {
    const store = useDashboardStore()
    const dashboard = makeDashboard({ id: 42, title: 'My Board' })
    store.dashboards = [dashboard]
    store.currentDashboardId = 42
    expect(store.currentDashboard).toEqual(dashboard)
  })

  it('currentDashboard returns null when id does not match', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard({ id: 1 })]
    store.currentDashboardId = 999
    expect(store.currentDashboard).toBeNull()
  })

  // ── currentWidgets ────────────────────────────────────────────────
  it('currentWidgets returns empty when no dashboard selected', () => {
    const store = useDashboardStore()
    expect(store.currentWidgets).toEqual([])
  })

  it('currentWidgets returns widgets of current dashboard', () => {
    const store = useDashboardStore()
    const widget: DashboardWidget = {
      id: 'w-1',
      position: { x: 0, y: 0, w: 3, h: 2 },
      widget: { type: 'kpi', config: { value: 42, label: 'Score' } },
    }
    store.dashboards = [makeDashboard({ id: 1, widgets: [widget] })]
    store.currentDashboardId = 1
    expect(store.currentWidgets).toHaveLength(1)
    expect(store.currentWidgets[0].id).toBe('w-1')
  })

  // ── activeFilters ─────────────────────────────────────────────────
  it('activeFilters returns empty when no dashboard selected', () => {
    const store = useDashboardStore()
    expect(store.activeFilters).toEqual([])
  })

  it('activeFilters resolves dropdown filter to eq', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard({
      id: 1,
      widgets: [makeFilterWidget([
        { key: 'region', type: 'dropdown', column: 'region' },
      ])],
    })]
    store.currentDashboardId = 1
    store.filterValues = { region: 'APAC' }
    expect(store.activeFilters).toEqual([
      { column: 'region', dimension: undefined, op: 'eq', value: 'APAC' },
    ])
  })

  it('activeFilters resolves dropdown array filter to in', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard({
      id: 1,
      widgets: [makeFilterWidget([
        { key: 'region', type: 'dropdown', column: 'region' },
      ])],
    })]
    store.currentDashboardId = 1
    store.filterValues = { region: ['APAC', 'EMEA'] }
    expect(store.activeFilters).toEqual([
      { column: 'region', dimension: undefined, op: 'in', value: ['APAC', 'EMEA'] },
    ])
  })

  it('activeFilters resolves search filter to ilike with % wrapping', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard({
      id: 1,
      widgets: [makeFilterWidget([
        { key: 'search', type: 'search', column: 'name' },
      ])],
    })]
    store.currentDashboardId = 1
    store.filterValues = { search: 'hello' }
    expect(store.activeFilters).toEqual([
      { column: 'name', dimension: undefined, op: 'ilike', value: '%hello%' },
    ])
  })

  it('activeFilters resolves date_range filter to gte/lte pair', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard({
      id: 1,
      widgets: [makeFilterWidget([
        { key: 'dates', type: 'date_range', column: 'order_date' },
      ])],
    })]
    store.currentDashboardId = 1
    store.filterValues = { dates: { from: '2024-01-01', to: '2024-12-31' } }
    expect(store.activeFilters).toEqual([
      { column: 'order_date', dimension: undefined, op: 'gte', value: '2024-01-01' },
      { column: 'order_date', dimension: undefined, op: 'lte', value: '2024-12-31' },
    ])
  })

  it('activeFilters skips controls with empty values', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard({
      id: 1,
      widgets: [makeFilterWidget([
        { key: 'region', type: 'dropdown', column: 'region' },
        { key: 'search', type: 'search', column: 'name' },
      ])],
    })]
    store.currentDashboardId = 1
    store.filterValues = { region: '', search: null }
    expect(store.activeFilters).toEqual([])
  })

  // ── addWidget ─────────────────────────────────────────────────────
  it('addWidget adds a widget and sets dirty', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard({ id: 1, widgets: [] })]
    store.currentDashboardId = 1
    expect(store.dirty).toBe(false)

    store.addWidget('kpi')

    expect(store.currentWidgets).toHaveLength(1)
    expect(store.currentWidgets[0].widget.type).toBe('kpi')
    expect(store.dirty).toBe(true)
  })

  // ── removeWidget ──────────────────────────────────────────────────
  it('removeWidget removes widget and sets dirty', () => {
    const store = useDashboardStore()
    const widget: DashboardWidget = {
      id: 'w-1',
      position: { x: 0, y: 0, w: 3, h: 2 },
      widget: { type: 'kpi', config: { value: 42, label: 'Score' } },
    }
    store.dashboards = [makeDashboard({ id: 1, widgets: [widget] })]
    store.currentDashboardId = 1

    store.removeWidget('w-1')

    expect(store.currentWidgets).toHaveLength(0)
    expect(store.dirty).toBe(true)
  })

  // ── $resetAll ─────────────────────────────────────────────────────
  it('$resetAll clears all state', () => {
    const store = useDashboardStore()
    store.dashboards = [makeDashboard()]
    store.currentDashboardId = 1
    store.editMode = true
    store.dirty = true
    store.filterValues = { region: 'APAC' }
    store.connectionTypes = { 1: 'postgres' }

    store.$resetAll()

    expect(store.dashboards).toEqual([])
    expect(store.currentDashboardId).toBeNull()
    expect(store.editMode).toBe(false)
    expect(store.dirty).toBe(false)
    expect(store.filterValues).toEqual({})
    expect(store.connectionTypes).toEqual({})
  })

  // ── GA4 events ────────────────────────────────────────────────────
  describe('GA4 events', () => {
    beforeEach(() => {
      trackEventMock.mockClear()
      for (const k of Object.keys(apiDashboards)) delete apiDashboards[k]
      for (const k of Object.keys(apiConnections)) delete apiConnections[k]
    })

    it('createDashboard fires dashboard_create with the new id', async () => {
      apiDashboards.create = vi.fn().mockResolvedValue({ id: 5, title: 't', widgets: [], created_at: '', updated_at: '' })
      const store = useDashboardStore()
      await store.createDashboard('t')
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('dashboard_create', { dashboard_id: 5 })
    })

    it('openDashboard fires dashboard_view with the id', async () => {
      apiDashboards.get = vi.fn().mockResolvedValue({ id: 42, title: 'x', widgets: [], created_at: '', updated_at: '' })
      apiDashboards.refreshAll = vi.fn().mockResolvedValue({ widgets: {} })
      apiConnections.list = vi.fn().mockResolvedValue([])
      const store = useDashboardStore()
      await store.openDashboard(42)
      expect(trackEventMock).toHaveBeenCalledWith('dashboard_view', { dashboard_id: 42 })
      expect(trackEventMock.mock.calls.filter(c => c[0] === 'dashboard_view')).toHaveLength(1)
    })

    it('addWidget fires widget_add with the widget type', () => {
      const store = useDashboardStore()
      store.dashboards = [makeDashboard({ id: 1 })]
      store.currentDashboardId = 1
      store.editMode = true
      store.addWidget('kpi')
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('widget_add', { widget_type: 'kpi' })
    })

    it('refreshAllWidgets fires widget_refresh once past the concurrent-dedup guard', async () => {
      apiDashboards.refreshAll = vi.fn().mockResolvedValue({ widgets: {} })
      const store = useDashboardStore()
      store.dashboards = [makeDashboard({ id: 3, widgets: [] })]
      store.currentDashboardId = 3
      // Two concurrent identical bulk requests → dedup guard → one event
      await Promise.all([store.refreshAllWidgets(), store.refreshAllWidgets()])
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('widget_refresh', {
        dashboard_id: 3,
        widget_count: 0,
      })
    })
  })
})
