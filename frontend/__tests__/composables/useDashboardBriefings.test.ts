import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, computed } from 'vue'

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)

const stateStore = new Map<string, any>()
vi.stubGlobal('useState', (key: string, init: () => any) => {
  if (!stateStore.has(key)) stateStore.set(key, ref(init()))
  return stateStore.get(key)
})

const mockFetch = vi.fn()
vi.stubGlobal('useApi', () => ({ fetchWithRefresh: mockFetch }))

import { useDashboardBriefings } from '~/composables/useDashboardBriefings'

function makeBriefing(overrides: Record<string, any> = {}) {
  return { id: 1, dashboard_id: 10, status: 'ready', payload: null, created_at: '2026-05-17T10:00:00Z', ...overrides }
}
const tick = () => new Promise(r => setTimeout(r, 0))

describe('useDashboardBriefings', () => {
  beforeEach(() => { mockFetch.mockReset(); stateStore.clear() })

  it('ensure() fetches scoped to the dashboard id', async () => {
    mockFetch.mockResolvedValue([makeBriefing()])
    const { briefings, loaded, ensure } = useDashboardBriefings(10)
    ensure()
    await tick(); await tick()
    expect(mockFetch).toHaveBeenCalledWith('/api/briefings?dashboard_id=10&limit=50', { method: 'GET' })
    expect(loaded.value).toBe(true)
    expect(briefings.value).toHaveLength(1)
  })

  it('keeps separate cached state per dashboard id', async () => {
    mockFetch.mockResolvedValue([makeBriefing()])
    const a = useDashboardBriefings(10)
    await a.refresh()
    mockFetch.mockClear()
    const b = useDashboardBriefings(20)
    expect(b.loaded.value).toBe(false)
    b.ensure()
    await tick(); await tick()
    expect(mockFetch).toHaveBeenCalledWith('/api/briefings?dashboard_id=20&limit=50', { method: 'GET' })
  })

  it('ensure() is a no-op once loaded', async () => {
    mockFetch.mockResolvedValue([makeBriefing()])
    const { ensure } = useDashboardBriefings(10)
    ensure()
    await tick(); await tick()
    expect(mockFetch).toHaveBeenCalledTimes(1)
    ensure()
    await tick()
    expect(mockFetch).toHaveBeenCalledTimes(1)
  })
})
