import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, watch, computed } from 'vue'
import { setActivePinia, createPinia } from 'pinia'

// ── Mock the file-upload composable (imported by useChatStreaming) ──────
// require('vue') inside the factory avoids the hoist-order TDZ on `ref`.
const { mockAttachedFiles, mockUploadPendingDatasets } = vi.hoisted(() => {
  const { ref } = require('vue')
  return {
    mockAttachedFiles: ref([] as any[]),
    mockUploadPendingDatasets: vi.fn(async () => {}),
  }
})
vi.mock('~/composables/useChatFileUpload', () => ({
  useChatFileUpload: () => ({
    attachedFiles: mockAttachedFiles,
    uploadPendingDatasets: mockUploadPendingDatasets,
  }),
}))

const CSV_MIME = 'text/csv'

/** An attachment as it looks in the composer, defaulting to a resolved CSV. */
function attachment(over: Record<string, any> = {}) {
  return {
    file: { name: 'data.csv', type: CSV_MIME, size: 10 },
    file_id: null,
    connection_id: null,
    preview_url: null,
    resolved_type: CSV_MIME,
    status: 'attached',
    ...over,
  }
}

// ── Stub Nuxt auto-imports as globals ──────────────────────────────────
vi.stubGlobal('localStorage', {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
})
vi.stubGlobal('ref', ref)
vi.stubGlobal('watch', watch)
vi.stubGlobal('computed', computed)
vi.stubGlobal('onScopeDispose', vi.fn())

// Capture the (request_id-gated) WebSocket handlers so tests can fire events, and
// the unsub returned for each registration so we can assert teardown/persistence.
const wsHandlers = new Map<string, Function>()
const wsUnsubs = new Map<string, ReturnType<typeof vi.fn>>()
// Stable across useWebSocket() calls so tests can assert what was dispatched.
const wsSend = vi.fn()
vi.stubGlobal('useWebSocket', () => ({
  on: vi.fn((type: string, handler: Function) => {
    wsHandlers.set(type, handler)
    const unsub = vi.fn()
    wsUnsubs.set(type, unsub)
    return unsub
  }),
  isConnected: ref(true),   // true → skip the reconnect/auth branch in sendMessage
  send: wsSend,
}))

/** Every `chat.send` frame dispatched so far. */
const chatSends = () => wsSend.mock.calls
  .map(c => c[0])
  .filter((f: any) => f?.type === 'chat.send')

vi.stubGlobal('useCreditBalance', () => ({ refresh: vi.fn() }))
vi.stubGlobal('useDatasetStatus', () => ({ datasets: ref([]) }))

const { trackEventMock } = vi.hoisted(() => ({ trackEventMock: vi.fn() }))
vi.mock('~/utils/analytics', () => ({ trackEvent: trackEventMock }))
vi.stubGlobal('useMentions', () => ({
  extractMentionConnectionIds: () => [],
  extractMentions: () => [],
}))

import { useChatStore } from '~/stores/chat'
import { useChatStreaming } from '~/composables/useChatStreaming'
import { MAX_QUERY_RESULT_ROWS } from '~/composables/_chatConstants'

