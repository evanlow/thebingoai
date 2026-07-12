import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, computed, watch } from 'vue'

// ── Stub Nuxt auto-imports as globals ──────────────────────────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', watch)
vi.stubGlobal('onUnmounted', vi.fn())

const mockDashList = vi.fn()
const mockConnList = vi.fn()
vi.stubGlobal('useApi', () => ({
  dashboards: { list: mockDashList },
  connections: { list: mockConnList },
}))

import { useMentions } from '~/composables/useMentions'

// _doLoad awaits Promise.all of the mocked (resolved) API calls; flush microtasks.
const flush = async () => { for (let i = 0; i < 6; i++) await Promise.resolve() }

describe('useMentions filteredGroups — root search matches connection names', () => {
  beforeEach(() => {
    mockDashList.mockResolvedValue({ dashboards: [] })
    // Two Google Sheets connections — the case the @-mention fix targets.
    mockConnList.mockResolvedValue([
      { id: 48, name: 'Sales', db_type: 'google_sheets' },
      { id: 49, name: 'Inventory', db_type: 'google_sheets' },
    ])
  })

  it('typing a connection name at root surfaces its group (was "0 matches")', async () => {
    const m = useMentions()
    m.openMention(0)          // triggers _doLoad
    await flush()
    m.setQuery('Sales')

    const groups = m.filteredGroups.value
    const db = groups.find((g: any) => g.id === 'databases')
    expect(db).toBeTruthy()
    // Group is kept AND narrowed to the matching connection only.
    expect(db.items.map((i: any) => i.displayName)).toEqual(['Sales'])
    expect(db.count).toBe(1)
  })

  it('matches by group label too (whole group kept)', async () => {
    const m = useMentions()
    m.openMention(0)
    await flush()
    m.setQuery('Databases')

    const db = m.filteredGroups.value.find((g: any) => g.id === 'databases')
    expect(db).toBeTruthy()
    expect(db.items.length).toBe(2)   // label match → all items retained
  })

  it('a query matching nothing yields no groups', async () => {
    const m = useMentions()
    m.openMention(0)
    await flush()
    m.setQuery('zzz-no-such-thing')
    expect(m.filteredGroups.value.length).toBe(0)
  })

  it('empty query returns all groups unfiltered', async () => {
    const m = useMentions()
    m.openMention(0)
    await flush()
    m.setQuery('')
    const db = m.filteredGroups.value.find((g: any) => g.id === 'databases')
    expect(db.items.length).toBe(2)
  })
})
