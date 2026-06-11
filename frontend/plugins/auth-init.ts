export default defineNuxtPlugin(async () => {
  const authStore = useAuthStore()

  // Maintenance-mode bypass: if the URL carries `?maint_bypass=KEY`, exchange it
  // for an HttpOnly cookie via the backend. Strip the param from the visible URL
  // either way so the key never lingers in history / bookmarks / referrers.
  if (import.meta.client) {
    const url = new URL(window.location.href)
    const bypassKey = url.searchParams.get('maint_bypass')
    if (bypassKey) {
      try {
        await $fetch('/api/maintenance/bypass', {
          method: 'POST',
          body: { key: bypassKey },
          credentials: 'include',
          timeout: 10_000,
        })
      } catch {
        // Invalid key / bypass disabled → user will see the maintenance page.
      }
      url.searchParams.delete('maint_bypass')
      history.replaceState({}, '', url.toString())
    }
  }

  // Load SSO auth config from backend (includes maintenance state + bypass flag).
  // Must never block app mount forever — a hung backend would leave a blank page.
  try {
    await authStore.loadAuthConfig()
  } catch (error) {
    console.error('Auth config load failed during boot, continuing degraded:', error)
  }

  // Restore user session from localStorage
  try {
    await authStore.loadUser()
  } catch {
    // Session restore failed (e.g. inactive account) — start unauthenticated
  }
})
