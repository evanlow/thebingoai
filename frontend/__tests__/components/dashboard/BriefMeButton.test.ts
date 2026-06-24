import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

// ── Stub auto-imports ────────────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.mock('lucide-vue-next', () => ({ Sparkles: { render: () => null, setup: () => null } }))

const mockNavigate = vi.fn()
vi.stubGlobal('navigateTo', mockNavigate)

import BriefMeButton from '~/components/dashboard/BriefMeButton.vue'

function clickButton() {
  const btn = document.querySelector('button')
  if (btn) btn.click()
}

describe('BriefMeButton', () => {
  beforeEach(() => {
    mockNavigate.mockReset()
  })

  it('renders "Brief me" label', () => {
    mount(BriefMeButton, { props: { dashboardId: 1 }, attachTo: document.body })
    const btn = document.querySelector('button')!
    expect(btn.textContent).toMatch(/Brief me/i)
    document.body.innerHTML = ''
  })

  it('navigates to the generating page with the dashboard id on click', () => {
    mount(BriefMeButton, { props: { dashboardId: 1 }, attachTo: document.body })
    clickButton()
    expect(mockNavigate).toHaveBeenCalledWith('/briefings/new?dashboard_id=1')
    document.body.innerHTML = ''
  })

  it('uses the correct dashboardId prop', () => {
    mount(BriefMeButton, { props: { dashboardId: 42 }, attachTo: document.body })
    clickButton()
    expect(mockNavigate).toHaveBeenCalledWith('/briefings/new?dashboard_id=42')
    document.body.innerHTML = ''
  })
})
