<template>
  <button v-if="briefings.length" class="hdr-btn" title="Previous briefings" @click="emit('open')">
    <Newspaper class="h-3.5 w-3.5" />
    <span class="hidden sm:inline">Previous briefs</span>
  </button>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { Newspaper } from 'lucide-vue-next'
import { useDashboardBriefings } from '~/composables/useDashboardBriefings'

const props = defineProps<{ dashboardId: number }>()
const emit = defineEmits<{ open: [] }>()

const { briefings, loaded, refresh, ensure } = useDashboardBriefings(props.dashboardId)
onMounted(() => {
  ensure()
  if (loaded.value) refresh()
})
</script>

<style scoped>
/* Mirror DashboardTitleBar's .hdr-btn — scoped styles there don't reach this component. */
.hdr-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 8px;
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 500;
  border: 1px solid var(--line);
  background: var(--paper-0);
  color: var(--ink-1);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.1s, border-color 0.1s;
}
.hdr-btn:hover { background: var(--paper-2); }
</style>
