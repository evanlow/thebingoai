// GA4 gtag wrapper. Enabled only when initAnalytics() gets a non-empty id
// (NUXT_PUBLIC_GA4_ID); otherwise every export is a silent no-op so the
// community build ships zero tracking by default.
type Params = Record<string, unknown>

let enabled = false

declare global {
  interface Window {
    dataLayer: unknown[]
    gtag: (...args: unknown[]) => void
  }
}

export function initAnalytics(id: string) {
  if (!id || enabled || typeof window === 'undefined') return
  window.dataLayer = window.dataLayer || []
  // GA4's standard bootstrap: gtag() pushes its `arguments` object onto dataLayer.
  window.gtag = function gtag() {
    // eslint-disable-next-line prefer-rest-params
    window.dataLayer.push(arguments)
  }
  window.gtag('js', new Date())
  // send_page_view:false — the plugin fires page_view on router.afterEach
  // (including the initial navigation), so auto page_view would double-count.
  window.gtag('config', id, { send_page_view: false })
  // Seed page_location with the origin ONLY — no path, no query — because
  // gtag's automatic events (scroll etc.) can fire before the router
  // plugin's afterEach runs, and init has no route match yet to derive a
  // safe pattern from. A path segment can itself be a secret (the briefing
  // share token originally rode in the path; it now travels in the URL
  // fragment, but nothing stops a future route from putting a secret in a
  // dynamic segment), so window.location.pathname is not safe to seed here,
  // only the query would be. The router
  // plugin's afterEach immediately overwrites this with the redacted route
  // pattern, so this bare-origin value is only ever visible to an
  // auto-event firing in the tiny window before the first afterEach runs.
  window.gtag('set', { page_location: window.location.origin })
  const script = document.createElement('script')
  script.async = true
  script.src = `https://www.googletagmanager.com/gtag/js?id=${id}`
  document.head.appendChild(script)
  enabled = true
}

// gtag auto-attaches document.location (dl=) and document.referrer (dr=) to
// EVERY hit, including its own automatic events — so query strings carrying
// auth/reset/invite tokens would reach GA4 even though our page_view sends
// path-only. Persistently override both with path-only values on each route
// change; gtag('set') applies to all subsequent hits.
export function setAnalyticsPage(path: string, referrerPath?: string) {
  if (!enabled) return
  try {
    window.gtag('set', {
      page_location: window.location.origin + path,
      page_referrer: referrerPath ? window.location.origin + referrerPath : undefined,
    })
  } catch {
    // analytics must never break app flow
  }
}

export function trackEvent(event: string, params?: Params) {
  if (!enabled) return
  try {
    // import.meta.dev is compile-time false in prod builds — log stripped entirely
    if (import.meta.dev) console.debug('[ga4]', event, params ?? {})
    window.gtag('event', event, params ?? {})
  } catch {
    // analytics must never break app flow
  }
}

export function setAnalyticsUser(userId: string | null, orgId?: string | null) {
  if (!enabled) return
  try {
    window.gtag('set', { user_id: userId })
    window.gtag('set', 'user_properties', { org_id: orgId ?? null })
  } catch {
    // analytics must never break app flow
  }
}
