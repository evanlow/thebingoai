import { describe, it, expect, vi, beforeEach } from 'vitest'

// ── Mock the analytics core — the plugin's only side effects go through it ──
const mocks = vi.hoisted(() => ({
  initAnalytics: vi.fn(),
  trackEvent: vi.fn(),
  setAnalyticsUser: vi.fn(),
  setAnalyticsPage: vi.fn(),
}))
vi.mock('~/utils/analytics', () => mocks)

// ── Stub Nuxt auto-imports ──────────────────────────────────────────
vi.stubGlobal('defineNuxtPlugin', (fn: Function) => fn)
vi.stubGlobal('useRuntimeConfig', () => ({ public: { ga4Id: 'G-PLUGIN1' } }))

let afterEachCb: (to: any, from: any) => void
vi.stubGlobal('useRouter', () => ({
  afterEach: (cb: any) => { afterEachCb = cb },
}))

// watch stub: capture the identity callback and honor immediate
let userWatchCb: (u: any) => void
const authState = { user: null as any }
vi.stubGlobal('watch', (src: () => any, cb: any, opts?: any) => {
  userWatchCb = cb
  if (opts?.immediate) cb(src())
})

vi.mock('~/stores/auth', () => ({ useAuthStore: () => authState }))

describe('analytics client plugin', () => {
  beforeEach(async () => {
    Object.values(mocks).forEach((m) => m.mockClear())
    authState.user = null
    // Dynamic import — the plugin module calls defineNuxtPlugin at load time,
    // so it must be imported after the global stubs are installed.
    const { default: plugin } = await import('~/plugins/analytics.client')
    ;(plugin as unknown as () => void)()
  })

  it('initializes analytics with the runtime-config GA4 id', () => {
    expect(mocks.initAnalytics).toHaveBeenCalledExactlyOnceWith('G-PLUGIN1')
  })

  it('fires page_view with the matched route pattern only — never the query string', () => {
    afterEachCb(
      { path: '/auth/success', fullPath: '/auth/success?access_token=SECRET', matched: [{ path: '/auth/success' }] },
      { path: '/login', fullPath: '/login', matched: [{ path: '/login' }] },
    )
    expect(mocks.trackEvent).toHaveBeenCalledExactlyOnceWith('page_view', {
      page_path: '/auth/success',
    })
    expect(JSON.stringify(mocks.trackEvent.mock.calls)).not.toContain('SECRET')
  })

  it('re-sets the route-pattern page_location and page_referrer before each page_view', () => {
    afterEachCb(
      { path: '/dashboard', fullPath: '/dashboard?id=40', matched: [{ path: '/dashboard' }] },
      { path: '/data', fullPath: '/data', matched: [{ path: '/data' }] },
    )
    expect(mocks.setAnalyticsPage).toHaveBeenCalledExactlyOnceWith('/dashboard', '/data')
    // set must precede the page_view event so the hit carries the stripped URL
    expect(mocks.setAnalyticsPage.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.trackEvent.mock.invocationCallOrder[0],
    )
  })

  it('reports the share-briefing route as its :token pattern — never the concrete token', () => {
    const token = '0jSZlt8t1LrG86fqMrv_8NOYKdwLSsj8YnficKrDmGg'
    afterEachCb(
      {
        path: `/share/briefings/${token}`,
        fullPath: `/share/briefings/${token}`,
        matched: [{ path: '/share/briefings/:token' }],
      },
      { path: '/', fullPath: '/', matched: [{ path: '/' }] },
    )
    expect(mocks.trackEvent).toHaveBeenCalledExactlyOnceWith('page_view', {
      page_path: '/share/briefings/:token',
    })
    expect(mocks.setAnalyticsPage).toHaveBeenCalledExactlyOnceWith('/share/briefings/:token', '/')
    expect(JSON.stringify(mocks.trackEvent.mock.calls)).not.toContain(token)
    expect(JSON.stringify(mocks.setAnalyticsPage.mock.calls)).not.toContain(token)
  })

  it('falls back to a fixed constant (never the raw path) for an unmatched route', () => {
    const secretLike = '/share/briefings/leaked-if-fallback-used'
    afterEachCb(
      { path: secretLike, fullPath: secretLike, matched: [] },
      { path: '/', fullPath: '/', matched: [{ path: '/' }] },
    )
    expect(mocks.trackEvent).toHaveBeenCalledExactlyOnceWith('page_view', {
      page_path: '/unmatched',
    })
    expect(JSON.stringify(mocks.trackEvent.mock.calls)).not.toContain('leaked-if-fallback-used')
  })

  it('binds identity immediately (null before login) and on user change', () => {
    expect(mocks.setAnalyticsUser).toHaveBeenCalledWith(null, null)
    userWatchCb({ id: 'u-uuid', org_id: 'o-uuid' })
    expect(mocks.setAnalyticsUser).toHaveBeenLastCalledWith('u-uuid', 'o-uuid')
    userWatchCb(null) // logout clears identity
    expect(mocks.setAnalyticsUser).toHaveBeenLastCalledWith(null, null)
  })
})
