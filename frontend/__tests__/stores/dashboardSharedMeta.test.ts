import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.stubGlobal('localStorage', {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
})

const listDashboardsMock = vi.fn()
const getDashboardMock = vi.fn()
const listConnectionsMock = vi.fn(async () => [])

vi.mock('~/composables/useApi', () => ({
  useApi: () => ({
    dashboards: { list: listDashboardsMock, get: getDashboardMock },
    connections: { list: listConnectionsMock },
  }),
}))

import { useDashboardStore } from '~/stores/dashboard'

const SHARED_ROW = {
  id: 1,
  title: 'Shared',
  widgets: [],
  created_at: 'c',
  updated_at: 'u',
  org_name: 'Host Inc',
  owner_email: 'host@x.com',
  is_shared: true,
}

describe('dashboard store — shared/owner metadata mapping', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listDashboardsMock.mockReset()
    getDashboardMock.mockReset()
    listConnectionsMock.mockReset()
    listConnectionsMock.mockResolvedValue([])
  })

  it('fetchDashboards maps snake_case org/owner/shared → camelCase', async () => {
    listDashboardsMock.mockResolvedValueOnce([SHARED_ROW])
    const store = useDashboardStore()

    await store.fetchDashboards()

    const d = store.dashboards[0] as any
    expect(d.orgName).toBe('Host Inc')
    expect(d.ownerEmail).toBe('host@x.com')
    expect(d.isShared).toBe(true)
  })

  it('fetchDashboards defaults isShared/owner to null/false when absent (own dashboard)', async () => {
    listDashboardsMock.mockResolvedValueOnce([
      { id: 2, title: 'Mine', widgets: [], created_at: 'c', updated_at: 'u' },
    ])
    const store = useDashboardStore()

    await store.fetchDashboards()

    const d = store.dashboards[0] as any
    expect(d.ownerEmail).toBeNull()
    expect(d.orgName).toBeNull()
    expect(d.isShared).toBe(false)
  })

  it('fetchDashboard preserves owner/org/shared (opening must not blank the owner)', async () => {
    // Seed the list row carrying the shared metadata.
    listDashboardsMock.mockResolvedValueOnce([SHARED_ROW])
    const store = useDashboardStore()
    await store.fetchDashboards()

    // Open it — the detail response carries the same metadata; the store must
    // keep ownerEmail so the OWNER column doesn't fall back to the viewer
    // (the "ownership changed on click" bug).
    getDashboardMock.mockResolvedValueOnce({ ...SHARED_ROW, data_context: null })
    await store.fetchDashboard(1)

    const d = store.dashboards[0] as any
    expect(d.ownerEmail).toBe('host@x.com')
    expect(d.orgName).toBe('Host Inc')
    expect(d.isShared).toBe(true)
  })
})
