<template>
  <div v-if="widget && widget.widget?.config" class="rounded-lg border border-neutral-100 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-4">
    <DashboardWidget :widget="widget" :auto-refresh="!snapshot" />
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  widgetId: string | number
  dashboardId: number
  // Rendered data config snapshot from generation time. When present we merge
  // it instead of re-running the widget's SQL — instant render, no live query.
  snapshot?: Record<string, any>
}>()

const emit = defineEmits<{ loaded: [] }>()

const { fetchWithRefresh } = useApi()
const widget = ref<any>(null)
// DashboardWidget only refreshes on click; briefing embeds render the saved
// (data-less) config. Pull the widget's data on mount so charts/KPIs populate.
// Skip useWidgetData's auto-refresh watcher when a snapshot is present — the
// snapshot populates the config below, so a live re-query would be redundant.
const { refresh } = useWidgetData(widget as any, !props.snapshot)

onMounted(async () => {
  try {
    widget.value = await fetchWithRefresh(
      `/api/dashboards/${props.dashboardId}/widgets/${props.widgetId}`,
      { method: 'GET' },
    )
    if (props.snapshot) {
      // Snapshot present (generated post-rollout): merge the saved data config,
      // no SQL round-trip. mergeRefreshedConfig preserves editor-only columns.
      const { mergeRefreshedConfig } = await import('~/utils/widgetMerge')
      Object.assign(widget.value.widget.config, mergeRefreshedConfig(widget.value, { ...props.snapshot }))
    } else if (widget.value?.dataSource) {
      await refresh()
    }
  } catch {
    // widget deleted between briefing-time and view-time — silent drop
    widget.value = null
  } finally {
    // Always signal completion — even a dropped widget must not stall the PDF wait.
    emit('loaded')
  }
})
</script>
