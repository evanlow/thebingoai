<template>
  <button class="hdr-btn" @click="onClick">
    <Sparkles class="h-3.5 w-3.5" />
    <span class="hidden sm:inline">Brief me</span>
  </button>
</template>

<script setup lang="ts">
import { Sparkles } from 'lucide-vue-next'

const props = defineProps<{ dashboardId: number }>()

// Navigate to the generating page immediately. The briefing is created there
// (POST /brief), so the click feels instant instead of blocking on a POST that
// queues behind the dashboard's in-flight widget-refresh requests.
function onClick() {
  navigateTo(`/briefings/new?dashboard_id=${props.dashboardId}`)
}
</script>
