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

const DOCS = '**orders.csv** — Customer orders\n\n| Column | I read this as |\n| --- | --- |\n| amt | Order total |'

function docsPayload(overrides: Record<string, any> = {}) {
  return {
    thread_id: 'thread-1',
    connection_id: 1,
    message: {
      id: 77,
      content: DOCS,
      timestamp: '2026-07-26T10:00:00Z',
    },
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

  // Real timers on purpose. Switching the whole file to fake timers destabilises
  // unrelated suites when the full run is parallelised, so only the one test that
  // cannot wait out its delay fakes them, and only for its own duration.
  const settled = async (predicate: () => boolean, budgetMs = 3000) => {
    const deadline = Date.now() + budgetMs
    while (!predicate() && Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 10))
    }
    return predicate()
  }

  it('subscribes to the dataset.docs event', () => {
    useChatWsHandlers().registerDatasetDocsHandler()
    expect(wsHandlers.has('dataset.docs')).toBe(true)
  })

  it('appends an assistant message with source dataset_docs for the open thread', async () => {
    useChatWsHandlers().registerDatasetDocsHandler()
    wsHandlers.get('dataset.docs')!(docsPayload())

    expect(store.messages).toHaveLength(1)
    const msg = store.messages[0]
    expect(msg.role).toBe('assistant')
    expect(msg.source).toBe('dataset_docs')
    expect(msg.id).toBe('77')

    // Content is revealed progressively, so it starts short and settles on the full text.
    expect(msg.content.length).toBeLessThan(DOCS.length)
    expect(await settled(() => store.messages[0].content === DOCS)).toBe(true)
  })

  it('reveals table rows whole so the markdown is never half-rendered', async () => {
    useChatWsHandlers().registerDatasetDocsHandler()
    wsHandlers.get('dataset.docs')!(docsPayload())

    // Sample the reveal in flight; a partial state may end mid-prose but never on
    // an incomplete `|` row, which would render as broken markdown.
    let sawPartial = false
    await settled(() => {
      const partial = store.messages[0].content
      if (partial !== DOCS) sawPartial = true
      const lastLine = partial.split('\n').pop()!
      if (lastLine.startsWith('|')) expect(lastLine.endsWith('|')).toBe(true)
      return partial === DOCS
    })

    expect(sawPartial).toBe(true)
    expect(store.messages[0].content).toBe(DOCS)
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

  it('clears docs-pending even when the payload carries no message', () => {
    useChatWsHandlers().registerDatasetDocsHandler()

    wsHandlers.get('dataset.docs.start')!({ thread_id: 'thread-1', connection_id: 1 })
    wsHandlers.get('dataset.docs')!({ thread_id: 'thread-1', connection_id: 1 })

    expect(store.docsPendingConnections).not.toContain(1)
    expect(store.messages).toHaveLength(0)
  })

  it('ignores a payload for a different thread', () => {
    useChatWsHandlers().registerDatasetDocsHandler()
    wsHandlers.get('dataset.docs')!(docsPayload({ thread_id: 'other-thread' }))

    expect(store.messages).toHaveLength(0)
  })

  it('does not increment unread — the user is already looking at this thread', () => {
    const incrementUnread = vi.spyOn(store, 'incrementUnread')
    useChatWsHandlers().registerDatasetDocsHandler()
    wsHandlers.get('dataset.docs')!(docsPayload())

    expect(incrementUnread).not.toHaveBeenCalled()
  })

  it('ignores a payload with no message without throwing', () => {
    useChatWsHandlers().registerDatasetDocsHandler()
    expect(() => wsHandlers.get('dataset.docs')!({ thread_id: 'thread-1' })).not.toThrow()
    expect(store.messages).toHaveLength(0)
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
