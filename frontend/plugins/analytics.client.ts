/**
 * GA4 analytics plugin. No-op unless NUXT_PUBLIC_GA4_ID is set.
 * Fires SPA page_view on every route change and binds user/org identity
 * to the GA4 session on login/logout.
 */
import { initAnalytics, trackEvent, setAnalyticsUser, setAnalyticsPage } from '~/utils/analytics'
import { useAuthStore } from '~/stores/auth'

export default defineNuxtPlugin(() => {
  const id = useRuntimeConfig().public.ga4Id as string
  initAnalytics(id)

  // Nuxt's router plugin re-runs the initial navigation after app:created,
  // so this covers first load + every SPA route change exactly once.
  //
  // We report the MATCHED ROUTE PATTERN (e.g. "/briefings/:id"), never the
  // concrete to.path/from.path. Query strings carry secrets
  // (auth/reset/invite tokens) — that's the case setAnalyticsPage's
  // page_location override below handles. But a route can carry a secret
  // directly in the path itself (the briefing share token originally rode
  // in the path before moving to the URL fragment), so path-only is not
  // enough: reporting the route pattern instead means no dynamic segment,
  // for this route or any future one, can ever reach GA.
  const UNMATCHED = '/unmatched'
  const router = useRouter()
  router.afterEach((to, from) => {
    // An unmatched route (to.matched empty — no page component resolved)
    // could itself be a mistyped secret-bearing path (e.g. a bad share
    // link that fails to match). There's no safe pattern to derive for it,
    // so report a fixed constant instead of ever falling back to the raw
    // to.path/from.path.
    const toPattern = to.matched.at(-1)?.path ?? UNMATCHED
    const fromPattern = from ? (from.matched.at(-1)?.path ?? UNMATCHED) : undefined
    // Strip query from gtag's auto-attached page_location/page_referrer too —
    // they'd otherwise carry the full URL (incl. tokens) on every hit.
    setAnalyticsPage(toPattern, fromPattern)
    trackEvent('page_view', { page_path: toPattern })
  })

  const authStore = useAuthStore()
  watch(
    () => authStore.user,
    (u) => setAnalyticsUser(u?.id ?? null, u?.org_id ?? null),
    { immediate: true }
  )
})
