import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, computed, onMounted } from 'vue'

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('onMounted', onMounted)
vi.mock('lucide-vue-next', () => ({ Newspaper: { render: () => null } }))

const briefings = ref<any[]>([])
const ensure = vi.fn()
const loaded = ref(false)
const refresh = vi.fn()
vi.mock('~/composables/useDashboardBriefings', () => ({
  useDashboardBriefings: () => ({ briefings, ensure, loaded, refresh }),
}))

import DashboardBriefsButton from '~/components/dashboard/DashboardBriefsButton.vue'

describe('DashboardBriefsButton', () => {
  beforeEach(() => { briefings.value = []; ensure.mockClear(); loaded.value = false; refresh.mockClear() })

  it('renders nothing when there are no briefings', async () => {
    const wrapper = mount(DashboardBriefsButton, { props: { dashboardId: 1 } })
    await flushPromises()
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('renders a button and emits open when briefings exist', async () => {
    briefings.value = [{ id: 1 }]
    const wrapper = mount(DashboardBriefsButton, { props: { dashboardId: 1 } })
    await flushPromises()
    const btn = wrapper.get('button')
    expect(btn.text()).toMatch(/previous briefs/i)
    await btn.trigger('click')
    expect(wrapper.emitted('open')).toBeTruthy()
  })

  it('revalidates on mount when the list is already loaded', async () => {
    loaded.value = true
    mount(DashboardBriefsButton, { props: { dashboardId: 1 } })
    await flushPromises()
    expect(refresh).toHaveBeenCalled()
  })
})
