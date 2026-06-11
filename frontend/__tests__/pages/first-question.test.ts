import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// ── Nuxt auto-import stubs ──────────────────────────────────────────────
const routeQuery = { value: {} as Record<string, string> }
const navigateTo = vi.fn()
let chatStore: { pendingConnectionIds: number[]; inputText: string }
const listMock = vi.fn()

vi.stubGlobal('definePageMeta', vi.fn())
vi.stubGlobal('navigateTo', navigateTo)
vi.stubGlobal('useRoute', () => ({ query: routeQuery.value }))
vi.stubGlobal('useApi', () => ({ connections: { list: listMock } }))
vi.stubGlobal('useChatStore', () => chatStore)
vi.stubGlobal('ref', (val: any) => {
  const { ref: vueRef } = require('vue')
  return vueRef(val)
})
vi.stubGlobal('onMounted', (fn: any) => {
  const { onMounted: vueOnMounted } = require('vue')
  return vueOnMounted(fn)
})

import FirstQuestion from '~/pages/first-question.vue'

const stubs = { AuthBrandingPanel: { template: '<div />', props: ['step', 'stepContext'] } }

interface Conn {
  id: number
  name: string
  db_type: string
  table_count: number | null
  source_filename: string | null
  is_ephemeral: boolean
  profiling_status: string | null
}

function makeConn(overrides: Partial<Conn> = {}): Conn {
  return {
    id: 1,
    name: 'Prod DB',
    db_type: 'postgres',
    table_count: 4,
    source_filename: null,
    is_ephemeral: false,
    profiling_status: 'ready',
    ...overrides,
  }
}

// Deferred promise so we can control when the connections list resolves.
function deferred<T>() {
  let resolve!: (v: T) => void
  const promise = new Promise<T>((r) => { resolve = r })
  return { promise, resolve }
}

const sendBtn = (wrapper: any) =>
  wrapper.findAll('button').find((b: any) => b.text().trim() === 'Send')

describe('first-question page', () => {
  beforeEach(() => {
    routeQuery.value = {}
    chatStore = { pendingConnectionIds: [], inputText: '' }
    vi.clearAllMocks()
  })

  it('scopes to the route-query connection once the list resolves (happy path)', async () => {
    routeQuery.value = { connection: '5' }
    listMock.mockResolvedValue([makeConn({ id: 5, name: 'Chosen' })])

    const wrapper = mount(FirstQuestion, { global: { stubs } })
    await flushPromises()

    await wrapper.find('textarea').setValue('how many users?')
    await sendBtn(wrapper)!.trigger('click')

    expect(chatStore.pendingConnectionIds).toEqual([5])
    expect(chatStore.inputText).toBe('how many users?')
    expect(navigateTo).toHaveBeenCalledWith('/chat')
  })

  it('scopes from the route query even when Send is clicked before the list resolves (race guard)', async () => {
    routeQuery.value = { connection: '5' }
    const d = deferred<Conn[]>()
    listMock.mockReturnValue(d.promise)

    const wrapper = mount(FirstQuestion, { global: { stubs } })
    // Do NOT flush — list fetch is still pending, recentConnection is null.

    await wrapper.find('textarea').setValue('first question')
    await sendBtn(wrapper)!.trigger('click')

    expect(chatStore.pendingConnectionIds).toEqual([5])
    expect(navigateTo).toHaveBeenCalledWith('/chat')

    // Let the dangling fetch resolve so no unhandled promise leaks.
    d.resolve([makeConn({ id: 5 })])
    await flushPromises()
  })

  it('falls back to the most recent non-ephemeral connection when there is no route query', async () => {
    routeQuery.value = {}
    listMock.mockResolvedValue([
      makeConn({ id: 1, is_ephemeral: false }),
      makeConn({ id: 2, is_ephemeral: true }),
      makeConn({ id: 3, is_ephemeral: false }),
    ])

    const wrapper = mount(FirstQuestion, { global: { stubs } })
    await flushPromises()

    await wrapper.find('textarea').setValue('overview please')
    await sendBtn(wrapper)!.trigger('click')

    expect(chatStore.pendingConnectionIds).toEqual([3])
  })

  it('does not navigate when the question is empty', async () => {
    routeQuery.value = { connection: '5' }
    listMock.mockResolvedValue([makeConn({ id: 5 })])

    const wrapper = mount(FirstQuestion, { global: { stubs } })
    await flushPromises()

    await sendBtn(wrapper)!.trigger('click')

    expect(navigateTo).not.toHaveBeenCalled()
    expect(chatStore.pendingConnectionIds).toEqual([])
  })
})
