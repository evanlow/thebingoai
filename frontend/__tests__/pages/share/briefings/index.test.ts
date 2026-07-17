import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, onMounted } from 'vue'

// The public share page must render entirely from the one public endpoint.
// Any authed call here is a bug: an anonymous visitor has no token for it.
// The share token travels in the URL FRAGMENT and is resolved via POST body —
// never a path or query segment — so the raw credential stays out of server
// access logs and Referer headers.

vi.stubGlobal('ref', ref)
vi.stubGlobal('onMounted', onMounted)
vi.stubGlobal('definePageMeta', () => {})

const fetchMock = vi.fn()
vi.stubGlobal('$fetch', fetchMock)

import SharePage from '~/pages/share/briefings/index.vue'
import BriefingBody from '~/components/briefings/BriefingBody.vue'

const PUBLIC_PAYLOAD = {
  headline: 'Revenue up 12%',
  deck: 'A short deck.',
  kpis: [],
  sections: [{ heading: 'One', prose: 'p', widget_id: 'chart_1' }],
  key_takeaways: ['Grow', 'Ship', 'Measure'],
  widget_snapshots: { chart_1: { series: [1, 2, 3] } },
  widgets: { chart_1: { id: 'chart_1', widget: { type: 'bar', config: { type: 'bar' } } } },
  dashboard_name: 'Sales',
  created_at: '2026-07-16T10:00:00Z',
}

const mountPage = () =>
  mount(SharePage, {
    attachTo: document.body,
    // BriefingBody is auto-imported by Nuxt at runtime but not under VTU —
    // register it explicitly or its content never renders.
    global: { stubs: { BriefingWidgetEmbed: true }, components: { BriefingBody } },
  })

describe('share/briefings (fragment token)', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    fetchMock.mockReset()
    window.location.hash = '#tok123'
  })

  it('resolves the fragment token via POST body — never a token-bearing URL', async () => {
    fetchMock.mockResolvedValue(PUBLIC_PAYLOAD)
    mountPage()
    await flushPromises()

    expect(document.body.textContent).toContain('Revenue up 12%')
    expect(document.body.textContent).toContain('Grow')
    expect(fetchMock).toHaveBeenCalledWith('/api/public/briefings/resolve', {
      method: 'POST',
      body: { token: 'tok123' },
    })
    // The token must appear in NO requested URL: a path/query token lands the
    // raw credential in uvicorn/nginx access logs.
    const urls = fetchMock.mock.calls.map((c) => String(c[0]))
    expect(urls.some((u) => u.includes('tok123'))).toBe(false)
  })

  it('never calls an authed dashboard endpoint', async () => {
    fetchMock.mockResolvedValue(PUBLIC_PAYLOAD)
    mountPage()
    await flushPromises()

    const urls = fetchMock.mock.calls.map((c) => String(c[0]))
    expect(urls.some((u) => u.includes('/api/dashboards/'))).toBe(false)
  })

  it('shows a generic message for an unavailable link', async () => {
    fetchMock.mockRejectedValue(new Error('404'))
    mountPage()
    await flushPromises()

    expect(document.body.textContent).toContain("isn't available")
    // Must not distinguish revoked from never-existed.
    expect(document.body.textContent).not.toContain('revoked')
  })

  it('makes no request at all when the fragment is empty', async () => {
    window.location.hash = ''
    mountPage()
    await flushPromises()

    expect(fetchMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain("isn't available")
  })
})