describe('useChatStreaming — query.result → query_files', () => {
  let store: ReturnType<typeof useChatStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    wsHandlers.clear()
    wsUnsubs.clear()
    store = useChatStore()
    store.pendingConnectionIds = []
  })

  // Start a turn (registers handlers synchronously) and return the query.result handler.
  function startTurn() {
    const { sendMessage } = useChatStreaming()
    sendMessage('hi')   // never awaited — its promise only resolves on chat.done/cleanup
    const handler = wsHandlers.get('query.result')
    expect(handler).toBeDefined()
    return handler!
  }

  // The assistant placeholder is the last message sendMessage added.
  const lastMsg = () => store.messages.at(-1)!

  it('appends a QueryFile and transforms rows into result objects', () => {
    startTurn()({
      result_ref: 'r1',
      data: { columns: ['a', 'b'], rows: [[1, 2], [3, 4]], label: 'Q1', row_count: 2 },
    })

    expect(lastMsg().query_files).toEqual([
      { result_ref: 'r1', label: 'Q1', row_count: 2, col_count: 2 },
    ])
    expect(lastMsg().results).toEqual([{ a: 1, b: 2 }, { a: 3, b: 4 }])
  })

  it('dedups repeated frames with the same result_ref', () => {
    const fire = startTurn()
    const frame = { result_ref: 'r1', data: { columns: ['a'], rows: [[1]], label: 'Q', row_count: 1 } }
    fire(frame)
    fire(frame)
    expect(lastMsg().query_files).toHaveLength(1)
  })

  it('tracks each distinct result_ref in arrival order', () => {
    const fire = startTurn()
    fire({ result_ref: 'r1', data: { columns: ['a'], rows: [[1]], label: 'first' } })
    fire({ result_ref: 'r2', data: { columns: ['a'], rows: [[2]], label: 'second' } })

    const qf = lastMsg().query_files!
    expect(qf.map(f => f.result_ref)).toEqual(['r1', 'r2'])
    expect(qf.map(f => f.label)).toEqual(['first', 'second'])
  })

  it('sets results but no query_files when result_ref is absent', () => {
    startTurn()({ data: { columns: ['a'], rows: [[1]] } })
    expect(lastMsg().results).toEqual([{ a: 1 }])
    expect(lastMsg().query_files).toBeUndefined()
  })

  it('falls back to "query" label and the raw row count', () => {
    startTurn()({
      result_ref: 'r1',
      data: { columns: ['a'], rows: [[1], [2], [3]] },   // no label, no row_count
    })
    expect(lastMsg().query_files![0].label).toBe('query')
    expect(lastMsg().query_files![0].row_count).toBe(3)
  })

  it('caps results at MAX_QUERY_RESULT_ROWS but reports the true row_count', () => {
    const rows = Array.from({ length: 60 }, (_, i) => [i])
    startTurn()({ result_ref: 'r1', data: { columns: ['a'], rows, row_count: 60 } })

    expect(lastMsg().results).toHaveLength(MAX_QUERY_RESULT_ROWS)
    expect(lastMsg().query_files![0].row_count).toBe(60)
  })
})

describe('useChatStreaming — persistent query.result handler', () => {
  let store: ReturnType<typeof useChatStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    wsHandlers.clear()
    wsUnsubs.clear()
    store = useChatStore()
    store.pendingConnectionIds = []
  })

  const lastMsg = () => store.messages.at(-1)!
  const frame = (result_ref = 'r1') => ({
    result_ref,
    data: { columns: ['a'], rows: [[1]], label: 'Q', row_count: 1 },
  })

  it('survives cleanup() — a late query.result after chat.done still writes to the message', () => {
    const { sendMessage } = useChatStreaming()
    sendMessage('hi')
    const fire = wsHandlers.get('query.result')!
    const qrUnsub = wsUnsubs.get('query.result')!

    // chat.done with no prior tokens drains instantly, so cleanup() runs synchronously
    // and tears down the per-turn handlers — but must NOT touch query.result.
    wsHandlers.get('chat.done')!({ thread_id: 't1' })
    expect(store.isStreaming).toBe(false)     // cleanup ran
    expect(qrUnsub).not.toHaveBeenCalled()    // query.result handler outlived it

    fire(frame())
    expect(lastMsg().results).toEqual([{ a: 1 }])
    expect(lastMsg().query_files).toEqual([
      { result_ref: 'r1', label: 'Q', row_count: 1, col_count: 1 },
    ])
  })

  it('is replaced at the next turn — the previous turn\'s handler is unsubscribed', () => {
    const { sendMessage } = useChatStreaming()
    sendMessage('hi')                         // turn 1
    const qrUnsub1 = wsUnsubs.get('query.result')!

    sendMessage('again')                      // turn 2 drops the previous handler
    expect(qrUnsub1).toHaveBeenCalledTimes(1)
  })

  it('drops a frame whose request_id belongs to a different turn', () => {
    const fire = (() => {
      const { sendMessage } = useChatStreaming()
      sendMessage('hi')
      return wsHandlers.get('query.result')!
    })()

    fire({ ...frame(), request_id: '__other_turn__' })
    expect(lastMsg().results).toBeUndefined()
    expect(lastMsg().query_files).toBeUndefined()
  })
})

