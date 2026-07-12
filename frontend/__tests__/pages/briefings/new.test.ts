import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, onMounted } from 'vue'

// new.vue POSTs /brief on mount, then replaces the route with the real briefing id.
// On failure (e.g. 402) it shows the error inline instead of redirecting.

vi.stubGlobal('ref', ref)
vi.stubGlobal('onMounted', onMounted)

const mockFetch = vi.fn()
vi.stubGlobal('useApi', () => ({ fetchWithRefresh: mockFetch }))

const mockNavigate = vi.fn()
vi.stubGlobal('navigateTo', mockNavigate)

const mockRefreshBriefings = vi.fn()
vi.stubGlobal('useBriefingsList', () => ({ refresh: mockRefreshBriefings }))

let query: Record<string, any> = {}
vi.stubGlobal('useRoute', () => ({ query }))

const { trackEventMock } = vi.hoisted(() => ({ trackEventMock: vi.fn() }))
vi.mock('~/utils/analytics', () => ({ trackEvent: trackEventMock }))

import NewBriefing from '~/pages/briefings/new.vue'

describe('briefings/new', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    mockNavigate.mockReset()
    mockRefreshBriefings.mockReset()
    query = { dashboard_id: '40' }
  })

  it('POSTs the brief and replaces to the real briefing id', async () => {
    mockFetch.mockResolvedValue({ briefing_id: 46, status: 'generating' })
    mount(NewBriefing, { attachTo: document.body })
    await flushPromises()

    expect(mockFetch).toHaveBeenCalledWith('/api/dashboards/40/brief', { method: 'POST' })
    expect(mockRefreshBriefings).toHaveBeenCalledTimes(1)
    expect(mockNavigate).toHaveBeenCalledWith('/briefings/46', { replace: true })
    document.body.innerHTML = ''
  })

  it('shows the 402 detail.message and does not redirect when out of credits', async () => {
    mockFetch.mockRejectedValue({
      data: { detail: { error_code: 'insufficient_credits', cap: 'user_daily', message: 'Daily credits used up.' } },
    })
    mount(NewBriefing, { attachTo: document.body })
    await flushPromises()

    expect(mockNavigate).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('Daily credits used up.')
    document.body.innerHTML = ''
  })

  it('fires GA4 briefing_create with the numeric dashboard id on success', async () => {
    trackEventMock.mockClear()
    mockFetch.mockResolvedValue({ briefing_id: 46, status: 'generating' })
    mount(NewBriefing, { attachTo: document.body })
    await flushPromises()

    expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('briefing_create', { dashboard_id: 40 })
    document.body.innerHTML = ''
  })

  it('fires no GA4 event when the POST fails', async () => {
    trackEventMock.mockClear()
    mockFetch.mockRejectedValue({ data: { detail: 'nope' } })
    mount(NewBriefing, { attachTo: document.body })
    await flushPromises()

    expect(trackEventMock).not.toHaveBeenCalled()
    document.body.innerHTML = ''
  })

  it('errors without POSTing when dashboard_id is missing', async () => {
    query = {}
    mount(NewBriefing, { attachTo: document.body })
    await flushPromises()

    expect(mockFetch).not.toHaveBeenCalled()
    expect(mockNavigate).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('Missing dashboard id.')
    document.body.innerHTML = ''
  })
})
