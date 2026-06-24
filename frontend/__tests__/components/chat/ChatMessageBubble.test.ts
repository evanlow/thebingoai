import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, computed, reactive } from 'vue'

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('reactive', reactive)

// Stub Nuxt auto-imported composables used by the bubble
vi.stubGlobal('useChatStore', () => ({ isStreaming: false, messages: [], skillSuggestions: [] }))
vi.stubGlobal('useAuthStore', () => ({ user: { email: 'test@example.com' } }))
vi.stubGlobal('useApi', () => ({ skills: { respondToSuggestion: vi.fn() } }))
vi.stubGlobal('useMentions', () => ({ resolvedMentions: { value: new Map() } }))
vi.stubGlobal('navigateTo', vi.fn())

// Stub Pinia chat store used by the bubble (matches plan + protects against explicit import paths)
vi.mock('~/stores/chat', () => ({
  useChatStore: () => ({ isStreaming: false, messages: [], skillSuggestions: [] }),
}))

vi.mock('~/stores/dashboard', () => ({
  useDashboardStore: () => ({}),
}))

// Stub markdown renderer + briefing/skill children to avoid pulling their deps
vi.mock('~/components/ui/UiMarkdownRenderer.vue', () => ({
  default: { name: 'UiMarkdownRenderer', props: ['content'], template: '<div />' },
}))
vi.mock('~/components/chat/ChatSkillSuggestionCard.vue', () => ({
  default: { name: 'ChatSkillSuggestionCard', template: '<div />' },
}))
vi.mock('~/components/briefing/BriefingCard.vue', () => ({
  default: { name: 'BriefingCard', template: '<div />' },
}))

import ChatMessageBubble from '~/components/chat/ChatMessageBubble.vue'

const assistantMsg = {
  id: 'm1',
  role: 'assistant',
  content: 'Hello',
  source: 'chat',
  briefing_id: null,
}

describe('ChatMessageBubble', () => {
  function withChatStore(state: { isStreaming: boolean; messages?: any[] }) {
    vi.stubGlobal('useChatStore', () => ({
      isStreaming: state.isStreaming,
      messages: state.messages ?? [],
    }))
  }

  beforeEach(() => {
    withChatStore({ isStreaming: false })
  })

  it('renders both theme-aware logos for assistant avatar', () => {
    const wrapper = mount(ChatMessageBubble, {
      props: {
        message: assistantMsg,
        showActions: false,
        actionType: null,
        isLast: false,
        agentName: 'Bingo',
      },
    })
    const imgs = wrapper.findAll('img')
    const norm = (s: string | undefined) => (s ?? '').replace(/%20/g, ' ')
    const light = imgs.find(i => norm(i.attributes('src')) === '/logo/BINGO Logo Design_FA_Icon.png')
    const dark = imgs.find(i => norm(i.attributes('src')) === '/logo/BINGO Logo Design_FA_Icon_W.png')
    expect(light).toBeTruthy()
    expect(dark).toBeTruthy()
    expect(light!.classes()).toContain('dark:hidden')
    expect(dark!.classes()).toContain('hidden')
    expect(dark!.classes()).toContain('dark:block')
  })

  it('declares an agentAvatarUrl prop (custom agent avatar, passed by ChatThread)', () => {
    const wrapper = mount(ChatMessageBubble, {
      props: {
        message: assistantMsg,
        showActions: false,
        actionType: null,
        isLast: false,
        agentName: 'Bingo',
      },
    })
    const propsDef = (wrapper.vm as any).$options.props ?? {}
    // Positive control — if propsDef ever collapses to {} due to a compiler change,
    // this assertion fails first, preventing a false-positive pass below.
    expect('message' in propsDef).toBe(true)
    expect('agentAvatarUrl' in propsDef).toBe(true)
  })

  it('applies avatar-spin to the avatar wrapper when streaming and message empty (last bubble)', () => {
    withChatStore({ isStreaming: true })
    const wrapper = mount(ChatMessageBubble, {
      props: {
        message: { ...assistantMsg, content: '' },
        showActions: false,
        actionType: null,
        isLast: true,
        agentName: 'Bingo',
      },
    })
    const lightImg = wrapper.findAll('img').find(
      i => (i.attributes('src') ?? '').replace(/%20/g, ' ') === '/logo/BINGO Logo Design_FA_Icon.png'
    )!
    const avatarWrapper = lightImg.element.parentElement!
    expect(avatarWrapper.className).toContain('avatar-spin')
    expect(wrapper.find('.typing-indicator').exists()).toBe(false)
    expect(wrapper.findAll('.typing-dot').length).toBe(0)
  })

  it('does not apply avatar-spin when the message has content', () => {
    withChatStore({ isStreaming: true })
    const wrapper = mount(ChatMessageBubble, {
      props: {
        message: { ...assistantMsg, content: 'Hello' },
        showActions: false,
        actionType: null,
        isLast: true,
        agentName: 'Bingo',
      },
    })
    const lightImg = wrapper.findAll('img').find(
      i => (i.attributes('src') ?? '').replace(/%20/g, ' ') === '/logo/BINGO Logo Design_FA_Icon.png'
    )!
    const avatarWrapper = lightImg.element.parentElement!
    expect(avatarWrapper.className).not.toContain('avatar-spin')
  })
})

