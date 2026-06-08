<template>
  <TransformDetailView v-if="detailId" :id="detailId" @back="closeDetail" />

  <div v-else class="flex flex-col h-full overflow-hidden">
    <div class="px-7 pt-3 pb-2 border-b border-[var(--line)] flex-shrink-0 flex items-start justify-between gap-3">
      <div>
        <p class="eyebrow mb-0.5 text-gray-400 dark:text-neutral-500">Settings · Data Platform</p>
        <h1 class="settings-h1 text-3xl text-gray-900 dark:text-neutral-100 mb-1">Transforms</h1>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <UiButton @click="showCreateModal = true">
          <Plus class="h-4 w-4" />
          New Transform
        </UiButton>
      </div>
    </div>
    <div class="flex-1 overflow-y-auto px-7 py-6">
      <p class="text-sm text-gray-500 dark:text-neutral-400 max-w-2xl mb-6">
        Define SQL models that join and aggregate your pipeline data.
      </p>

    <!-- Loading skeletons -->
    <div v-if="loading" class="space-y-3">
      <UiSkeleton class="h-24 w-full rounded-lg" />
      <UiSkeleton class="h-24 w-full rounded-lg" />
      <UiSkeleton class="h-24 w-full rounded-lg" />
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-400"
    >
      {{ error }}
    </div>

    <!-- Empty state -->
    <UiEmptyState
      v-else-if="transforms.length === 0"
      title="No transforms yet"
      description="Create a transform to define SQL models that aggregate your pipeline data."
      :icon="GitBranch"
    >
      <template #action>
        <UiButton @click="showCreateModal = true">
          Create Your First Transform
        </UiButton>
      </template>
    </UiEmptyState>

    <!-- Transform table -->
    <div v-else class="rounded-xl border border-[var(--line)] overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--line)] bg-[var(--paper-1)]">
            <th class="text-left px-4 py-2.5 text-[11px] font-medium uppercase tracking-wide text-[var(--ink-3)]">Transform</th>
            <th class="text-left px-4 py-2.5 text-[11px] font-medium uppercase tracking-wide text-[var(--ink-3)]">Type</th>
            <th class="text-left px-4 py-2.5 text-[11px] font-medium uppercase tracking-wide text-[var(--ink-3)]">SQL</th>
            <th class="text-left px-4 py-2.5 text-[11px] font-medium uppercase tracking-wide text-[var(--ink-3)]">Schedule</th>
            <th class="text-left px-4 py-2.5 text-[11px] font-medium uppercase tracking-wide text-[var(--ink-3)]">Status</th>
            <th class="text-left px-4 py-2.5 text-[11px] font-medium uppercase tracking-wide text-[var(--ink-3)]">Last run</th>
            <th class="px-4 py-2.5"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="transform in transforms"
            :key="transform.id"
            class="border-b border-[var(--line)] last:border-b-0 hover:bg-[var(--paper-1)] cursor-pointer transition-colors"
            @click="openDetail(transform.id)"
          >
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <span class="font-medium text-[var(--ink-0)] truncate">{{ transform.name }}</span>
                <UiBadge v-if="!transform.enabled" variant="default" size="sm">disabled</UiBadge>
              </div>
            </td>
            <td class="px-4 py-3">
              <UiBadge :variant="materializationVariant(transform.materialization)" size="sm" class="capitalize">
                {{ transform.materialization }}
              </UiBadge>
            </td>
            <td class="px-4 py-3 max-w-xs">
              <span class="font-mono text-xs text-[var(--ink-2)] truncate block">{{ sqlPreview(transform.sql) }}</span>
            </td>
            <td class="px-4 py-3">
              <span v-if="transform.cron" class="font-mono text-xs text-[var(--ink-2)]">{{ transform.cron }}</span>
              <span v-else class="text-xs italic text-[var(--ink-3)]">Manual only</span>
            </td>
            <td class="px-4 py-3">
              <UiBadge :variant="statusVariant(transform.last_run_status)" size="sm" :dot="true">
                {{ statusLabel(transform.last_run_status) }}
              </UiBadge>
            </td>
            <td class="px-4 py-3 text-xs text-[var(--ink-3)] whitespace-nowrap">
              {{ transform.last_run_at ? formatRelative(transform.last_run_at) : '—' }}
            </td>
            <td class="px-4 py-3 text-right">
              <UiButton
                size="sm"
                variant="outline"
                :loading="runningTransforms.has(transform.id)"
                :disabled="runningTransforms.has(transform.id)"
                @click.stop="handleRun(transform.id)"
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
    <TransformsTransformEditor
      :open="showCreateModal"
      @update:open="showCreateModal = $event"
      @created="handleCreated"
    />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Plus, Play, GitBranch } from 'lucide-vue-next'
import { useUserTransforms } from '~/composables/useUserTransforms'

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

const { transforms, loading, error, fetchTransforms, triggerRun } = useUserTransforms()
const showCreateModal = ref(false)
const runningTransforms = ref<Set<string>>(new Set())

onMounted(() => fetchTransforms())

async function handleRun(transformId: string) {
  runningTransforms.value = new Set([...runningTransforms.value, transformId])
  try {
    await triggerRun(transformId)
    await fetchTransforms()
  } finally {
    const next = new Set(runningTransforms.value)
    next.delete(transformId)
    runningTransforms.value = next
  }
}

function handleCreated() {
  showCreateModal.value = false
  fetchTransforms()
}

function statusVariant(status: string | null): 'success' | 'error' | 'info' | 'default' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'running') return 'info'
  return 'default'
}

function statusLabel(status: string | null): string {
  if (status === 'success') return 'Success'
  if (status === 'failed') return 'Failed'
  if (status === 'running') return 'Running'
  return 'Never run'
}

function materializationVariant(mat: string): 'info' | 'primary' | 'warning' | 'default' {
  if (mat === 'view') return 'info'
  if (mat === 'incremental') return 'warning'
  if (mat === 'table') return 'primary'
  return 'default'
}

function sqlPreview(sql: string): string {
  return sql.replace(/\s+/g, ' ').trim().slice(0, 80)
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
