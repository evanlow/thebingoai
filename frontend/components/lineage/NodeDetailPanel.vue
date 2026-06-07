<script setup lang="ts">
import { computed } from 'vue'
import type { LineageNode, LineageGraph } from '~/composables/useLineage'
import { timeAgo } from '~/utils/format'

const props = defineProps<{
  node: LineageNode | null
  graph?: LineageGraph | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'rerun', node: LineageNode): void
}>()

const meta = computed(() => props.node?.meta ?? {})

const palette: Record<string, { dot: string; accent: string; label: string }> = {
  source:    { dot: '#3b82f6', accent: '#dbeafe', label: 'SOURCE' },
  pipeline:  { dot: '#8b5cf6', accent: '#ede9fe', label: 'PIPELINE' },
  parquet:   { dot: '#64748b', accent: '#f1f5f9', label: 'PARQUET' },
  transform: { dot: '#f59e0b', accent: '#fef3c7', label: 'TRANSFORM' },
  widget:    { dot: '#0ea5e9', accent: '#e0f2fe', label: 'WIDGET' },
}

const kindPal = computed(() => palette[props.node?.kind ?? ''] ?? { dot: '#9ca3af', accent: '#f3f4f6', label: props.node?.kind?.toUpperCase() ?? '' })
const kindLabel = computed(() => kindPal.value.label)
const dotColor = computed(() => kindPal.value.dot)

const lastBuild = computed(() => {
  const t = meta.value.last_run_at
  return t ? timeAgo(t) : '—'
})

const errorMessage = computed(() => meta.value.error_message as string | null)

const neighbors = computed(() => {
  const g = props.graph
  const nid = props.node?.id
  if (!g || !nid) return { upstream: [] as string[], downstream: [] as string[] }
  const up: string[] = []
  const down: string[] = []
  for (const e of g.edges) {
    if (e.dst === nid) {
      const src = g.nodes.find(n => n.id === e.src)
      if (src) up.push(src.name)
    }
    if (e.src === nid) {
      const dst = g.nodes.find(n => n.id === e.dst)
      if (dst) down.push(dst.name)
    }
  }
  return { upstream: up, downstream: down }
})

const showRerun = computed(() => {
  const k = props.node?.kind
  return k === 'pipeline' || k === 'transform'
})

// One class set per status — the gray fallback applies only when no specific
// status matches, so the badge never carries two conflicting backgrounds.
const STATUS_CLASSES: Record<string, string> = {
  success: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300',
  succeeded: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300',
  failed: 'bg-rose-100 text-rose-800 dark:bg-rose-950/40 dark:text-rose-300',
  running: 'bg-blue-100 text-blue-800 dark:bg-blue-950/40 dark:text-blue-300',
}
const STATUS_FALLBACK = 'bg-gray-100 text-gray-600 dark:bg-neutral-800 dark:text-neutral-400'

const statusClass = computed(() =>
  STATUS_CLASSES[meta.value.last_run_status as string] ?? STATUS_FALLBACK,
)
</script>

<template>
  <div
    v-if="node"
    class="border-l border-[var(--line)] bg-white dark:bg-neutral-900 w-80 flex-shrink-0 overflow-y-auto"
  >
    <!-- Header -->
    <div class="p-4 border-b border-[var(--line)] flex items-start justify-between">
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-1.5 mb-1">
          <span class="h-2 w-2 rounded-full shrink-0" :style="{ background: dotColor }" />
          <span class="text-[10px] font-semibold tracking-widest uppercase text-gray-400 dark:text-neutral-500">
            {{ kindLabel }}
          </span>
        </div>
        <p class="text-sm font-medium text-gray-900 dark:text-neutral-100 break-all leading-snug">
          {{ node.name }}
        </p>
      </div>
      <button
        class="text-gray-400 hover:text-gray-600 dark:hover:text-neutral-200 text-sm shrink-0 ml-2"
        @click="emit('close')"
      >
        ✕
      </button>
    </div>

    <!-- Detail rows -->
    <div class="p-4 space-y-3 text-sm">
      <div v-if="meta.last_run_status">
        <div class="text-xs text-gray-500 dark:text-neutral-400">Status</div>
        <span
          class="inline-block mt-0.5 px-2 py-0.5 rounded text-xs font-medium"
          :class="statusClass"
        >
          {{ meta.last_run_status }}
        </span>
      </div>

      <div v-if="meta.materialization">
        <div class="text-xs text-gray-500 dark:text-neutral-400">Materialization</div>
        <div class="text-gray-900 dark:text-neutral-100 mt-0.5">{{ meta.materialization }}</div>
      </div>

      <div v-if="meta.last_run_at">
        <div class="text-xs text-gray-500 dark:text-neutral-400">Last build</div>
        <div class="text-gray-900 dark:text-neutral-100 mt-0.5">{{ lastBuild }}</div>
      </div>

      <div v-if="neighbors.upstream.length">
        <div class="text-xs text-gray-500 dark:text-neutral-400">Upstream</div>
        <div class="text-gray-900 dark:text-neutral-100 mt-0.5 space-y-0.5">
          <div v-for="n in neighbors.upstream" :key="n" class="text-[13px]">· {{ n }}</div>
        </div>
      </div>

      <div v-if="neighbors.downstream.length">
        <div class="text-xs text-gray-500 dark:text-neutral-400">Downstream</div>
        <div class="text-gray-900 dark:text-neutral-100 mt-0.5 space-y-0.5">
          <div v-for="n in neighbors.downstream" :key="n" class="text-[13px]">· {{ n }}</div>
        </div>
      </div>

      <!-- Error callout -->
      <div v-if="errorMessage" class="rounded-lg bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 p-3 text-xs text-rose-800 dark:text-rose-300">
        {{ errorMessage }}
      </div>

      <div
        v-else-if="node.kind === 'widget' && meta.lineage_status === 'incomplete'"
        class="rounded-lg bg-yellow-50 dark:bg-yellow-950/30 border border-yellow-200 dark:border-yellow-800 p-3 text-xs text-yellow-800 dark:text-yellow-300"
      >
        Lineage incomplete — SQL not parseable. An admin will review.
      </div>

      <!-- Action buttons -->
      <div class="pt-2 space-y-2">
        <template v-for="(link, i) in [
          meta.model_id ? { key: 'transform', to: { path: '/settings', query: { tab: 'transforms', id: meta.model_id } }, label: 'Open transform →' } : null,
          meta.pipeline_id ? { key: 'pipeline', to: { path: '/settings', query: { tab: 'pipelines', id: meta.pipeline_id } }, label: 'Open pipeline →' } : null,
          meta.dashboard_id ? { key: 'dashboard', to: { path: '/dashboard', query: { id: meta.dashboard_id } }, label: 'Open dashboard →' } : null,
        ]" :key="link?.key">
          <NuxtLink
            v-if="link"
            :to="link.to"
            class="block w-full text-center text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium"
          >
            {{ link.label }}
          </NuxtLink>
        </template>

        <button
          v-if="showRerun"
          class="block w-full text-center text-[13px] font-medium px-3 py-1.5 rounded-lg border border-[var(--line)] bg-[var(--paper-0)] text-[var(--ink-0)] hover:bg-[var(--paper-1)] transition-colors"
          @click="emit('rerun', node)"
        >
          Re-run
        </button>
      </div>
    </div>
  </div>
</template>
