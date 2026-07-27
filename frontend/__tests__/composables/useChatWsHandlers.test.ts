import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, computed, watch } from 'vue'
import { setActivePinia, createPinia } from 'pinia'

// ── Stub Nuxt auto-imports as globals ──────────────────────────────

vi.stubGlobal('localStorage', {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
})
vi.stubGlobal('$fetch', vi.fn())
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', watch)
vi.stubGlobal('onUnmounted', vi.fn())

// Capture the handlers the composable subscribes with so tests can fire events
const wsHandlers = new Map<string, Function>()
const mockSend = vi.fn()
vi.stubGlobal('useWebSocket', () => ({
  on: vi.fn((type: string, handler: Function) => {
    wsHandlers.set(type, handler)
    return vi.fn()
  }),
  send: mockSend,
}))

import { useChatStore } from '~/stores/chat'
import { useChatWsHandlers } from '~/composables/useChatWsHandlers'

function docsPayload(overrides: Record<string, any> = {}) {
  return {
    thread_id: 'thread-1',
    connection_id: 1,
    table_name: 'csv_1',
    filename: 'orders.csv',
    table_description: 'Customer orders',
    columns: [{ name: 'amt', display_name: 'Order total', description: 'Value in cents' }],
    total_columns: 1,
    ...overrides,
  }
}

describe('registerDatasetDocsHandler', () => {
  let store: ReturnType<typeof useChatStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    wsHandlers.clear()
    store = useChatStore()
    store.currentThreadId = 'thread-1'
    store.messages = []
    store.docsPendingConnections = []
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('subscribes to the dataset.docs event', () => {
    useChatWsHandlers().registerDatasetDocsHandler()
    expect(wsHandlers.has('dataset.docs')).toBe(true)
  })

  it('stores the payload against its connection and appends no message', () => {
    // Documentation belongs inside the dataset's card now, not in the transcript.
    useChatWsHandlers().registerDatasetDocsHandler()
    wsHandlers.get('dataset.docs')!(docsPayload())

    expect(store.messages).toHaveLength(0)
    expect(store.datasetDocs[1]).toEqual({
      connection_id: 1,
      table_name: 'csv_1',
      filename: 'orders.csv',
      table_description: 'Customer orders',
      columns: [{ name: 'amt', display_name: 'Order total', description: 'Value in cents' }],
      total_columns: 1,
    })
  })

  it('keeps each connection separate', () => {
    useChatWsHandlers().registerDatasetDocsHandler()
    wsHandlers.get('dataset.docs')!(docsPayload({ connection_id: 1, filename: 'a.csv' }))
    wsHandlers.get('dataset.docs')!(docsPayload({ connection_id: 2, filename: 'b.csv' }))

    expect(store.datasetDocs[1].filename).toBe('a.csv')
    expect(store.datasetDocs[2].filename).toBe('b.csv')
  })

  it('marks the connection docs-pending on dataset.docs.start and clears it on arrival', async () => {
    useChatWsHandlers().registerDatasetDocsHandler()

    wsHandlers.get('dataset.docs.start')!({ thread_id: 'thread-1', connection_id: 1 })
    expect(store.docsPendingConnections).toContain(1)

    wsHandlers.get('dataset.docs')!(docsPayload())
    expect(store.docsPendingConnections).not.toContain(1)
  })

  it('leaves a second upload pending when the first upload finishes', () => {
    // Two files in one thread: the first file's docs must not take the second
    // file's progress down with it.
    useChatWsHandlers().registerDatasetDocsHandler()

    wsHandlers.get('dataset.docs.start')!({ thread_id: 'thread-1', connection_id: 1 })
    wsHandlers.get('dataset.docs.start')!({ thread_id: 'thread-1', connection_id: 2 })

    wsHandlers.get('dataset.docs')!(docsPayload({ connection_id: 1 }))

    expect(store.docsPendingConnections).not.toContain(1)
    expect(store.docsPendingConnections).toContain(2)
  })

  it('ignores a start event with no connection id — it could not be cleared later', () => {
    useChatWsHandlers().registerDatasetDocsHandler()
    wsHandlers.get('dataset.docs.start')!({ thread_id: 'thread-1' })

    expect(store.docsPendingConnections).toHaveLength(0)
  })

  it('clears a stuck docs-pending flag so the flow cannot hang forever', async () => {
    vi.useFakeTimers()
    useChatWsHandlers().registerDatasetDocsHandler()

    wsHandlers.get('dataset.docs.start')!({ thread_id: 'thread-1', connection_id: 1 })
    expect(store.docsPendingConnections).toContain(1)

    // Generation died — no completion event ever arrives.
    await vi.advanceTimersByTimeAsync(120_000)
    expect(store.docsPendingConnections).not.toContain(1)
  })

  it('clears docs-pending on an empty terminal payload and stores nothing renderable', () => {
    // The skip paths publish columns: [] purely to release the waiting composer.
    useChatWsHandlers().registerDatasetDocsHandler()

    wsHandlers.get('dataset.docs.start')!({ thread_id: 'thread-1', connection_id: 1 })
    wsHandlers.get('dataset.docs')!({
      thread_id: 'thread-1', connection_id: 1, columns: [], total_columns: 0,
    })

    expect(store.docsPendingConnections).not.toContain(1)
    expect(store.datasetDocs[1].columns).toEqual([])
    expect(store.messages).toHaveLength(0)
  })

  it('ignores a payload with no connection id, and does not throw', () => {
    // Nothing to key the docs on, and nothing to release.
    useChatWsHandlers().registerDatasetDocsHandler()
    expect(() => wsHandlers.get('dataset.docs')!({ thread_id: 'thread-1' })).not.toThrow()

    expect(store.datasetDocs).toEqual({})
    expect(store.messages).toHaveLength(0)
  })

  it('survives a malformed columns field', () => {
    useChatWsHandlers().registerDatasetDocsHandler()
    expect(() => wsHandlers.get('dataset.docs')!(docsPayload({ columns: 'nope' }))).not.toThrow()

    expect(store.datasetDocs[1].columns).toEqual([])
  })

  it('does not increment unread — the user is already looking at this thread', () => {
    const incrementUnread = vi.spyOn(store, 'incrementUnread')
    useChatWsHandlers().registerDatasetDocsHandler()
    wsHandlers.get('dataset.docs')!(docsPayload())

    expect(incrementUnread).not.toHaveBeenCalled()
  })
})

describe('useChatWsHandlers exports', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('exposes registerDatasetDocsHandler', () => {
    expect(typeof useChatWsHandlers().registerDatasetDocsHandler).toBe('function')
  })
})
