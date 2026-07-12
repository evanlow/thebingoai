import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, computed, onMounted } from 'vue'

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('onMounted', onMounted)
vi.mock('lucide-vue-next', () => ({ Newspaper: { render: () => null }, X: { render: () => null } }))

const mockNavigate = vi.fn()
vi.stubGlobal('navigateTo', mockNavigate)

const briefings = ref<any[]>([])
const ensure = vi.fn()
const refresh = vi.fn()
const loaded = ref(false)
const loading = ref(false)
const error = ref('')
vi.mock('~/composables/useDashboardBriefings', () => ({
  useDashboardBriefings: () => ({ briefings, ensure, refresh, loaded, loading, error }),
}))

import DashboardBriefsPanel from '~/components/dashboard/DashboardBriefsPanel.vue'

describe('DashboardBriefsPanel', () => {
  beforeEach(() => {
    briefings.value = []; ensure.mockClear(); refresh.mockClear()
    mockNavigate.mockReset(); loaded.value = false; error.value = ''
  })

  it('emits close when the close button is clicked', async () => {
    const wrapper = mount(DashboardBriefsPanel, { props: { dashboardId: 1 } })
    await flushPromises()
    await wrapper.get('[data-testid="briefs-panel-close"]').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('navigates to the briefing page when a row is clicked', async () => {
    briefings.value = [{ id: 5, status: 'ready', payload: { headline: 'H' }, created_at: '2026-05-17T10:00:00Z' }]
    const wrapper = mount(DashboardBriefsPanel, { props: { dashboardId: 1 } })
    await flushPromises()
    await wrapper.get('[data-testid="briefs-row"]').trigger('click')
    expect(mockNavigate).toHaveBeenCalledWith('/briefings/5')
  })
})
