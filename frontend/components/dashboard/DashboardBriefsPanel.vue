<template>
  <aside class="briefs-panel flex flex-col border-l border-[var(--line)] bg-[var(--paper-0)] dark:bg-neutral-900 dark:border-neutral-700">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-[var(--line)] dark:border-neutral-700">
      <h2 class="text-sm font-semibold text-[var(--ink-0)]">Previous briefs</h2>
      <button
        data-testid="briefs-panel-close"
        class="p-1 rounded hover:bg-[var(--paper-2)] text-[var(--ink-2)]"
        @click="emit('close')"
      >
        <X class="h-4 w-4" />
      </button>
    </div>

    <!-- Body -->
    <div class="flex-1 overflow-y-auto px-3 py-2">
      <div v-if="!loaded && loading" class="text-sm text-[var(--ink-2)] py-4 text-center">Loading briefings…</div>
      <div v-else-if="error && !briefings.length" class="text-sm text-red-500 py-4 text-center">{{ error }}</div>
      <div v-else-if="!briefings.length" class="text-sm text-[var(--ink-2)] py-8 text-center">No briefings yet</div>

      <template v-else>
        <button
          v-for="b in briefings"
          :key="b.id"
          data-testid="briefs-row"
          class="relative w-full flex items-center gap-1.5 py-1.5 pl-1.5 pr-16 rounded-lg hover:bg-[var(--paper-2)] transition-colors text-left"
          @click="openBriefing(b.id)"
        >
          <Newspaper
            class="flex-shrink-0 w-3.5 h-3.5"
            :class="b.status === 'ready' ? 'text-violet-400' : 'text-[var(--ink-2)]'"
          />
          <span class="min-w-0 truncate text-sm text-[var(--ink-1)]">
            {{ b.payload?.headline || 'Untitled briefing' }}
          </span>
          <span class="absolute right-1.5 text-sm text-[var(--ink-2)] tabular-nums">
            {{ formatShort(b.created_at) }}
          </span>
        </button>
      </template>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { Newspaper, X } from 'lucide-vue-next'
import { useDashboardBriefings } from '~/composables/useDashboardBriefings'

const props = defineProps<{ dashboardId: number }>()
const emit = defineEmits<{ close: [] }>()

const { briefings, loaded, loading, error, ensure, refresh } = useDashboardBriefings(props.dashboardId)

onMounted(() => {
  ensure()
  if (loaded.value) refresh()
})

function openBriefing(id: number) {
  navigateTo('/briefings/' + id)
}

function formatShort(s: string) {
  const diffMs = Date.now() - new Date(s).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 60) return `${mins}m`
  const hours = Math.floor(diffMs / 3600000)
  if (hours < 24) return `${hours}h`
  if (hours < 48) return 'yesterday'
  return new Date(s).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
.briefs-panel {
  width: 320px;
  max-width: 90vw;
  height: 100%;
}
</style>
