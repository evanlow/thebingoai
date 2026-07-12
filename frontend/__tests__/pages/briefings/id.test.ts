import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, computed, watch } from 'vue'

// Regression: a briefing whose status is 'generating' has payload === null.
// The Ready branch derefs briefing.payload!.headline, so without a dedicated
// generating branch the page crashes on render (bit twice). Lock both states.

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', watch)
vi.stubGlobal('useRoute', () => ({ params: { id: '48' } }))

let briefingValue: any = null
let loadingValue = false
vi.stubGlobal('useBriefing', () => ({
  briefing: ref(briefingValue),
  loading: ref(loadingValue),
  refresh: vi.fn(),
}))
vi.stubGlobal('useBriefingPdf', () => ({
  exporting: ref(false),
  markWidgetLoaded: vi.fn(),
  resetWidgets: vi.fn(),
  exportPdf: vi.fn(),
}))

const navigateToMock = vi.fn()
vi.stubGlobal('navigateTo', navigateToMock)

import BriefingPage from '~/pages/briefings/[id].vue'

const mountPage = () =>
  mount(BriefingPage, {
    attachTo: document.body,
    global: { stubs: { BriefingWidgetEmbed: true } },
  })

describe('briefings/[id]', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    loadingValue = false
    navigateToMock.mockClear()
  })

  it('does not render the back button before the briefing loads', () => {
    briefingValue = null
    loadingValue = true
    mountPage()
    expect(document.body.querySelector('[data-testid="briefing-back"]')).toBeNull()
  })

  it('renders the generating skeleton without crashing when payload is null', () => {
    briefingValue = { id: 48, status: 'generating', payload: null, dashboard_id: 40, created_at: '2026-06-19T00:00:00Z' }
    expect(() => mountPage()).not.toThrow()
    expect(document.body.textContent).toContain('Generating your briefing')
    expect(document.body.textContent).not.toContain('Compiled by Bingo')
  })

  it('renders the headline once the briefing is ready', () => {
    briefingValue = {
      id: 48,
      status: 'ready',
      dashboard_id: 40,
      created_at: '2026-06-19T00:00:00Z',
      date_range_from: null,
      date_range_to: null,
      payload: { headline: 'Sales up 12%', deck: 'Strong quarter', kpis: [], sections: [], key_takeaways: ['Grow'] },
    }
    mountPage()
    expect(document.body.textContent).toContain('Sales up 12%')
    expect(document.body.textContent).toContain('Compiled by Bingo')
  })

  it('renders a back-to-dashboard button once the briefing is ready', () => {
    briefingValue = {
      id: 48,
      status: 'ready',
      dashboard_id: 42,
      created_at: '2026-06-19T00:00:00Z',
      date_range_from: null,
      date_range_to: null,
      payload: { headline: 'Sales up 12%', deck: 'Strong quarter', kpis: [], sections: [], key_takeaways: ['Grow'] },
    }
    mountPage()
    const backBtn = document.body.querySelector('[data-testid="briefing-back"]')
    expect(backBtn).not.toBeNull()
    expect(backBtn!.textContent).toMatch(/dashboard/i)
  })

  it('navigates to the originating dashboard when the back button is clicked', async () => {
    briefingValue = {
      id: 48,
      status: 'ready',
      dashboard_id: 42,
      created_at: '2026-06-19T00:00:00Z',
      date_range_from: null,
      date_range_to: null,
      payload: { headline: 'Sales up 12%', deck: 'Strong quarter', kpis: [], sections: [], key_takeaways: ['Grow'] },
    }
    const wrapper = mountPage()
    await wrapper.find('[data-testid="briefing-back"]').trigger('click')
    expect(navigateToMock).toHaveBeenCalledWith('/dashboard?id=42')
  })
})
