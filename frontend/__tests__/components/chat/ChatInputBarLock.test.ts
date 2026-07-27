/**
 * The composer's send gate and its "reading your data" lock.
 *
 * Attaching a dataset no longer uploads anything, so the send button must stay
 * enabled while a file sits in 'attached' — pressing Enter is what starts the
 * upload. Once the turn is in flight the whole composer locks until every
 * dataset is terminal, documentation included.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, computed, reactive, nextTick } from 'vue'

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('reactive', reactive)
vi.stubGlobal('nextTick', nextTick)
vi.stubGlobal('watch', vi.fn())
vi.stubGlobal('onMounted', vi.fn())
vi.stubGlobal('onUnmounted', vi.fn())
vi.stubGlobal('onBeforeUnmount', vi.fn())

const chatStore = reactive({
  inputText: '',
  isStreaming: false,
  messages: [] as any[],
  currentConversation: null as any,
})
vi.stubGlobal('useChatStore', () => chatStore)

// A plain object, not reactive(): reactive() unwraps nested refs, so the tests
// would be assigning to a boolean instead of the ref the component reads.
const fileState = {
  attachedFiles: ref([] as any[]),
  allFilesReady: ref(false),
  canSubmitFiles: ref(true),
  hasPendingDatasets: ref(false),
}
vi.stubGlobal('useChatFileUpload', () => ({
  attachedFiles: fileState.attachedFiles,
  allFilesReady: fileState.allFilesReady,
  canSubmitFiles: fileState.canSubmitFiles,
  hasPendingDatasets: fileState.hasPendingDatasets,
  addFiles: vi.fn(),
  removeFile: vi.fn(),
}))

vi.stubGlobal('useCreditBalance', () => ({
  isExhausted: ref(false), remaining: ref(100),
  orgExhausted: ref(false), isUnlimited: ref(false),
}))
vi.stubGlobal('useFeatureConfig', () => ({ config: ref({}) }))
vi.stubGlobal('useWorkspaceStore', () => ({}))
vi.mock('~/stores/workspace', () => ({ useWorkspaceStore: () => ({}) }))
vi.mock('~/composables/useMentions', () => ({
  useMentions: () => ({
    resolvedMentions: { value: new Map() },
    clearResolvedMentions: vi.fn(),
    registerMention: vi.fn(),
    searchMentions: vi.fn(async () => []),
  }),
}))

import ChatInputBar from '~/components/chat/ChatInputBar.vue'

function mountBar() {
  return mount(ChatInputBar, {
    global: {
      stubs: {
        UiDialog: true,
        ChatFilePreview: true,
        ChatMentionPanel: true,
        Scissors: true, ArrowUp: true, Paperclip: true, AtSign: true,
      },
    },
  })
}

const submitBtn = (w: any) => w.find('button[type="submit"]')

describe('ChatInputBar — send gate', () => {
  beforeEach(() => {
    chatStore.inputText = ''
    chatStore.isStreaming = false
    chatStore.messages = []
    fileState.attachedFiles.value = []
    fileState.allFilesReady.value = false
    fileState.canSubmitFiles.value = true
    fileState.hasPendingDatasets.value = false
  })

  it('is disabled with neither text nor a dataset', () => {
    expect(submitBtn(mountBar()).attributes('disabled')).toBeDefined()
  })

  it('is enabled with a dataset attached and no text', async () => {
    fileState.hasPendingDatasets.value = true
    const w = mountBar()
    await nextTick()
    // Enter is what starts the upload — gating on "uploaded" would deadlock.
    expect(submitBtn(w).attributes('disabled')).toBeUndefined()
  })

  it('is enabled with text and no files', async () => {
    chatStore.inputText = 'hello'
    const w = mountBar()
    await nextTick()
    expect(submitBtn(w).attributes('disabled')).toBeUndefined()
  })

  it('is disabled while a non-dataset file is still transferring', async () => {
    chatStore.inputText = 'hello'
    fileState.canSubmitFiles.value = false
    const w = mountBar()
    await nextTick()
    expect(submitBtn(w).attributes('disabled')).toBeDefined()
  })
})

describe('ChatInputBar — reading-your-data lock', () => {
  beforeEach(() => {
    chatStore.inputText = ''
    chatStore.isStreaming = false
    chatStore.messages = []
    fileState.attachedFiles.value = []
    fileState.allFilesReady.value = false
    fileState.canSubmitFiles.value = true
    fileState.hasPendingDatasets.value = false
  })

  it('locks the editor and shows the waiting label while datasets are non-terminal', async () => {
    chatStore.isStreaming = true
    fileState.allFilesReady.value = false
    const w = mountBar()
    await nextTick()

    expect(w.find('[data-testid="composer-waiting"]').exists()).toBe(true)
    expect(w.find('[role="textbox"]').attributes('contenteditable')).toBe('false')
    expect(submitBtn(w).attributes('disabled')).toBeDefined()
  })

  it('re-enables once every dataset is terminal and the turn ends', async () => {
    chatStore.isStreaming = true
    const w = mountBar()
    await nextTick()
    expect(w.find('[data-testid="composer-waiting"]').exists()).toBe(true)

    fileState.allFilesReady.value = true
    chatStore.isStreaming = false
    chatStore.inputText = 'follow up'
    await nextTick()

    expect(w.find('[data-testid="composer-waiting"]').exists()).toBe(false)
    expect(w.find('[role="textbox"]').attributes('contenteditable')).toBe('true')
    expect(submitBtn(w).attributes('disabled')).toBeUndefined()
  })

  it('shows no waiting label when nothing is streaming', async () => {
    const w = mountBar()
    await nextTick()
    expect(w.find('[data-testid="composer-waiting"]').exists()).toBe(false)
  })
})
