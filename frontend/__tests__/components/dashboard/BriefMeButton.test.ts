import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

// ── Stub auto-imports ────────────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('onMounted', onMounted)
vi.stubGlobal('onBeforeUnmount', onBeforeUnmount)
vi.mock('lucide-vue-next', () => ({
  Sparkles: { render: () => null },
  Check: { render: () => null },
}))

const mockNavigate = vi.fn()
vi.stubGlobal('navigateTo', mockNavigate)

const setBriefSchedule = vi.fn().mockResolvedValue({})
const removeBriefSchedule = vi.fn().mockResolvedValue({})
const getBriefSchedule = vi.fn().mockResolvedValue(null)
vi.mock('~/composables/useApi', () => ({
  useApi: () => ({ dashboards: { setBriefSchedule, removeBriefSchedule, getBriefSchedule } }),
}))

import BriefMeButton from '~/components/dashboard/BriefMeButton.vue'

function optionButton(label: string): HTMLButtonElement {
  const btns = Array.from(document.querySelectorAll('button'))
  return btns.find(b => b.textContent?.trim() === label) as HTMLButtonElement
}

describe('BriefMeButton', () => {
  beforeEach(() => {
    mockNavigate.mockReset()
    setBriefSchedule.mockClear()
    removeBriefSchedule.mockClear()
    getBriefSchedule.mockReset()
    getBriefSchedule.mockResolvedValue(null)
    document.body.innerHTML = ''
  })

  it('renders "Brief me" label', () => {
    mount(BriefMeButton, { props: { dashboardId: 1 }, attachTo: document.body })
    const btn = document.querySelector('button')!
    expect(btn.textContent).toMatch(/Brief me/i)
  })

  it('navigates to the generating page with the dashboard id on "Now"', async () => {
    mount(BriefMeButton, { props: { dashboardId: 42 }, attachTo: document.body })
    document.querySelector('button')!.click() // open dropdown
    await flushPromises()
    optionButton('Now').click()
    expect(mockNavigate).toHaveBeenCalledWith('/briefings/new?dashboard_id=42')
  })

  it('posts a preset for Daily', async () => {
    mount(BriefMeButton, { props: { dashboardId: 7 }, attachTo: document.body })
    document.querySelector('button')!.click()
    await flushPromises()
    optionButton('Daily').click()
    await flushPromises()
    expect(setBriefSchedule).toHaveBeenCalledWith(7, { schedule_type: 'preset', schedule_value: 'daily' })
  })

  it('posts a cron expression for Monthly (no preset)', async () => {
    mount(BriefMeButton, { props: { dashboardId: 7 }, attachTo: document.body })
    document.querySelector('button')!.click()
    await flushPromises()
    optionButton('Monthly').click()
    await flushPromises()
    expect(setBriefSchedule).toHaveBeenCalledWith(7, { schedule_type: 'cron', schedule_value: '0 9 1 * *' })
  })

  it('removes the schedule on Turn off after one is set', async () => {
    mount(BriefMeButton, { props: { dashboardId: 7 }, attachTo: document.body })
    document.querySelector('button')!.click()
    await flushPromises()
    optionButton('Weekly').click()
    await flushPromises()
    document.querySelector('button')!.click() // reopen
    await flushPromises()
    optionButton('Turn off').click()
    await flushPromises()
    expect(removeBriefSchedule).toHaveBeenCalledWith(7)
  })

  it('hydrates the active highlight + checked option from the server on mount', async () => {
    getBriefSchedule.mockResolvedValue({ schedule_type: 'preset', schedule_value: 'daily', is_active: true })
    mount(BriefMeButton, { props: { dashboardId: 7 }, attachTo: document.body })
    await flushPromises()
    const trigger = document.querySelector('button')!
    expect(trigger.classList.contains('hdr-btn--active')).toBe(true)
    trigger.click() // open dropdown
    await flushPromises()
    expect(optionButton('Turn off').disabled).toBe(false)
  })

  it('stays inactive with Turn off disabled when no schedule exists', async () => {
    getBriefSchedule.mockResolvedValue(null)
    mount(BriefMeButton, { props: { dashboardId: 7 }, attachTo: document.body })
    await flushPromises()
    const trigger = document.querySelector('button')!
    expect(trigger.classList.contains('hdr-btn--active')).toBe(false)
    trigger.click()
    await flushPromises()
    expect(optionButton('Turn off').disabled).toBe(true)
  })
})
