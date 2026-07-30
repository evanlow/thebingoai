import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'

// ── Stub Nuxt auto-imports ───────────────────────────────────────────
vi.stubGlobal('ref', ref)

const listMock = vi.fn()
const getTypesMock = vi.fn()
vi.stubGlobal('useApi', () => ({
  connections: { list: listMock, getTypes: getTypesMock },
}))

// The composable caches at module scope, so each test reloads it cold.
async function loadComposable() {
  vi.resetModules()
  const mod = await import('~/composables/useConnections')
  return mod.useConnections()
}

const CONNECTIONS = [
  { id: 104, name: 'HR_dataset', db_type: 'dataset', source_filename: 'HR_dataset.csv' },
  { id: 7, name: 'Warehouse', db_type: 'postgres', source_filename: null },
  // Non-upload connectors reuse the column for internal metadata.
  {
    id: 47, name: 'theleadio', db_type: 'facebook_ads',
    source_filename: '{"token_refreshed_at": "2026-05-26T00:49:52.061293+00:00"}',
  },
  {
    id: 59, name: 'Airbnb Listings (Sample)', db_type: 'sqlite',
    source_filename: '__bingo_sample__airbnb_listings',
  },
]

describe('useConnections.getSourceLabel', () => {
  beforeEach(() => {
    listMock.mockReset().mockResolvedValue(CONNECTIONS)
    getTypesMock.mockReset().mockResolvedValue([])
  })

  it('returns the uploaded filename for an upload-backed connection', async () => {
    const { ensureLoaded, getSourceLabel } = await loadComposable()
    await ensureLoaded()
    expect(getSourceLabel(104)).toBe('HR_dataset.csv')
  })

  it('returns null for a connection with no uploaded file', async () => {
    const { ensureLoaded, getSourceLabel } = await loadComposable()
    await ensureLoaded()
    expect(getSourceLabel(7)).toBeNull()
  })

  it('returns null when the column holds connector metadata, not a filename', async () => {
    const { ensureLoaded, getSourceLabel } = await loadComposable()
    await ensureLoaded()
    expect(getSourceLabel(47)).toBeNull()
    expect(getSourceLabel(59)).toBeNull()
  })

  it('returns null for an unknown connection id', async () => {
    const { ensureLoaded, getSourceLabel } = await loadComposable()
    await ensureLoaded()
    expect(getSourceLabel(999)).toBeNull()
  })

  it('returns null when the connection fetch fails', async () => {
    listMock.mockRejectedValue(new Error('boom'))
    const { ensureLoaded, getSourceLabel } = await loadComposable()
    await ensureLoaded()
    expect(getSourceLabel(104)).toBeNull()
  })
})

describe('useConnections.upsertConnection', () => {
  beforeEach(() => {
    listMock.mockReset().mockResolvedValue(CONNECTIONS)
    getTypesMock.mockReset().mockResolvedValue([])
  })

  it('labels a connection created after the cache went warm', async () => {
    // ensureLoaded returns early forever once loaded, so a dataset uploaded later
    // in the session had no entry and its dashboards lost the source label.
    const { ensureLoaded, getSourceLabel, upsertConnection } = await loadComposable()
    await ensureLoaded()
    expect(getSourceLabel(200)).toBeNull()

    upsertConnection({ id: 200, name: 'Q3_sales', db_type: 'dataset', source_filename: 'Q3_sales.csv' })
    expect(getSourceLabel(200)).toBe('Q3_sales.csv')
  })

  it('still refuses a value that is not filename-shaped', async () => {
    const { ensureLoaded, getSourceLabel, upsertConnection } = await loadComposable()
    await ensureLoaded()

    upsertConnection({ id: 201, name: 'ads', source_filename: '{"token_refreshed_at": "2026-05-26"}' })
    expect(getSourceLabel(201)).toBeNull()
  })

  it('overwrites an existing entry rather than duplicating it', async () => {
    const { ensureLoaded, getSourceLabel, upsertConnection } = await loadComposable()
    await ensureLoaded()

    upsertConnection({ id: 104, name: 'HR_dataset', db_type: 'dataset', source_filename: 'HR_v2.csv' })
    expect(getSourceLabel(104)).toBe('HR_v2.csv')
  })

  it('is a no-op before the first load, and the fetch still wins', async () => {
    // Nothing to merge into yet — ensureLoaded will pick the row up from the server,
    // so upserting into a null cache must not fabricate a partial one.
    const { ensureLoaded, getSourceLabel, upsertConnection } = await loadComposable()
    upsertConnection({ id: 104, name: 'HR_dataset', source_filename: 'stale.csv' })
    expect(getSourceLabel(104)).toBeNull()

    await ensureLoaded()
    expect(getSourceLabel(104)).toBe('HR_dataset.csv')
  })

  it('leaves the other cached connections alone', async () => {
    const { ensureLoaded, getSourceLabel, upsertConnection } = await loadComposable()
    await ensureLoaded()

    upsertConnection({ id: 200, name: 'Q3_sales', source_filename: 'Q3_sales.csv' })
    expect(getSourceLabel(104)).toBe('HR_dataset.csv')
    expect(getSourceLabel(7)).toBeNull()
  })
})
