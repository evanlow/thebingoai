import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, computed } from 'vue'

// ── Nuxt auto-import stubs ──────────────────────────────────────────────
const navigateTo = vi.fn()
const listMock = vi.fn()
const getTypesMock = vi.fn()

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('onMounted', (cb: any) => cb())
vi.stubGlobal('definePageMeta', vi.fn())
vi.stubGlobal('navigateTo', navigateTo)
vi.stubGlobal('useApi', () => ({ connections: { list: listMock, getTypes: getTypesMock } }))

import ConnectPage from '~/pages/connect.vue'

const stubs = {
  AuthBrandingPanel: { name: 'AuthBrandingPanel', template: '<div />', props: ['step', 'stepContext'] },
  OnboardingConnectionDialog: {
    name: 'OnboardingConnectionDialog',
    props: ['open', 'connectorType'],
    emits: ['update:open', 'created'],
    template: '<div class="dialog-stub" />',
  },
}

const SAMPLE = {
  id: 1, name: 'Sample Sales', db_type: 'postgres', table_count: 5,
  source_filename: '__bingo_sample__/sales.csv', is_ephemeral: false, profiling_status: 'ready',
}
const PLAIN = {
  id: 2, name: 'Prod', db_type: 'postgres', table_count: 9,
  source_filename: null, is_ephemeral: false, profiling_status: 'ready',
}
const TYPES = [
  { id: 'postgres', display_name: 'PostgreSQL', description: '', default_port: 5432, badge_variant: 'info', version: null, card_meta_items: [] },
  { id: 'mysql', display_name: 'MySQL', description: '', default_port: 3306, badge_variant: 'info', version: null, card_meta_items: [] },
]

async function flush() {
  await new Promise(r => setTimeout(r, 0))
  await new Promise(r => setTimeout(r, 0))
}

const continueBtn = (wrapper: any) =>
  wrapper.findAll('button').find((b: any) => b.text().includes('Continue with'))

describe('connect page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getTypesMock.mockResolvedValue(TYPES)
  })

  it('auto-enables the default connection when a sample exists', async () => {
    listMock.mockResolvedValue([SAMPLE, PLAIN])
    const wrapper = mount(ConnectPage, { global: { stubs } })
    await flush()

    const btn = continueBtn(wrapper)
    expect(btn).toBeTruthy()
    expect((btn!.element as HTMLButtonElement).disabled).toBe(false)
    expect(btn!.text()).toContain('Sample Sales')
  })

  it('navigates to first-question with the sample id on the default path', async () => {
    listMock.mockResolvedValue([SAMPLE])
    const wrapper = mount(ConnectPage, { global: { stubs } })
    await flush()

    await continueBtn(wrapper)!.trigger('click')

    expect(navigateTo).toHaveBeenCalledWith('/first-question?connection=1')
  })

  it('opens the dialog with the selected connector type', async () => {
    listMock.mockResolvedValue([])
    const wrapper = mount(ConnectPage, { global: { stubs } })
    await flush()

    // Select the PostgreSQL connector card, then continue.
    const pgCard = wrapper.findAll('button').find((b: any) => b.text().includes('PostgreSQL'))
    await pgCard!.trigger('click')
    await continueBtn(wrapper)!.trigger('click')

    const dialog = wrapper.findComponent(stubs.OnboardingConnectionDialog)
    expect(dialog.props('open')).toBe(true)
    expect(dialog.props('connectorType')).toMatchObject({ id: 'postgres' })
    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('navigates to first-question when the dialog reports a created connection', async () => {
    listMock.mockResolvedValue([])
    const wrapper = mount(ConnectPage, { global: { stubs } })
    await flush()

    const dialog = wrapper.findComponent(stubs.OnboardingConnectionDialog)
    dialog.vm.$emit('created', { id: 99 })
    await flush()

    expect(navigateTo).toHaveBeenCalledWith('/first-question?connection=99')
  })
})
