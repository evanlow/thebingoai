<template>
  <PipelineDetailView v-if="detailId" :id="detailId" @back="closeDetail" />

  <div v-else class="flex flex-col h-full overflow-hidden">
    <div class="px-7 pt-3 pb-2 border-b border-[var(--line)] flex-shrink-0 flex items-start justify-between gap-3">
      <div>
        <p class="eyebrow mb-0.5 text-gray-400 dark:text-neutral-500">Settings · Data Platform</p>
        <h1 class="settings-h1 text-3xl text-gray-900 dark:text-neutral-100 mb-1">Pipelines</h1>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <UiButton @click="showCreateModal = true">
          <Plus class="h-4 w-4" />
          New Pipeline
        </UiButton>
      </div>
    </div>
    <div class="flex-1 overflow-y-auto px-7 py-6">
      <p class="text-base text-gray-500 dark:text-neutral-400 max-w-2xl mb-6">
        Manage scheduled data sync pipelines from your connections.
      </p>

    <!-- Error -->
    <div
      v-if="error"
      class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-400"
    >
      {{ error }}
    </div>

    <!-- Loading skeletons -->
    <div v-if="loading" class="space-y-3">
      <UiSkeleton class="h-24 w-full rounded-lg" />
      <UiSkeleton class="h-24 w-full rounded-lg" />
      <UiSkeleton class="h-24 w-full rounded-lg" />
    </div>

    <!-- Empty state -->
    <UiEmptyState
      v-else-if="pipelines.length === 0"
      title="No pipelines yet"
      description="Create a pipeline to schedule automated data syncs from your connections."
      :icon="Workflow"
    >
      <template #action>
        <UiButton @click="showCreateModal = true">
          Create Your First Pipeline
        </UiButton>
      </template>
    </UiEmptyState>

    <!-- Pipeline table -->
    <div v-else class="rounded-xl border border-[var(--line)] overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--line)] bg-[var(--paper-1)]">
            <th class="text-left px-4 py-2.5 text-sm font-medium uppercase tracking-wide text-[var(--ink-3)]">Pipeline</th>
            <th class="text-left px-4 py-2.5 text-sm font-medium uppercase tracking-wide text-[var(--ink-3)]">Source</th>
            <th class="text-left px-4 py-2.5 text-sm font-medium uppercase tracking-wide text-[var(--ink-3)]">Target</th>
            <th class="text-left px-4 py-2.5 text-sm font-medium uppercase tracking-wide text-[var(--ink-3)]">Schedule</th>
            <th class="text-left px-4 py-2.5 text-sm font-medium uppercase tracking-wide text-[var(--ink-3)]">Status</th>
            <th class="text-left px-4 py-2.5 text-sm font-medium uppercase tracking-wide text-[var(--ink-3)]">Last run</th>
            <th class="px-4 py-2.5"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="pipeline in pipelines"
            :key="pipeline.id"
            class="border-b border-[var(--line)] last:border-b-0 hover:bg-[var(--paper-1)] cursor-pointer transition-colors"
            @click="openDetail(pipeline.id)"
          >
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <span class="font-medium text-[var(--ink-0)] truncate">{{ pipeline.name }}</span>
                <UiBadge v-if="!pipeline.enabled" variant="default" size="sm">disabled</UiBadge>
              </div>
            </td>
            <td class="px-4 py-3 max-w-[200px]">
              <div class="flex items-center gap-2 min-w-0">
                <span
                  class="grid place-items-center h-6 w-6 rounded-md text-sm font-semibold text-white shrink-0"
                  :class="avatarColor(pipeline.source_connection_id)"
                >
                  {{ sourceInitial(pipeline.source_connection_id) }}
                </span>
                <span class="text-[var(--ink-1)] truncate" :title="sourceLabel(pipeline.source_connection_id)">{{ sourceLabel(pipeline.source_connection_id) }}</span>
              </div>
            </td>
            <td class="px-4 py-3 font-mono text-sm text-[var(--ink-2)]">{{ pipeline.target_table }}</td>
            <td class="px-4 py-3">
              <span v-if="pipeline.cron" class="font-mono text-sm text-[var(--ink-2)]">{{ pipeline.cron }}</span>
              <span v-else class="text-sm italic text-[var(--ink-3)]">Manual only</span>
            </td>
            <td class="px-4 py-3">
              <UiBadge :variant="statusVariant(pipeline.last_run_status)" size="sm" :dot="true">
                {{ statusLabel(pipeline.last_run_status) }}
              </UiBadge>
            </td>
            <td class="px-4 py-3 text-sm text-[var(--ink-3)] whitespace-nowrap">
              {{ pipeline.last_run_at ? formatRelative(pipeline.last_run_at) : '—' }}
            </td>
            <td class="px-4 py-3 text-right">
              <UiButton
                size="sm"
                variant="outline"
                :loading="runningPipelines.has(pipeline.id)"
                @click.stop="handleRun(pipeline.id)"
                :disabled="runningPipelines.has(pipeline.id)"
              >
                <Play class="h-3.5 w-3.5" />
                Run
              </UiButton>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create modal -->
    <PipelinesPipelineEditModal
      v-model:open="showCreateModal"
      @created="handleCreated"
    />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Plus, Play, Workflow } from 'lucide-vue-next'
import { useUserPipelines, type Pipeline } from '~/composables/useUserPipelines'
import { useConnections } from '~/composables/useConnections'
import { avatarColor, initialFromLabel } from '~/utils/pipelineFormat'

const route = useRoute()
const router = useRouter()

const detailId = computed(() => (route.query.id as string) || '')

function openDetail(id: string) {
  router.push({ query: { ...route.query, id } })
}

function closeDetail() {
  const next = { ...route.query }
  delete next.id
  router.replace({ query: next })
}

const { pipelines, loading, error, fetchPipelines, triggerRun } = useUserPipelines()
const { ensureLoaded, getConnectionLabel } = useConnections()
const showCreateModal = ref(false)
const runningPipelines = ref<Set<string>>(new Set())

onMounted(() => {
  fetchPipelines()
  ensureLoaded()
})

// Source connection display — rows only carry source_connection_id, so resolve
// names through the shared connections cache (falls back to "Connection #id").
function sourceLabel(id: number): string {
  return getConnectionLabel(id)
}
function sourceInitial(id: number): string {
  return initialFromLabel(getConnectionLabel(id))
}

async function handleRun(pipelineId: string) {
  runningPipelines.value = new Set([...runningPipelines.value, pipelineId])
  try {
    await triggerRun(pipelineId)
    await fetchPipelines()
  } finally {
    const next = new Set(runningPipelines.value)
    next.delete(pipelineId)
    runningPipelines.value = next
  }
}

function handleCreated() {
  showCreateModal.value = false
  fetchPipelines()
}

function statusVariant(status: Pipeline['last_run_status']): 'success' | 'error' | 'info' | 'default' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'running') return 'info'
  return 'default'
}

function statusLabel(status: Pipeline['last_run_status']): string {
  if (status === 'success') return 'Success'
  if (status === 'failed') return 'Failed'
  if (status === 'running') return 'Running'
  return 'Never run'
}

function formatRelative(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.round(diffMs / 1000)
  if (diffSec < 60) return 'just now'
  const diffMin = Math.round(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.round(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.round(diffHr / 24)
  if (diffDay < 30) return `${diffDay}d ago`
  return date.toLocaleDateString()
}
</script>