describe('useChatStreaming — deferred dataset upload', () => {
  let store: ReturnType<typeof useChatStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    wsHandlers.clear()
    wsUnsubs.clear()
    wsSend.mockClear()
    mockUploadPendingDatasets.mockReset()
    mockUploadPendingDatasets.mockResolvedValue(undefined)
    mockAttachedFiles.value = []
    store = useChatStore()
    store.currentThreadId = 't1'
    store.pendingConnectionIds = []
  })

  it('uploads pending datasets before dispatching chat.send', async () => {
    let release!: () => void
    const uploadDone = new Promise<void>(r => { release = r })
    mockUploadPendingDatasets.mockImplementation(() => uploadDone)
    mockAttachedFiles.value = [attachment()]

    const { sendMessage } = useChatStreaming()
    sendMessage('what is in here?')
    await Promise.resolve()

    // The upload is in flight — the question must not have gone out yet.
    expect(mockUploadPendingDatasets).toHaveBeenCalled()
    expect(chatSends()).toHaveLength(0)

    // The upload lands: markProcessing stamps the connection file_id.
    mockAttachedFiles.value = [attachment({
      status: 'processing', file_id: 'connection:42', connection_id: 42, sent: true,
    })]
    release()
    await new Promise(r => setTimeout(r, 0))

    // Still held — the send now also waits on documentation (see the phase-3 block).
    expect(chatSends()).toHaveLength(0)
    store.clearDocsPending(42)
    await new Promise(r => setTimeout(r, 0))

    const sends = chatSends()
    expect(sends).toHaveLength(1)
    expect(sends[0].file_ids).toEqual(['connection:42'])
  })

  it('carries the file_ids of every uploaded dataset', async () => {
    mockAttachedFiles.value = [attachment(), attachment({ file: { name: 'b.csv', type: CSV_MIME, size: 5 } })]
    mockUploadPendingDatasets.mockImplementation(async () => {
      mockAttachedFiles.value = [
        attachment({ status: 'processing', file_id: 'connection:1', connection_id: 1, sent: true }),
        attachment({ status: 'processing', file_id: 'connection:2', connection_id: 2, sent: true }),
      ]
    })

    const { sendMessage } = useChatStreaming()
    sendMessage('compare these')
    await new Promise(r => setTimeout(r, 0))
    store.clearDocsPending(1)
    store.clearDocsPending(2)
    await new Promise(r => setTimeout(r, 0))

    expect(chatSends()[0].file_ids).toEqual(['connection:1', 'connection:2'])
  })

  it('treats a text/plain .csv as a dataset when collecting file_ids', async () => {
    // Regression: the send path used to test the raw file.type, so a
    // drag-dropped CSV never reached the agent.
    mockUploadPendingDatasets.mockImplementation(async () => {
      mockAttachedFiles.value = [attachment({
        file: { name: 'report.csv', type: 'text/plain', size: 5 },
        resolved_type: CSV_MIME,
        status: 'processing', file_id: 'connection:7', connection_id: 7, sent: true,
      })]
    })
    mockAttachedFiles.value = [attachment({
      file: { name: 'report.csv', type: 'text/plain', size: 5 },
      resolved_type: CSV_MIME,
    })]

    const { sendMessage } = useChatStreaming()
    sendMessage('summarise')
    await new Promise(r => setTimeout(r, 0))
    store.clearDocsPending(7)
    await new Promise(r => setTimeout(r, 0))

    expect(chatSends()[0].file_ids).toEqual(['connection:7'])
  })

  it('sends immediately when nothing is attached', async () => {
    const { sendMessage } = useChatStreaming()
    sendMessage('hi')
    await new Promise(r => setTimeout(r, 0))

    expect(chatSends()).toHaveLength(1)
    expect(chatSends()[0].file_ids).toEqual([])
  })
})

