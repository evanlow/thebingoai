<template>
  <div
    class="rounded-lg bg-[var(--paper-1)] border px-2.5 py-2"
    :class="dataset.step === 'failed' ? 'border-red-200' : 'border-[var(--line)]'"
  >
    <!-- File header -->
    <div class="flex items-center gap-2 mb-2">
      <svg class="w-3.5 h-3.5 text-[var(--ink-2)] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <span class="text-sm font-medium text-gray-600 dark:text-neutral-400 truncate min-w-0 flex-1">{{ dataset.name }}</span>
      <span class="text-sm text-gray-300 shrink-0">{{ formatSize(dataset.size) }}</span>
    </div>

    <!-- Vertical timeline -->
    <div class="pl-1">
      <DatasetTimelineStep
        :status="stepStatus('uploading')"
        label="Uploaded"
        active-label="Uploading..."
        :timestamp="stepTimestampFor('uploading')"
        :is-last="false"
        :next-status="stepStatus('schema')"
      />
      <DatasetTimelineStep
        :status="stepStatus('schema')"
        label="Schema built"
        active-label="Building schema..."
        :timestamp="stepTimestampFor('schema')"
        :is-last="false"
        :next-status="stepStatus('profiling')"
      />
      <DatasetTimelineStep
        :status="stepStatus('profiling')"
        label="Data profiled"
        active-label="Profiling data..."
        :timestamp="stepTimestampFor('profiling')"
        :is-last="!docsStatus"
        :next-status="docsStatus ?? undefined"
        :error="dataset.step === 'failed' && stepStatus('profiling') === 'failed' ? dataset.error : null"
      />

      <!-- Documentation runs after profiling and is driven by the thread, not the
           dataset's own step — the panel renders the card without it. -->
      <div v-if="docsStatus" class="flex gap-2.5">
        <div class="flex flex-col items-center">
          <div class="w-3.5 h-3.5 flex items-center justify-center shrink-0 z-[1]">
            <template v-if="docsStatus === 'active'">
              <img src="/logo/BINGO Logo Design_FA_Icon.png" class="w-3.5 h-3.5 object-contain docs-spin dark:hidden" alt="" />
              <img src="/logo/BINGO Logo Design_FA_Icon_W.png" class="w-3.5 h-3.5 object-contain docs-spin hidden dark:block" alt="" />
            </template>
            <div v-else class="w-3.5 h-3.5 rounded-full border-2 border-[var(--line-2)]" />
          </div>
        </div>
        <div class="flex-1 min-w-0 pt-px">
          <span
            class="text-sm font-medium"
            :class="docsStatus === 'active' ? 'text-[var(--ink-1)]' : 'text-[var(--ink-3)]'"
          >
            {{ docsStatus === 'active' ? 'Reading the columns...' : 'Columns documented' }}
          </span>
        </div>
      </div>
    </div>

    <!-- Retry button for failed profiling -->
    <button
      v-if="dataset.step === 'failed' && dataset.connectionId && stepStatus('profiling') === 'failed'"
      @click="retryProfiling(dataset.connectionId!)"
      class="mt-1.5 ml-6 text-sm text-[var(--ink-2)] bg-[var(--paper-2)] border border-[var(--line)] rounded px-2 py-0.5 hover:bg-[var(--paper-3)] transition-colors"
    >
      Retry
    </button>
  </div>
</template>

<script setup lang="ts">
import type { DatasetStatus } from '~/composables/useDatasetStatus'

type StepName = 'uploading' | 'schema' | 'profiling'
type StepState = 'completed' | 'active' | 'pending' | 'failed'

const props = defineProps<{
  dataset: DatasetStatus
  /** Omit to hide the documentation step entirely (the info panel does). */
  docsStatus?: StepState | null
}>()

const { retryProfiling } = useDatasetStatus()

const STEP_ORDER: StepName[] = ['uploading', 'schema', 'profiling']

function stepStatus(stepName: StepName): StepState {
  const ds = props.dataset
  const stepIdx = STEP_ORDER.indexOf(stepName)
  const currentIdx = STEP_ORDER.indexOf(ds.step as StepName)

  // If dataset is ready, all steps are completed
  if (ds.step === 'ready') return 'completed'

  // If dataset failed, determine which step failed and derive states
  if (ds.step === 'failed') {
    let failedIdx: number
    if (ds.error === 'Upload failed') failedIdx = 0
    else if (!ds.connectionId) failedIdx = 1
    else failedIdx = 2

    if (stepIdx < failedIdx) return 'completed'
    if (stepIdx === failedIdx) return 'failed'
    return 'pending'
  }

  if (stepIdx < currentIdx) return 'completed'
  if (stepIdx === currentIdx) return 'active'
  return 'pending'
}

const formatSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// Live clock for active steps — ticks every second
const currentTime = ref(new Date().toISOString())
let clockInterval: ReturnType<typeof setInterval> | null = null
onMounted(() => { clockInterval = setInterval(() => { currentTime.value = new Date().toISOString() }, 1000) })
onUnmounted(() => { if (clockInterval) clearInterval(clockInterval) })

function stepTimestampFor(step: StepName): string | null {
  const ds = props.dataset
  const status = stepStatus(step)
  if (status === 'active') return currentTime.value
  if (status === 'completed') {
    if (step === 'uploading') return ds.uploadedAt
    if (step === 'schema') return ds.schemaBuiltAt
    if (step === 'profiling') return ds.completedAt
  }
  return null
}
</script>

<style scoped>
.docs-spin {
  animation: docs-spin 2s linear infinite;
}

@keyframes docs-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
