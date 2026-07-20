import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, computed, watch, reactive } from 'vue'

// Regression: a briefing whose status is 'generating' has payload === null.
// The Ready branch derefs briefing.payload!.headline, so without a dedicated
// generating branch the page crashes on render (bit twice). Lock both states.

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', watch)
// Reactive so tests can simulate in-place /briefings/A -> /briefings/B
// navigation (Nuxt reuses the page component on same-route param changes).
const routeParams = reactive({ id: '48' })
vi.stubGlobal('useRoute', () => ({ params: routeParams }))

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

// retry() re-POSTs /brief via useApi
const retryFetchMock = vi.fn()
vi.stubGlobal('useApi', () => ({ fetchWithRefresh: retryFetchMock }))

const { trackEventMock } = vi.hoisted(() => ({ trackEventMock: vi.fn() }))
vi.mock('~/utils/analytics', () => ({ trackEvent: trackEventMock }))

import BriefingPage from '~/pages/briefings/[id].vue'
import BriefingBody from '~/components/briefings/BriefingBody.vue'

const mountPage = () =>
  mount(BriefingPage, {
    attachTo: document.body,
    // BriefingBody is auto-imported by Nuxt at runtime but not under VTU —
    // register it explicitly or its content never renders.
    global: { stubs: { BriefingWidgetEmbed: true }, components: { BriefingBody } },
  })

