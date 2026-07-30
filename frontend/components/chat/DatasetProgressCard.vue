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

    <!-- Horizontal timeline -->
    <div class="flex items-start">
      <DatasetTimelineStep
        :status="stepStatus('uploading')"
        label="Uploaded"
        active-label="Uploading..."
        :timestamp="stepTimestampFor('uploading')"
        :is-last="false"
      />
      <DatasetTimelineStep
        :status="stepStatus('schema')"
        label="Schema built"
        active-label="Building schema..."
        :timestamp="stepTimestampFor('schema')"
        :is-last="false"
        :prev-status="stepStatus('uploading')"
      />
      <DatasetTimelineStep
        :status="stepStatus('profiling')"
        label="Data profiled"
        active-label="Profiling data..."
        :timestamp="stepTimestampFor('profiling')"
        :is-last="false"
        :prev-status="stepStatus('schema')"
      />
      <DatasetTimelineStep
        :status="stepStatus('documenting')"
        label="Columns documented"
        active-label="Reading the columns..."
        :timestamp="stepTimestampFor('documenting')"
        :is-last="true"
        :prev-status="stepStatus('profiling')"
      />
    </div>

    <!-- Failure detail sits under the whole row: a step column is too narrow for it -->
    <p v-if="dataset.step === 'failed' && dataset.error" class="mt-1.5 text-sm text-red-400">
      {{ dataset.error }}
    </p>

    <!-- What Bingo read the columns as. Collapsed by default — it is a review
         prompt, not something to read every time. -->
    <div v-if="docsColumns.length > 0" class="mt-2 pt-2 border-t border-dashed border-[var(--line)]">
      <button
        type="button"
        data-testid="docs-toggle"
        class="flex items-center gap-1.5 text-sm text-[var(--ink-2)] hover:text-[var(--ink-1)] transition-colors"
        :aria-expanded="docsExpanded"
        @click="docsExpanded = !docsExpanded"
      >
        <span class="inline-block transition-transform" :class="docsExpanded ? 'rotate-90' : ''">▸</span>
        I read {{ docsColumns.length }} column{{ docsColumns.length === 1 ? '' : 's' }} — review
      </button>

      <div v-if="docsExpanded" data-testid="docs-body" class="mt-2">
        <p v-if="docs?.table_description" class="text-sm text-[var(--ink-2)] mb-1.5">
          {{ docs.table_description }}
        </p>
        <div class="overflow-x-auto">
          <table class="w-full text-sm border-collapse">
            <thead>
              <tr class="text-left text-[var(--ink-3)] border-b border-[var(--line)]">
                <th class="font-normal pb-1 pr-3">Column</th>
                <th class="font-normal pb-1 pr-3">Reads as</th>
                <th class="font-normal pb-1">Meaning</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="col in docsColumns"
                :key="col.name"
                class="align-top border-b border-[var(--line)] last:border-0"
              >
                <td class="py-1 pr-3 font-mono text-[var(--ink-1)] whitespace-nowrap">{{ col.name }}</td>
                <td class="py-1 pr-3 text-[var(--ink-2)]">{{ col.display_name }}</td>
                <td class="py-1 text-[var(--ink-2)]">{{ col.description }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="mt-2 text-sm text-[var(--ink-3)]">Tell me anything I've read wrong.</p>
      </div>
    </div>

    <!-- Retry button for failed profiling -->
    <button
      v-if="dataset.step === 'failed' && dataset.connectionId && stepStatus('profiling') === 'failed'"
      @click="emit('retry', dataset.connectionId!)"
      class="mt-1.5 text-sm text-[var(--ink-2)] bg-[var(--paper-2)] border border-[var(--line)] rounded px-2 py-0.5 hover:bg-[var(--paper-3)] transition-colors"
    >
      Retry
    </button>
  </div>
</template>

<script setup lang="ts">
import type { DatasetStatus } from '~/composables/useDatasetStatus'
import type { DatasetDocsColumn } from '~/stores/chat'

type StepName = 'uploading' | 'schema' | 'profiling' | 'documenting'
type StepState = 'completed' | 'active' | 'pending' | 'failed'

const props = defineProps<{
  dataset: DatasetStatus
}>()

// Retry is delegated to the parent, which already holds a useDatasetStatus
// instance. Calling it here would give every card on screen its own ws
// subscription, poller set and REST reload over all the same datasets.
const emit = defineEmits<{ retry: [connectionId: number] }>()

const chatStore = useChatStore()
const api = useApi()

const STEP_ORDER: StepName[] = ['uploading', 'schema', 'profiling', 'documenting']

// --- Documentation ---------------------------------------------------------

const docsExpanded = ref(false)
const docs = computed(() =>
  props.dataset.connectionId != null
    ? chatStore.datasetDocs[props.dataset.connectionId]
    : undefined
)
const docsColumns = computed<DatasetDocsColumn[]>(() => docs.value?.columns ?? [])

/**
 * A thread loaded from history never saw the `dataset.docs` event, so the card
 * fetches the stored glossary itself. Keys are `table.column`; the order follows
 * the connection's saved context, which is not the schema's order.
 */
async function loadDocsFromHistory() {
  const connectionId = props.dataset.connectionId
  if (connectionId == null || chatStore.datasetDocs[connectionId]) return
  try {
    const layer = await api.connections.getSemantics(connectionId) as {
      glossary?: Record<string, { display_name?: string; description?: string }>
    }
    const glossary = layer?.glossary ?? {}
    const tableName = `csv_${connectionId}`
    const columns: DatasetDocsColumn[] = []
    let tableDescription: string | null = null

    for (const [key, entry] of Object.entries(glossary)) {
      if (!entry || typeof entry !== 'object') continue
      if (key === tableName) { tableDescription = entry.description ?? null; continue }
      if (!key.startsWith(`${tableName}.`)) continue
      if (!entry.display_name && !entry.description) continue
      columns.push({
        name: key.slice(tableName.length + 1),
        display_name: entry.display_name ?? null,
        description: entry.description ?? null,
      })
    }
    if (columns.length === 0 && !tableDescription) return

    chatStore.setDatasetDocs({
      connection_id: connectionId,
      table_name: tableName,
      filename: props.dataset.name,
      table_description: tableDescription,
      columns,
      total_columns: columns.length,
    })
  } catch {
    // No documentation to show — the card is still useful without it.
  }
}

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
onMounted(() => {
  clockInterval = setInterval(() => { currentTime.value = new Date().toISOString() }, 1000)
  loadDocsFromHistory()
})
onUnmounted(() => { if (clockInterval) clearInterval(clockInterval) })

function stepTimestampFor(step: StepName): string | null {
  const ds = props.dataset
  const status = stepStatus(step)
  if (status === 'active') return currentTime.value
  if (status === 'completed') {
    if (step === 'uploading') return ds.uploadedAt
    if (step === 'schema') return ds.schemaBuiltAt
    // Profiling and documentation both finish at completedAt: the dataset only
    // reports one completion time, and documenting is what makes it 'ready'.
    if (step === 'profiling' || step === 'documenting') return ds.completedAt
  }
  return null
}
</script>
