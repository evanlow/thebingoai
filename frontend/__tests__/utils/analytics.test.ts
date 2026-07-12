import { describe, it, expect } from 'vitest'
import { initAnalytics, trackEvent, setAnalyticsUser, setAnalyticsPage } from '~/utils/analytics'

describe('analytics', () => {
  it('is a no-op before init (no GA4 id configured)', () => {
    trackEvent('anything', { a: 1 })
    setAnalyticsUser('u1', 'o1')
    expect(window.dataLayer).toBeUndefined()
  })

  it('init with empty id stays disabled', () => {
    initAnalytics('')
    trackEvent('anything')
    expect(window.dataLayer).toBeUndefined()
  })

  it('init wires dataLayer, strips query from page_location, and injects the gtag script tag', () => {
    // Simulate landing on an OAuth return URL — the query must never reach GA.
    window.history.replaceState({}, '', '/auth/success?access_token=SECRET_TOKEN')
    initAnalytics('G-TEST123')
    expect(window.dataLayer!.length).toBeGreaterThan(0)
    const entries = window.dataLayer!.map((e) => Array.from(e as ArrayLike<unknown>))
    const pageSet = entries.find(
      (e) => e[0] === 'set' && !!(e[1] as Record<string, unknown>)?.page_location
    )
    expect((pageSet![1] as Record<string, unknown>).page_location).toBe(
      window.location.origin + '/auth/success'
    )
    expect(JSON.stringify(entries)).not.toContain('SECRET_TOKEN')
    const script = document.head.querySelector(
      'script[src="https://www.googletagmanager.com/gtag/js?id=G-TEST123"]'
    )
    expect(script).toBeTruthy()
  })

  it('trackEvent pushes the event with params', () => {
    const before = window.dataLayer!.length
    trackEvent('dashboard_create', { dashboard_id: 7 })
    expect(window.dataLayer!.length).toBe(before + 1)
    const entry = Array.from(window.dataLayer!.at(-1) as ArrayLike<unknown>)
    expect(entry).toEqual(['event', 'dashboard_create', { dashboard_id: 7 }])
  })

  it('setAnalyticsUser sets user_id then org_id user property', () => {
    setAnalyticsUser('user-uuid', 'org-uuid')
    const entries = window.dataLayer!.slice(-2).map((e) => Array.from(e as ArrayLike<unknown>))
    expect(entries[0]).toEqual(['set', { user_id: 'user-uuid' }])
    expect(entries[1]).toEqual(['set', 'user_properties', { org_id: 'org-uuid' }])
  })

  it('setAnalyticsPage sets path-only page_location and page_referrer', () => {
    setAnalyticsPage('/dashboard', '/login')
    const entry = Array.from(window.dataLayer!.at(-1) as ArrayLike<unknown>)
    expect(entry).toEqual([
      'set',
      {
        page_location: window.location.origin + '/dashboard',
        page_referrer: window.location.origin + '/login',
      },
    ])
  })

  it('second init is ignored (no duplicate script)', () => {
    initAnalytics('G-TEST123')
    const scripts = document.head.querySelectorAll('script[src^="https://www.googletagmanager.com"]')
    expect(scripts.length).toBe(1)
  })
})
