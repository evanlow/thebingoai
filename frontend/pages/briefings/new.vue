<template>
  <div class="h-full overflow-y-auto bg-white dark:bg-neutral-900">
    <div class="max-w-3xl mx-auto px-6 py-10 space-y-4">
      <!-- Create failed (e.g. 402 out of credits) -->
      <div v-if="error" class="rounded-lg border border-rose-200 bg-rose-50 p-6">
        <h2 class="text-lg font-semibold text-rose-900 mb-2">Could not start briefing</h2>
        <p class="text-sm text-rose-700">{{ error }}</p>
      </div>

      <!-- Creating — shown instantly so the click feels responsive even while the
           POST waits behind the dashboard's in-flight widget-refresh requests. -->
      <template v-else>
        <p class="text-sm uppercase tracking-wider text-neutral-500">Generating your briefing…</p>
        <div class="h-10 w-3/4 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
        <div class="h-4 w-full bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
        <div class="h-4 w-5/6 bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
        <div class="h-4 w-2/3 bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const error = ref('')
const { fetchWithRefresh } = useApi()

onMounted(async () => {
  const dashboardId = route.query.dashboard_id
  if (!dashboardId) {
    error.value = 'Missing dashboard id.'
    return
  }
  try {
    const resp = await fetchWithRefresh(`/api/dashboards/${dashboardId}/brief`, { method: 'POST' })
    useBriefingsList().refresh()
    await navigateTo(`/briefings/${resp.briefing_id}`, { replace: true })
  } catch (err: any) {
    const detail = err?.data?.detail
    error.value = (detail && typeof detail === 'object' ? detail.message : detail)
      || err?.message
      || 'Failed to generate briefing'
  }
})
</script>
