import { describe, it, expect, vi, beforeEach } from 'vitest'
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
  })

  it('subscribes to the dataset.docs event', () => {
    useChatWsHandlers().registerDatasetDocsHandler()
    expect(wsHandlers.has('dataset.docs')).toBe(true)
  })

  it('appends an assistant message with source dataset_docs for the open thread', () => {
    useChatWsHandlers().registerDatasetDocsHandler()
    wsHandlers.get('dataset.docs')!(docsPayload())

    expect(store.messages).toHaveLength(1)
    const msg = store.messages[0]
    expect(msg.role).toBe('assistant')
    expect(msg.source).toBe('dataset_docs')
    expect(msg.content).toBe(DOCS)
    expect(msg.id).toBe('77')
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