describe('briefings/[id]', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    loadingValue = false
    navigateToMock.mockClear()
    routeParams.id = '48'
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

  it('renders recommended actions when present in the payload', () => {
    briefingValue = {
      id: 48,
      status: 'ready',
      dashboard_id: 40,
      created_at: '2026-06-19T00:00:00Z',
      date_range_from: null,
      date_range_to: null,
      payload: {
        headline: 'Sales up 12%',
        deck: 'Strong quarter',
        kpis: [],
        sections: [],
        key_takeaways: ['Grow'],
        recommended_actions: ['Ship the fix', 'Review pricing'],
      },
    }
    mountPage()
    expect(document.body.textContent).toContain('Recommended actions')
    expect(document.body.textContent).toContain('Ship the fix')
    expect(document.body.textContent).toContain('Review pricing')
  })

  it('hides the recommended actions block on old briefings without the field', () => {
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
    expect(document.body.textContent).not.toContain('Recommended actions')
  })

  it('retry on a failed briefing fires GA4 briefing_create with the dashboard id', async () => {
    trackEventMock.mockClear()
    retryFetchMock.mockResolvedValue({ briefing_id: 49 })
    briefingValue = {
      id: 48,
      status: 'failed',
      dashboard_id: 42,
      error: 'generation blew up',
      payload: null,
      created_at: '2026-06-19T00:00:00Z',
    }
    const wrapper = mountPage()
    const retryBtn = wrapper.findAll('button').find((b) => b.text() === 'Retry')
    expect(retryBtn).toBeDefined()
    await retryBtn!.trigger('click')
    expect(retryFetchMock).toHaveBeenCalledWith('/api/dashboards/42/brief', { method: 'POST' })
    expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('briefing_create', { dashboard_id: 42 })
  })

  const READY = () => ({
    id: 48,
    status: 'ready',
    dashboard_id: 40,
    created_at: '2026-06-19T00:00:00Z',
    date_range_from: null,
    date_range_to: null,
    payload: { headline: 'Sales up 12%', deck: 'Strong quarter', kpis: [], sections: [], key_takeaways: ['Grow'] },
  })

  it('enabling sharing mints a link and copies it', async () => {
    const writeText = vi.fn()
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    retryFetchMock.mockReset()
    retryFetchMock.mockResolvedValue({
      token: 'tok123',
    })
    briefingValue = READY()

    const wrapper = mountPage()
    await wrapper.find('[data-testid="briefing-share-toggle"]').trigger('click')
    await flushPromises()

    expect(retryFetchMock).toHaveBeenCalledWith('/api/briefings/48/share', { method: 'POST' })
    // No `url` in the response — the page builds it from the browser's own
    // origin (mirrors stores/auth.ts's window.location.origin pattern). The
    // token rides in the FRAGMENT so it never reaches server access logs.
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/share/briefings#tok123`)
  })

  it('surfaces the 400 when a briefing predates chart snapshots', async () => {
    retryFetchMock.mockReset()
    retryFetchMock.mockRejectedValue({
      data: { detail: "This briefing predates chart snapshots and can't be shared. Generate a fresh one." },
    })
    briefingValue = READY()

    const wrapper = mountPage()
    await wrapper.find('[data-testid="briefing-share-toggle"]').trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain('predates chart snapshots')
  })

  it('clicking "Turn off" revokes the share and returns to "Share to web"', async () => {
    const writeText = vi.fn()
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    retryFetchMock.mockReset()
    retryFetchMock.mockResolvedValueOnce({ active: false }) // mount-time GET /share hydration
    retryFetchMock.mockResolvedValueOnce({
      token: 'tok123',
    })
    retryFetchMock.mockResolvedValueOnce(undefined)
    briefingValue = READY()

    const wrapper = mountPage()
    await wrapper.find('[data-testid="briefing-share-toggle"]').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Shared · Copy link')

    const turnOffBtn = wrapper.findAll('button').find((b) => b.text() === 'Turn off')
    expect(turnOffBtn).toBeDefined()
    await turnOffBtn!.trigger('click')
    await flushPromises()

    expect(retryFetchMock).toHaveBeenCalledWith('/api/briefings/48/share', { method: 'DELETE' })
    expect(document.body.textContent).toContain('Share to web')
    expect(document.body.textContent).not.toContain('Shared · Copy link')
  })

  it('surfaces an error when revoking sharing fails', async () => {
    const writeText = vi.fn()
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    retryFetchMock.mockReset()
    retryFetchMock.mockResolvedValueOnce({ active: false }) // mount-time GET /share hydration
    retryFetchMock.mockResolvedValueOnce({
      token: 'tok123',
    })
    retryFetchMock.mockRejectedValueOnce({ data: { detail: 'Server exploded while turning off sharing.' } })
    briefingValue = READY()

    const wrapper = mountPage()
    await wrapper.find('[data-testid="briefing-share-toggle"]').trigger('click')
    await flushPromises()

    const turnOffBtn = wrapper.findAll('button').find((b) => b.text() === 'Turn off')
    expect(turnOffBtn).toBeDefined()
    await turnOffBtn!.trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain('Server exploded while turning off sharing.')
  })

  it('keeps "Turn off" visible after a failed revoke and retries the DELETE on a second click', async () => {
    const writeText = vi.fn()
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    retryFetchMock.mockReset()
    retryFetchMock.mockResolvedValueOnce({ active: false }) // mount-time GET /share hydration
    retryFetchMock.mockResolvedValueOnce({
      token: 'tok123',
    })
    retryFetchMock.mockRejectedValueOnce({ data: { detail: 'Server exploded while turning off sharing.' } })
    retryFetchMock.mockResolvedValueOnce(undefined)
    briefingValue = READY()

    const wrapper = mountPage()
    await wrapper.find('[data-testid="briefing-share-toggle"]').trigger('click')
    await flushPromises()

    let turnOffBtn = wrapper.findAll('button').find((b) => b.text() === 'Turn off')
    expect(turnOffBtn).toBeDefined()
    await turnOffBtn!.trigger('click')
    await flushPromises()

    // Error surfaced AND the Turn off button must still be present — this is
    // the retry escape hatch that the buggy v-else-if removed.
    expect(document.body.textContent).toContain('Server exploded while turning off sharing.')
    turnOffBtn = wrapper.findAll('button').find((b) => b.text() === 'Turn off')
    expect(turnOffBtn).toBeDefined()

    await turnOffBtn!.trigger('click')
    await flushPromises()

    expect(retryFetchMock).toHaveBeenNthCalledWith(4, '/api/briefings/48/share', { method: 'DELETE' })
    expect(document.body.textContent).toContain('Share to web')
    expect(document.body.textContent).not.toContain('Server exploded while turning off sharing.')
  })

  it('clicking the toggle while shared copies the link and does not issue a DELETE', async () => {
    const writeText = vi.fn()
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    retryFetchMock.mockReset()
    retryFetchMock.mockResolvedValueOnce({ active: false }) // mount-time GET /share hydration
    retryFetchMock.mockResolvedValueOnce({
      token: 'tok123',
    })
    briefingValue = READY()

    const wrapper = mountPage()
    await wrapper.find('[data-testid="briefing-share-toggle"]').trigger('click')
    await flushPromises()
    expect(retryFetchMock).toHaveBeenCalledTimes(2)
    writeText.mockClear()

    await wrapper.find('[data-testid="briefing-share-toggle"]').trigger('click')
    await flushPromises()

    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/share/briefings#tok123`)
    expect(retryFetchMock).toHaveBeenCalledTimes(2)
    expect(retryFetchMock).not.toHaveBeenCalledWith('/api/briefings/48/share', { method: 'DELETE' })
    expect(document.body.textContent).toContain('Shared · Copy link')
  })

  it('hydrates share status on load: an already-shared briefing shows "Shared · New link", never "Share to web"', async () => {
    // The whole reason GET /share exists: without hydration the button reads
    // "Share to web" and a click silently rotates the token, killing the link
    // the owner already distributed.
    retryFetchMock.mockReset()
    retryFetchMock.mockResolvedValueOnce({ active: true })
    briefingValue = READY()

    mountPage()
    await flushPromises()

    expect(retryFetchMock).toHaveBeenCalledWith('/api/briefings/48/share', { method: 'GET' })
    expect(document.body.textContent).toContain('Shared · New link')
    expect(document.body.textContent).not.toContain('Share to web')
    // The revoke escape hatch must be reachable without minting a new token.
    expect(document.body.textContent).toContain('Turn off')
  })

  it('a clipboard failure after a successful share does not surface a share error', async () => {
    const writeText = vi.fn().mockRejectedValue(new DOMException('denied', 'NotAllowedError'))
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    retryFetchMock.mockReset()
    retryFetchMock.mockResolvedValueOnce({ active: false }) // mount-time GET /share hydration
    retryFetchMock.mockResolvedValueOnce({ token: 'tok123' })
    briefingValue = READY()

    const wrapper = mountPage()
    await wrapper.find('[data-testid="briefing-share-toggle"]').trigger('click')
    await flushPromises()

    // The share succeeded — showing "Could not create a share link" here
    // invited a re-click, which rotates the token and kills the working link.
    expect(document.body.textContent).toContain('Shared · Copy link')
    expect(document.body.textContent).not.toContain('Could not create a share link')
    // With the clipboard dead, the rendered selectable URL is the owner's only
    // way to retrieve the link they just made public.
    const urlEl = document.body.querySelector('[data-testid="briefing-share-url"]')
    expect(urlEl).not.toBeNull()
    expect(urlEl!.textContent).toContain('/share/briefings#tok123')
  })

  it('navigating to another briefing resets share state — no wrong-briefing URL or DELETE', async () => {
    // Nuxt reuses the page component across /briefings/:id changes. Without a
    // reset, briefing B renders A's "Shared · Copy link", Copy copies A's URL,
    // and Turn off DELETEs against B while A stays exposed.
    const writeText = vi.fn()
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    retryFetchMock.mockReset()
    retryFetchMock.mockResolvedValueOnce({ active: false }) // mount-time GET for briefing 48
    retryFetchMock.mockResolvedValueOnce({ token: 'tokA' }) // POST share on 48
    retryFetchMock.mockResolvedValueOnce({ active: false }) // hydration GET for briefing 50
    briefingValue = READY()

    const wrapper = mountPage()
    await wrapper.find('[data-testid="briefing-share-toggle"]').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Shared · Copy link')

    routeParams.id = '50' // in-place navigation, component NOT remounted
    await flushPromises()

    expect(retryFetchMock).toHaveBeenCalledWith('/api/briefings/50/share', { method: 'GET' })
    expect(document.body.textContent).toContain('Share to web')
    expect(document.body.textContent).not.toContain('tokA')
    expect(retryFetchMock).not.toHaveBeenCalledWith(expect.anything(), { method: 'DELETE' })
  })
})
