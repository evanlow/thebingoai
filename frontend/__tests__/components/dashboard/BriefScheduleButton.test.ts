import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

// ── Stub auto-imports ────────────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('onMounted', onMounted)
vi.stubGlobal('onBeforeUnmount', onBeforeUnmount)
vi.mock('lucide-vue-next', () => ({
  CalendarClock: { render: () => null },
  Check: { render: () => null },
}))

const setBriefSchedule = vi.fn().mockResolvedValue({})
const removeBriefSchedule = vi.fn().mockResolvedValue({})
vi.mock('~/composables/useApi', () => ({
  useApi: () => ({ dashboards: { setBriefSchedule, removeBriefSchedule } }),
}))

import BriefScheduleButton from '~/components/dashboard/BriefScheduleButton.vue'

function optionButton(label: string): HTMLButtonElement {
  const btns = Array.from(document.querySelectorAll('button'))
  return btns.find(b => b.textContent?.trim() === label) as HTMLButtonElement
}

describe('BriefScheduleButton', () => {
  beforeEach(() => {
    setBriefSchedule.mockClear()
    removeBriefSchedule.mockClear()
    document.body.innerHTML = ''
  })

  it('posts a preset for Daily', async () => {
    mount(BriefScheduleButton, { props: { dashboardId: 7 }, attachTo: document.body })
    document.querySelector('button')!.click() // open dropdown
    await flushPromises()
    optionButton('Daily').click()
    await flushPromises()
    expect(setBriefSchedule).toHaveBeenCalledWith(7, { schedule_type: 'preset', schedule_value: 'daily' })
  })

  it('posts a cron expression for Monthly (no preset)', async () => {
    mount(BriefScheduleButton, { props: { dashboardId: 7 }, attachTo: document.body })
    document.querySelector('button')!.click()
    await flushPromises()
    optionButton('Monthly').click()
    await flushPromises()
    expect(setBriefSchedule).toHaveBeenCalledWith(7, { schedule_type: 'cron', schedule_value: '0 9 1 * *' })
  })

  it('removes the schedule on Turn off after one is set', async () => {
    mount(BriefScheduleButton, { props: { dashboardId: 7 }, attachTo: document.body })
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
})
