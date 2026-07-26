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

function dataset(step: string) {
  return { name: 'HR_dataset.csv', size: 1, fileId: 'f1', connectionId: 1, step, error: null }
}

function makeChatStore(type = 'task', messages: any[] = [], docsPendingThreads: string[] = []) {
  return {
    currentConversation: { type, title: 'Bingo AI' },
    currentThreadId: 'thread-123',
    infoPanelOpen: false,
    messages,
    messagesLoading: false,
    isStreaming: false,
    docsPendingThreads,
    toggleInfoPanel: vi.fn(),
    permanentConversation: type === 'permanent' ? { title: 'Bingo AI' } : null,
  }
}

async function mountThread(type = 'task', messages: any[] = [], docsPendingThreads: string[] = []) {
  vi.stubGlobal('useChatStore', () => makeChatStore(type, messages, docsPendingThreads))
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
    const wrapper = await mountThread('task', [], ['thread-123'])

    expect(wrapper.find('.progress-card').attributes('data-docs')).toBe('pending')
  })

  it('marks the documentation step active once profiling is done and docs are still running', async () => {
    mockDatasets.value = [dataset('ready')]
    const wrapper = await mountThread('task', [], ['thread-123'])

    expect(wrapper.find('.progress-card').attributes('data-docs')).toBe('active')
  })

  it('drops the documentation step for a failed dataset', async () => {
    mockDatasets.value = [dataset('failed'), dataset('uploading')]
    const wrapper = await mountThread('task', [], ['thread-123'])

    const cards = wrapper.findAll('.progress-card')
    expect(cards[0].attributes('data-docs')).toBe('null')
  })

  it('keeps the processing copy after profiling finishes while docs are still generating', async () => {
    // The exact regression: profiling completes seconds before the LLM does, and
    // the copy used to flicker back to the idle prompt in between.
    mockDatasets.value = [dataset('ready')]
    const text = (await mountThread('task', [], ['thread-123'])).text()

    expect(text).toContain(PENDING)
    expect(text).not.toContain(IDLE)
  })

  it('ignores a docs-pending flag belonging to another thread', async () => {
    mockDatasets.value = [dataset('ready')]
    const text = (await mountThread('task', [], ['some-other-thread'])).text()

    expect(text).toContain(IDLE)
    expect(text).not.toContain(PENDING)
  })

  it('renders neither empty state once messages exist', async () => {
    mockDatasets.value = [dataset('profiling')]
    const wrapper = await mountThread('task', [
      { id: 'm1', role: 'assistant', content: 'hi', source: 'dataset_docs', created_at: '2026-07-26T10:00:00Z' },
    ])

    expect(wrapper.text()).not.toContain(PENDING)
    expect(wrapper.text()).not.toContain(IDLE)
    expect(wrapper.find('.bubble').exists()).toBe(true)
  })

  it('keeps the permanent-conversation welcome regardless of pending datasets', async () => {
    mockDatasets.value = [dataset('uploading')]
    const text = (await mountThread('permanent')).text()

    expect(text).toContain('Welcome to')
    expect(text).not.toContain(PENDING)
  })
})
