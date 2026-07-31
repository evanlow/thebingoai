/**
 * Dataset cards now live in the transcript, attached to the user message whose
 * files they describe, rather than floating at the bottom of the thread. The
 * empty state is back to a plain "no messages yet" check.
 */
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
  ChatMessageBubble: {
    props: ['message'],
    template: '<div class="bubble" :data-id="message.id" />',
  },
  DatasetProgressCard: {
    props: ['dataset'],
    template: '<div class="progress-card" :data-name="dataset.name" :data-step="dataset.step" />',
  },
}

const IDLE = 'Ask me anything about your data'

function dataset(step: string, connectionId = 1, name = 'HR_dataset.csv') {
  return {
    name, size: 1, fileId: `connection:${connectionId}`, connectionId, step, error: null,
  }
}

/** A user message carrying dataset attachments, as `_resolve_attachments` stores them. */
function userMessageWith(connectionIds: number[], names: string[] = []) {
  return {
    id: 'm1',
    role: 'user',
    content: 'what is in here?',
    created_at: '2026-07-26T10:00:00Z',
    attachments: connectionIds.map((id, i) => ({
      file_id: `connection:${id}`,
      name: names[i] ?? `f${id}.csv`,
      size: 1,
      type: 'text/csv',
      preview_url: null,
      status: 'ready',
    })),
  }
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

describe('ChatThread — empty state', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // useAgentProfile reaches for a Pinia store during ChatThread setup
    setActivePinia(createPinia())
    mockDatasets.value = []
  })

  it('shows the idle prompt when the thread has no messages', async () => {
    expect((await mountThread()).text()).toContain(IDLE)
  })

  it('still resolves correctly with datasets around but no messages', async () => {
    // The old condition also consulted `datasetsPending`, which no longer exists.
    // A thread cannot show cards without messages — the cards hang off a message.
    mockDatasets.value = [dataset('profiling')]
    const wrapper = await mountThread()

    expect(wrapper.text()).toContain(IDLE)
    expect(wrapper.find('.progress-card').exists()).toBe(false)
  })

  it('drops the empty state once a message exists', async () => {
    const wrapper = await mountThread('task', [userMessageWith([])])

    expect(wrapper.text()).not.toContain(IDLE)
    expect(wrapper.find('.bubble').exists()).toBe(true)
  })

  it('keeps the permanent-conversation welcome', async () => {
    mockDatasets.value = [dataset('uploading')]
    expect((await mountThread('permanent')).text()).toContain('Welcome to')
  })
})

describe('ChatThread — dataset cards in the transcript', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    mockDatasets.value = []
  })

  it('renders one card per dataset attachment, before that message bubble', async () => {
    mockDatasets.value = [dataset('ready', 1, 'first.csv'), dataset('profiling', 2, 'second.csv')]
    const wrapper = await mountThread('task', [userMessageWith([1, 2])])

    const cards = wrapper.findAll('.progress-card')
    expect(cards).toHaveLength(2)
    // Attachment order, and both ahead of the bubble.
    expect(cards.map(c => c.attributes('data-name'))).toEqual(['first.csv', 'second.csv'])

    const html = wrapper.html()
    expect(html.indexOf('progress-card')).toBeLessThan(html.indexOf('bubble'))
  })

  it('keeps the cards after documentation lands', async () => {
    // They used to drop out of the thread the moment docs arrived.
    mockDatasets.value = [dataset('ready')]
    const wrapper = await mountThread('task', [userMessageWith([1])], [])

    expect(wrapper.findAll('.progress-card')).toHaveLength(1)
    expect(wrapper.find('.progress-card').attributes('data-step')).toBe('ready')
  })

  it('renders no card for a message with no dataset attachments', async () => {
    mockDatasets.value = [dataset('ready')]
    const wrapper = await mountThread('task', [
      { id: 'm1', role: 'user', content: 'hi', created_at: '2026-07-26T10:00:00Z' },
    ])

    expect(wrapper.findAll('.progress-card')).toHaveLength(0)
  })

  it('ignores non-dataset attachments', async () => {
    mockDatasets.value = [dataset('ready')]
    const wrapper = await mountThread('task', [{
      id: 'm1', role: 'user', content: 'look', created_at: '2026-07-26T10:00:00Z',
      attachments: [{ file_id: 'file-abc', name: 'photo.png', size: 1, type: 'image/png', preview_url: null, status: 'ready' }],
    }])

    expect(wrapper.findAll('.progress-card')).toHaveLength(0)
  })

  it('renders nothing for an attachment whose dataset status is not known yet', async () => {
    mockDatasets.value = []
    const wrapper = await mountThread('task', [userMessageWith([1])])

    expect(wrapper.findAll('.progress-card')).toHaveLength(0)
    expect(wrapper.find('.bubble').exists()).toBe(true)
  })

  it('attaches each message its own cards across two turns', async () => {
    mockDatasets.value = [dataset('ready', 1, 'first.csv'), dataset('documenting', 2, 'second.csv')]
    const wrapper = await mountThread('task', [
      { ...userMessageWith([1], ['first.csv']), id: 'm1' },
      { ...userMessageWith([2], ['second.csv']), id: 'm2' },
    ])

    expect(wrapper.findAll('.progress-card').map(c => c.attributes('data-name')))
      .toEqual(['first.csv', 'second.csv'])
    expect(wrapper.findAll('.bubble')).toHaveLength(2)
  })
})