describe('useChatStreaming — the answer waits for documentation', () => {
  let store: ReturnType<typeof useChatStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    wsHandlers.clear()
    wsUnsubs.clear()
    wsSend.mockClear()
    mockUploadPendingDatasets.mockReset()
    mockAttachedFiles.value = []
    store = useChatStore()
    store.currentThreadId = 't1'
    store.pendingConnectionIds = []
  })

  /** Simulate an upload landing: the file gains a connection id. */
  function uploadsAs(...connectionIds: number[]) {
    mockAttachedFiles.value = connectionIds.map((id, i) =>
      attachment({ file: { name: `f${i}.csv`, type: CSV_MIME, size: 5 } }))
    mockUploadPendingDatasets.mockImplementation(async () => {
      mockAttachedFiles.value = connectionIds.map((id, i) => attachment({
        file: { name: `f${i}.csv`, type: CSV_MIME, size: 5 },
        status: 'processing', file_id: `connection:${id}`, connection_id: id,
        row_count: 100 + i, sent: true,
      }))
    })
  }

  const tick = () => new Promise(r => setTimeout(r, 0))

  it('holds chat.send while the connection is awaiting documentation', async () => {
    uploadsAs(42)
    const { sendMessage } = useChatStreaming()
    sendMessage('what is in here?')
    await tick()

    // markDocsPending was applied for the uploaded connection…
    expect(store.docsPendingConnections).toContain(42)
    expect(chatSends()).toHaveLength(0)

    // …and only clearing it releases the question.
    store.clearDocsPending(42)
    await tick()
    expect(chatSends()).toHaveLength(1)
    expect(chatSends()[0].message).toBe('what is in here?')
  })

  it('waits for both connections when two datasets are attached', async () => {
    uploadsAs(1, 2)
    const { sendMessage } = useChatStreaming()
    sendMessage('compare them')
    await tick()

    expect(store.docsPendingConnections).toEqual(expect.arrayContaining([1, 2]))

    store.clearDocsPending(1)
    await tick()
    expect(chatSends()).toHaveLength(0)   // still waiting on the second

    store.clearDocsPending(2)
    await tick()
    expect(chatSends()).toHaveLength(1)
  })

  it('is released by the self-heal that clears docsPendingConnections', async () => {
    vi.useFakeTimers()
    try {
      uploadsAs(42)
      const { sendMessage } = useChatStreaming()
      sendMessage('anything')
      await vi.advanceTimersByTimeAsync(1)
      expect(chatSends()).toHaveLength(0)

      // The 120 s ceiling fires — no permanent hang even if the backend went silent.
      await vi.advanceTimersByTimeAsync(120_000)
      expect(store.docsPendingConnections).not.toContain(42)
      expect(chatSends()).toHaveLength(1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('sends without waiting when no dataset was uploaded this turn', async () => {
    mockUploadPendingDatasets.mockResolvedValue(undefined)
    const { sendMessage } = useChatStreaming()
    sendMessage('plain question')
    await tick()

    expect(store.docsPendingConnections).toEqual([])
    expect(chatSends()).toHaveLength(1)
  })

  it('empty text plus a dataset posts a follow-up instead of an agent turn', async () => {
    uploadsAs(42)
    const { sendMessage } = useChatStreaming()
    sendMessage('')
    await tick()

    // Documentation arrives with a column count.
    store.setDatasetDocs({
      connection_id: 42, table_name: 'csv_42', filename: 'f0.csv',
      table_description: null, columns: [], total_columns: 7,
    })
    store.clearDocsPending(42)
    await tick()

    expect(chatSends()).toHaveLength(0)
    const reply = store.messages.at(-1)!
    expect(reply.role).toBe('assistant')
    expect(reply.content).toContain('f0.csv')
    expect(reply.content).toContain('100 rows')
    expect(reply.content).toContain('7 columns')
    expect(store.isStreaming).toBe(false)
  })

  it('empty text with no dataset still goes to the agent', async () => {
    mockUploadPendingDatasets.mockResolvedValue(undefined)
    const { sendMessage } = useChatStreaming()
    sendMessage('')
    await tick()

    expect(chatSends()).toHaveLength(1)
  })
})

describe('useChatStreaming — GA4 chat events', () => {
  let store: ReturnType<typeof useChatStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    wsHandlers.clear()
    wsUnsubs.clear()
    trackEventMock.mockClear()
    store = useChatStore()
    store.pendingConnectionIds = []
  })

  it('sendMessage fires chat_message_sent with the current thread id', () => {
    store.currentThreadId = 't9'
    const { sendMessage } = useChatStreaming()
    sendMessage('hi')
    expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('chat_message_sent', {
      thread_id: 't9',
    })
  })

  it('chat.done fires chat_response_received with has_sql false when no SQL ran', () => {
    const { sendMessage } = useChatStreaming()
    sendMessage('hi')
    trackEventMock.mockClear()
    // No streamed tokens → the drip is drained → finalize runs synchronously.
    wsHandlers.get('chat.done')!({ thread_id: 't1' })
    expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('chat_response_received', {
      thread_id: 't1',
      has_sql: false,
    })
  })

  it('chat.done fires has_sql true when an execute_query tool call ran', () => {
    const { sendMessage } = useChatStreaming()
    sendMessage('sum revenue')
    trackEventMock.mockClear()
    wsHandlers.get('chat.tool_call')!({ content: { tool: 'execute_query', args: {} } })
    wsHandlers.get('chat.done')!({ thread_id: 't1' })
    expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('chat_response_received', {
      thread_id: 't1',
      has_sql: true,
    })
  })

  it('chat.done fires has_sql true when execute_query is nested in data_agent sub_steps', () => {
    const { sendMessage } = useChatStreaming()
    sendMessage('sum revenue')
    trackEventMock.mockClear()
    wsHandlers.get('chat.tool_call')!({
      content: { tool: 'data_agent', args: {} },
    })
    // The tool_result handler copies result.steps into the step's sub_steps.
    wsHandlers.get('chat.tool_result')!({
      content: { tool: 'data_agent', result: { steps: [{ tool_name: 'execute_query' }] } },
    })
    wsHandlers.get('chat.done')!({ thread_id: 't1' })
    expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('chat_response_received', {
      thread_id: 't1',
      has_sql: true,
    })
  })
})
