import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, computed } from 'vue'
import { setActivePinia, createPinia } from 'pinia'

// ── Nuxt auto-import stubs ──────────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('nextTick', () => Promise.resolve())
vi.stubGlobal('watch', vi.fn())
vi.stubGlobal('defineEmits', vi.fn())
vi.stubGlobal('onMounted', vi.fn((cb: () => void) => cb()))
vi.stubGlobal('useRouter', () => ({ push: vi.fn() }))
vi.stubGlobal('useApi', () => ({
  telegram: { getStatus: vi.fn().mockResolvedValue({ connected: false, bot_username: null, is_active: false }) },
}))
vi.stubGlobal('useChat', () => ({ renameConversation: vi.fn() }))
vi.stubGlobal('useFeatureConfig', () => ({ config: ref({ telegram_enabled: false }) }))

// ChatThread reads `datasets` from this composable — drive it per test.
const mockDatasets = vi.hoisted(() => {
  const { ref } = require('vue')
  return ref<any[]>([])
})
vi.mock('~/composables/useDatasetStatus', () => ({
  useDatasetStatus: () => ({ datasets: mockDatasets }),
}))

// Not under test — both reach for Nuxt runtime helpers ChatThread's setup would
// otherwise trip on (useState, the auth store).
vi.mock('~/composables/useBriefingsList', () => {
  const { ref } = require('vue')
  return { useBriefingsList: () => ({ briefings: ref([]), ensure: vi.fn() }) }
})
vi.mock('~/composables/useAgentProfile', () => {
  const { ref } = require('vue')
  return { useAgentProfile: () => ({ profile: ref(null) }) }
})

import ChatThread from '~/components/chat/ChatThread.vue'

const stubs = {
  ChatMessageBubble: { template: '<div class="bubble" />' },
  // Surfaces the props ChatThread hands the progress card so the docs step is assertable.
  DatasetProgressCard: {
    props: ['dataset', 'docsStatus'],
    template: '<div class="progress-card" :data-name="dataset.name" :data-docs="String(docsStatus)" />',
  },
}

const PENDING = 'Reading your data…'
const IDLE = 'Ask me anything about your data'

function dataset(step: string, connectionId: number | null = 1, name = 'HR_dataset.csv') {
  return { name, size: 1, fileId: `f${connectionId}`, connectionId, step, error: null }
}

function makeChatStore(type = 'task', messages: any[] = [], docsPendingConnections: number[] = []) {
  return {
    currentConversation: { type, title: 'Bingo AI' },
    currentThreadId: 'thread-123',
    infoPanelOpen: false,
    messages,
    messagesLoading: false,
    isStreaming: false,
    docsPendingConnections,
    toggleInfoPanel: vi.fn(),
    permanentConversation: type === 'permanent' ? { title: 'Bingo AI' } : null,
  }
}

async function mountThread(type = 'task', messages: any[] = [], docsPendingConnections: number[] = []) {
  vi.stubGlobal('useChatStore', () => makeChatStore(type, messages, docsPendingConnections))
  const wrapper = mount(ChatThread, { global: { stubs } })
  await flushPromises()
  return wrapper
}