describe('ChatMessageBubble — reasoning steps toggle', () => {
  const agentSteps = [
    { step_type: 'reasoning', content: { text: 'thinking' } },
    { step_type: 'tool_call', tool_name: 'get_table_schema', content: {} },
    { step_type: 'tool_result', content: {} },
  ]

  beforeEach(() => {
    vi.stubGlobal('useChatStore', () => ({ isStreaming: false, messages: [] }))
  })

  // ChatReasoningTree is auto-imported in the app; stub it explicitly (declaring the
  // `message` prop) so we can both detect it and read the prop it receives.
  const ChatReasoningTreeStub = {
    name: 'ChatReasoningTree',
    props: ['message'],
    template: '<div class="crt-stub" />',
  }

  function mountBubble(message: any) {
    return mount(ChatMessageBubble, {
      props: { message, showActions: false, actionType: null, isLast: false, agentName: 'Bingo' },
      global: { stubs: { ChatReasoningTree: ChatReasoningTreeStub } },
    })
  }

  // The reasoning toggle is the only button rendered in this bare assistant bubble.
  const reasoningButton = (wrapper: any) =>
    wrapper.findAll('button').find((b: any) => b.text().includes('reasoning step'))

  it('shows the step count, excluding tool_result steps', () => {
    const wrapper = mountBubble({ ...assistantMsg, agent_steps: agentSteps })
    const btn = reasoningButton(wrapper)
    expect(btn).toBeTruthy()
    // reasoning + tool_call = 2; tool_result filtered out
    expect(btn!.text()).toContain('2 reasoning steps')
  })

  it('uses the singular label for a single step', () => {
    const wrapper = mountBubble({
      ...assistantMsg,
      agent_steps: [{ step_type: 'reasoning', content: { text: 'x' } }],
    })
    expect(reasoningButton(wrapper)!.text()).toContain('1 reasoning step')
    expect(reasoningButton(wrapper)!.text()).not.toContain('1 reasoning steps')
  })

  it('renders the tree collapsed by default and expands on click, collapses on second click', async () => {
    const wrapper = mountBubble({ ...assistantMsg, agent_steps: agentSteps })
    expect(wrapper.findComponent({ name: 'ChatReasoningTree' }).exists()).toBe(false)

    await reasoningButton(wrapper)!.trigger('click')
    const tree = wrapper.findComponent({ name: 'ChatReasoningTree' })
    expect(tree.exists()).toBe(true)
    expect(tree.props('message')).toMatchObject({ id: 'm1' })

    await reasoningButton(wrapper)!.trigger('click')
    expect(wrapper.findComponent({ name: 'ChatReasoningTree' }).exists()).toBe(false)
  })

  it('hides the reasoning button while steps_log is present (live streaming view)', () => {
    const wrapper = mountBubble({
      ...assistantMsg,
      agent_steps: agentSteps,
      steps_log: ['step a', 'step b'],
    })
    expect(reasoningButton(wrapper)).toBeUndefined()
    // live steps_log block renders its own toggle instead
    expect(wrapper.text()).toContain('2 steps')
  })

  it('renders no reasoning button when the message has no steps', () => {
    const wrapper = mountBubble({ ...assistantMsg })
    expect(reasoningButton(wrapper)).toBeUndefined()
  })
})
