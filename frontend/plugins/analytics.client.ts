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
  // to.path only — query strings carry secrets (auth/reset/invite tokens).
  const router = useRouter()
  router.afterEach((to, from) => {
    // Strip query from gtag's auto-attached page_location/page_referrer too —
    // they'd otherwise carry the full URL (incl. tokens) on every hit.
    setAnalyticsPage(to.path, from?.path)
    trackEvent('page_view', { page_path: to.path })
  })

  const authStore = useAuthStore()
  watch(
    () => authStore.user,
    (u) => setAnalyticsUser(u?.id ?? null, u?.org_id ?? null),
    { immediate: true }
  )
})