describe('ChatThread — empty state while a dataset is processing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // useAgentProfile reaches for a Pinia store during ChatThread setup
    setActivePinia(createPinia())
    mockDatasets.value = []
  })

  it('shows "Reading your data…" when a dataset is still processing', async () => {
    mockDatasets.value = [dataset('profiling')]
    const text = (await mountThread()).text()

    expect(text).toContain(PENDING)
    expect(text).not.toContain(IDLE)
  })

  it('shows the normal prompt once every dataset is ready', async () => {
    mockDatasets.value = [dataset('ready')]
    const text = (await mountThread()).text()

    expect(text).toContain(IDLE)
    expect(text).not.toContain(PENDING)
  })

  it('shows the normal prompt when a dataset failed — failed is terminal, not pending', async () => {
    mockDatasets.value = [dataset('failed')]
    const text = (await mountThread()).text()

    expect(text).toContain(IDLE)
    expect(text).not.toContain(PENDING)
  })

  it('renders the upload progress flow inline in the thread', async () => {
    mockDatasets.value = [dataset('profiling')]
    const wrapper = await mountThread()

    const card = wrapper.find('.progress-card')
    expect(card.exists()).toBe(true)
    expect(card.attributes('data-name')).toBe('HR_dataset.csv')
  })

  it('holds the documentation step pending until the dataset is profiled', async () => {
    mockDatasets.value = [dataset('profiling')]
    const wrapper = await mountThread('task', [], [1])

    expect(wrapper.find('.progress-card').attributes('data-docs')).toBe('pending')
  })

  it('marks the documentation step active once profiling is done and docs are still running', async () => {
    mockDatasets.value = [dataset('ready')]
    const wrapper = await mountThread('task', [], [1])

    expect(wrapper.find('.progress-card').attributes('data-docs')).toBe('active')
  })

  it('drops a failed dataset from the flow — terminal, nothing left to report', async () => {
    mockDatasets.value = [dataset('failed'), dataset('uploading', 2, 'other.csv')]
    const wrapper = await mountThread('task', [], [1])

    const cards = wrapper.findAll('.progress-card')
    expect(cards).toHaveLength(1)
    expect(cards[0].attributes('data-name')).toBe('other.csv')
  })

  it('keeps the processing copy after profiling finishes while docs are still generating', async () => {
    // The exact regression: profiling completes seconds before the LLM does, and
    // the copy used to flicker back to the idle prompt in between.
    mockDatasets.value = [dataset('ready')]
    const text = (await mountThread('task', [], [1])).text()

    expect(text).toContain(PENDING)
    expect(text).not.toContain(IDLE)
  })

  it('ignores a docs-pending flag belonging to another connection', async () => {
    mockDatasets.value = [dataset('ready')]
    const text = (await mountThread('task', [], [99])).text()

    expect(text).toContain(IDLE)
    expect(text).not.toContain(PENDING)
  })

  it('keeps a second upload reporting after the first one is documented', async () => {
    // Two files: #1 is done and its docs message is in the thread, #2 is still
    // profiling. The flow used to vanish wholesale on the first docs message.
    mockDatasets.value = [dataset('ready'), dataset('profiling', 2, 'other.csv')]
    const wrapper = await mountThread('task', [
      { id: 'm1', role: 'assistant', content: 'hi', source: 'dataset_docs', created_at: '2026-07-26T10:00:00Z' },
    ], [2])

    const cards = wrapper.findAll('.progress-card')
    expect(cards).toHaveLength(1)
    expect(cards[0].attributes('data-name')).toBe('other.csv')
    expect(wrapper.find('.bubble').exists()).toBe(true)
  })

  it('drops the flow once every dataset is documented', async () => {
    mockDatasets.value = [dataset('ready'), dataset('ready', 2, 'other.csv')]
    const wrapper = await mountThread('task', [
      { id: 'm1', role: 'assistant', content: 'hi', source: 'dataset_docs', created_at: '2026-07-26T10:00:00Z' },
    ], [])

    expect(wrapper.findAll('.progress-card')).toHaveLength(0)
  })

  it('renders no empty-state heading once messages exist', async () => {
    mockDatasets.value = [dataset('profiling')]
    const wrapper = await mountThread('task', [
      { id: 'm1', role: 'assistant', content: 'hi', source: 'dataset_docs', created_at: '2026-07-26T10:00:00Z' },
    ])

    expect(wrapper.text()).not.toContain(PENDING)
    expect(wrapper.text()).not.toContain(IDLE)
    expect(wrapper.find('.bubble').exists()).toBe(true)
    // The flow itself still renders — below the message, without the heading.
    expect(wrapper.find('.progress-card').exists()).toBe(true)
  })

  it('keeps the permanent-conversation welcome regardless of pending datasets', async () => {
    mockDatasets.value = [dataset('uploading')]
    const text = (await mountThread('permanent')).text()

    expect(text).toContain('Welcome to')
    expect(text).not.toContain(PENDING)
  })
})
