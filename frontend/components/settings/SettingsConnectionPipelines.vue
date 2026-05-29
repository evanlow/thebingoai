<template>
  <div class="flex flex-col gap-3">
    <div class="flex items-center justify-between shrink-0">
      <span class="text-xs font-semibold text-gray-400 dark:text-neutral-500 uppercase tracking-widest">
        Pipelines<template v-if="pipelines.length"> · {{ pipelines.length }}</template>
      </span>
      <UiButton
        v-if="pipelines.length"
        variant="outline"
        size="sm"
        :loading="loading"
        @click="refresh"
      >
        <RefreshCw class="h-3.5 w-3.5" />
        Refresh
      </UiButton>
    </div>

    <div v-if="loading && !pipelines.length" class="space-y-2">
      <UiSkeleton class="h-12 w-full rounded-lg" />
      <UiSkeleton class="h-12 w-full rounded-lg" />
    </div>

    <div
      v-else-if="!loading && !pipelines.length"
      class="text-sm text-gray-400 dark:text-neutral-500 italic"
    >
      No pipelines yet for this connection.
    </div>

    <div v-else class="flex flex-col gap-2">
      <div
        v-for="p in pipelines"
        :key="p.id"
        class="border border-gray-200 dark:border-neutral-700 rounded-lg p-3 bg-white dark:bg-neutral-800/40"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <p class="text-sm font-medium text-gray-900 dark:text-neutral-100 truncate">
                {{ p.name }}
              </p>
              <span
                :class="[
                  'px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider',
                  p.mode === 'incremental'
                    ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300'
                    : 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300',
                ]"
              >
                {{ p.mode }}
              </span>
              <span
                v-if="lastRunBadge(p)"
                :class="[
                  'px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider',
                  lastRunBadge(p)!.color,
                ]"
              >
                {{ lastRunBadge(p)!.label }}
              </span>
            </div>
            <p class="text-xs text-gray-500 dark:text-neutral-400 mt-1 font-mono truncate">
              {{ p.target_table }}
            </p>
            <div class="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs text-gray-500 dark:text-neutral-400">
              <p v-if="p.incremental_key">
                <span class="text-gray-400">cursor:</span>
                <span class="font-mono ml-1">{{ p.incremental_key }}</span>
              </p>
              <p v-if="p.cron">
                <span class="text-gray-400">cron:</span>
                <span class="font-mono ml-1">{{ p.cron }}</span>
              </p>
              <p v-if="p.last_run_at">
                <span class="text-gray-400">last:</span>
                <span class="ml-1">{{ formatRelative(p.last_run_at) }}</span>
              </p>
              <p v-if="p.next_run_at">
                <span class="text-gray-400">next:</span>
                <span class="ml-1">{{ formatRelative(p.next_run_at) }}</span>
              </p>
            </div>
            <p
              v-if="p.mode === 'incremental' && !hasUniqueKey(p)"
              class="mt-2 text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1"
            >
              <AlertTriangle class="h-3 w-3 shrink-0" />
              No primary key — backfills may duplicate rows.
            </p>
          </div>
          <div class="flex flex-col gap-1 shrink-0">
            <UiButton
              variant="outline"
              size="xs"
              :loading="busyId === p.id && busyAction === 'run'"
              @click="runNow(p)"
            >
              <Play class="h-3 w-3" />
              Run now
            </UiButton>
            <UiButton
              variant="outline"
              size="xs"
              :loading="busyId === p.id && busyAction === 'redetect'"
              @click="redetect(p)"
            >
              <Sparkles class="h-3 w-3" />
              Re-detect
            </UiButton>
            <UiButton
              variant="outline"
              size="xs"
              @click="openOverride(p)"
            >
              <Pencil class="h-3 w-3" />
              Edit
            </UiButton>
            <UiButton
              v-if="p.mode === 'incremental'"
              variant="outline"
              size="xs"
              @click="openBackfill(p)"
            >
              <Clock class="h-3 w-3" />
              Load history
            </UiButton>
          </div>
        </div>
      </div>
    </div>

    <!-- Override dialog -->
    <UiDialog v-model:open="overrideOpen" size="sm">
      <template #header>
        <span class="text-lg font-medium">Edit pipeline cursor</span>
      </template>
      <div class="space-y-4">
        <p class="text-xs text-gray-500 dark:text-neutral-400">
          {{ overrideTarget?.name }}
        </p>
        <div>
          <label class="text-sm font-normal mb-1.5 block">Mode</label>
          <select
            v-model="overrideForm.mode"
            class="w-full border border-gray-300 dark:border-neutral-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-neutral-800 text-gray-900 dark:text-neutral-100"
          >
            <option value="incremental">Incremental (cursor-based)</option>
            <option value="full">Full snapshot</option>
          </select>
        </div>
        <div v-if="overrideForm.mode === 'incremental'">
          <label class="text-sm font-normal mb-1.5 block">Cursor column</label>
          <input
            v-model="overrideForm.incremental_key"
            type="text"
            placeholder="created_at"
            class="w-full border border-gray-300 dark:border-neutral-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-neutral-800 text-gray-900 dark:text-neutral-100 font-mono"
          />
        </div>
      </div>
      <template #footer>
        <UiButton variant="outline" @click="overrideOpen = false">Cancel</UiButton>
        <UiButton :loading="overrideSaving" @click="saveOverride">Save</UiButton>
      </template>
    </UiDialog>

    <!-- Re-detect result dialog -->
    <UiDialog v-model:open="redetectOpen" size="sm">
      <template #header>
        <span class="text-lg font-medium">Watermark suggestion</span>
      </template>
      <div class="space-y-3 text-sm">
        <p class="text-xs text-gray-500 dark:text-neutral-400">
          {{ redetectTarget?.name }}
        </p>
        <div class="grid grid-cols-2 gap-2 p-3 bg-gray-50 dark:bg-neutral-800/60 rounded-lg">
          <div>
            <p class="text-[10px] uppercase tracking-wider text-gray-400">Current</p>
            <p class="font-mono">
              {{ redetectTarget?.incremental_key ?? '—' }}
            </p>
          </div>
          <div>
            <p class="text-[10px] uppercase tracking-wider text-gray-400">Suggested</p>
            <p class="font-mono">
              {{ redetectResult?.suggested_incremental_key ?? '—' }}
            </p>
          </div>
        </div>
        <p
          v-if="!redetectResult?.suggested_incremental_key"
          class="text-xs text-gray-500 dark:text-neutral-400"
        >
          Classifier found no usable cursor for this table.
        </p>
      </div>
      <template #footer>
        <UiButton variant="outline" @click="redetectOpen = false">Close</UiButton>
        <UiButton
          v-if="redetectResult?.suggested_incremental_key
            && redetectResult.suggested_incremental_key !== redetectTarget?.incremental_key"
          :loading="overrideSaving"
          @click="acceptRedetect"
        >
          Use suggestion
        </UiButton>
      </template>
    </UiDialog>

    <!-- Backfill dialog -->
    <UiDialog v-model:open="backfillOpen" size="sm">
      <template #header>
        <span class="text-lg font-medium">Load history</span>
      </template>
      <div class="space-y-4">
        <p class="text-xs text-gray-500 dark:text-neutral-400">
          {{ backfillTarget?.name }}
        </p>
        <p class="text-xs text-gray-500 dark:text-neutral-400">
          Triggers a one-off run that pulls rows where
          <code class="font-mono">{{ backfillTarget?.incremental_key }}</code>
          is at or after the chosen point. Off-schedule — does not affect the
          next cron run. Existing rows are de-duplicated by primary key when
          present.
        </p>
        <div>
          <label class="text-sm font-normal mb-1.5 block">Pull rows since</label>
          <input
            v-model="backfillForm.since"
            type="datetime-local"
            class="w-full border border-gray-300 dark:border-neutral-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-neutral-800 text-gray-900 dark:text-neutral-100"
          />
        </div>
        <p
          v-if="backfillTarget && !hasUniqueKey(backfillTarget)"
          class="text-xs text-amber-600 dark:text-amber-400 flex items-start gap-1"
        >
          <AlertTriangle class="h-3 w-3 shrink-0 mt-0.5" />
          This table has no primary key — backfilled rows may duplicate existing ones.
        </p>
      </div>
      <template #footer>
        <UiButton variant="outline" @click="backfillOpen = false">Cancel</UiButton>
        <UiButton
          :loading="backfillSaving"
          :disabled="!backfillForm.since"
          @click="runBackfill"
        >
          Start
        </UiButton>
      </template>
    </UiDialog>
  </div>
</template>

<script setup lang="ts">
import { AlertTriangle, Clock, Pencil, Play, RefreshCw, Sparkles } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type { PipelineRow, RedetectResponse } from '~/utils/api/pipelinesApi'
import { localInputToUtcIso, toLocalInputValue } from '~/utils/backfillTime'

const props = defineProps<{ connectionId: number }>()

const api = useApi() as any

const pipelines = ref<PipelineRow[]>([])
const loading = ref(false)
const busyId = ref<string | null>(null)
const busyAction = ref<string | null>(null)

const overrideOpen = ref(false)
const overrideTarget = ref<PipelineRow | null>(null)
const overrideForm = ref<{ mode: string; incremental_key: string }>({ mode: 'incremental', incremental_key: '' })
const overrideSaving = ref(false)

const redetectOpen = ref(false)
const redetectTarget = ref<PipelineRow | null>(null)
const redetectResult = ref<RedetectResponse | null>(null)

const backfillOpen = ref(false)
const backfillTarget = ref<PipelineRow | null>(null)
const backfillForm = ref<{ since: string }>({ since: '' })
const backfillSaving = ref(false)

function hasUniqueKey(p: PipelineRow): boolean {
  return Array.isArray(p.unique_key) && p.unique_key.length > 0
}

function lastRunBadge(p: PipelineRow): { label: string; color: string } | null {
  const status = p.last_run_status
  if (!status) return null
  if (status === 'success') return { label: 'success', color: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300' }
  if (status === 'running') return { label: 'running', color: 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300' }
  if (status === 'failed') return { label: 'failed', color: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300' }
  if (status === 'stale') return { label: 'stale', color: 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300' }
  return { label: status, color: 'bg-gray-100 dark:bg-neutral-800 text-gray-600 dark:text-neutral-400' }
}

function formatRelative(iso: string): string {
  const d = new Date(iso)
  const diffMs = Date.now() - d.getTime()
  const sec = Math.round(diffMs / 1000)
  if (Math.abs(sec) < 60) return sec >= 0 ? `${sec}s ago` : `in ${-sec}s`
  const min = Math.round(sec / 60)
  if (Math.abs(min) < 60) return min >= 0 ? `${min}m ago` : `in ${-min}m`
  const hr = Math.round(min / 60)
  if (Math.abs(hr) < 24) return hr >= 0 ? `${hr}h ago` : `in ${-hr}h`
  const day = Math.round(hr / 24)
  return day >= 0 ? `${day}d ago` : `in ${-day}d`
}

async function refresh() {
  loading.value = true
  try {
    const all: PipelineRow[] = await api.pipelines.list()
    pipelines.value = (Array.isArray(all) ? all : [])
      .filter(p => p.source_connection_id === props.connectionId)
  } catch (e: any) {
    toast.error('Failed to load pipelines', { description: e?.message ?? String(e) })
  } finally {
    loading.value = false
  }
}

async function runNow(p: PipelineRow) {
  busyId.value = p.id
  busyAction.value = 'run'
  try {
    await api.pipelines.run(p.id)
    toast.success('Run queued', { description: p.name })
    // Run is async via Celery — poll once after a short delay so the user sees
    // the row flip to `running` (and eventually `success`/`failed`) without
    // having to click Refresh. Tighter than a stream, simpler than SSE.
    setTimeout(() => { void refresh() }, 1500)
  } catch (e: any) {
    toast.error('Run failed', { description: e?.message ?? String(e) })
  } finally {
    busyId.value = null
    busyAction.value = null
  }
}

async function redetect(p: PipelineRow) {
  busyId.value = p.id
  busyAction.value = 'redetect'
  try {
    const result: RedetectResponse = await api.pipelines.redetect(p.id)
    redetectTarget.value = p
    redetectResult.value = result
    redetectOpen.value = true
  } catch (e: any) {
    toast.error('Re-detect failed', { description: e?.message ?? String(e) })
  } finally {
    busyId.value = null
    busyAction.value = null
  }
}

function openOverride(p: PipelineRow) {
  overrideTarget.value = p
  overrideForm.value = {
    mode: p.mode,
    incremental_key: p.incremental_key ?? '',
  }
  overrideOpen.value = true
}

async function saveOverride() {
  if (!overrideTarget.value) return
  if (overrideForm.value.mode === 'incremental' && !overrideForm.value.incremental_key.trim()) {
    toast.error('Cursor column required for incremental mode')
    return
  }
  overrideSaving.value = true
  try {
    const updated: PipelineRow = await api.pipelines.override(overrideTarget.value.id, {
      mode: overrideForm.value.mode,
      incremental_key: overrideForm.value.mode === 'incremental'
        ? overrideForm.value.incremental_key.trim()
        : null,
    })
    const idx = pipelines.value.findIndex(p => p.id === updated.id)
    if (idx !== -1) pipelines.value[idx] = updated
    overrideOpen.value = false
    redetectOpen.value = false
    toast.success('Pipeline updated')
  } catch (e: any) {
    toast.error('Save failed', { description: e?.message ?? String(e) })
  } finally {
    overrideSaving.value = false
  }
}

async function acceptRedetect() {
  if (!redetectTarget.value || !redetectResult.value?.suggested_incremental_key) return
  overrideTarget.value = redetectTarget.value
  overrideForm.value = {
    mode: 'incremental',
    incremental_key: redetectResult.value.suggested_incremental_key,
  }
  await saveOverride()
}

function openBackfill(p: PipelineRow) {
  backfillTarget.value = p
  // default to 30 days ago, rendered in the user's local timezone
  const d = new Date(Date.now() - 30 * 86400_000)
  backfillForm.value = { since: toLocalInputValue(d) }
  backfillOpen.value = true
}

async function runBackfill() {
  if (!backfillTarget.value || !backfillForm.value.since) return
  backfillSaving.value = true
  try {
    // datetime-local is local wall-clock → convert to the UTC instant the
    // backend expects (avoids the prior bug of tagging local time as +00:00).
    const since = localInputToUtcIso(backfillForm.value.since)
    await api.pipelines.backfill(backfillTarget.value.id, since)
    backfillOpen.value = false
    toast.success('Backfill queued', { description: backfillTarget.value.name })
    setTimeout(() => { void refresh() }, 1500)
  } catch (e: any) {
    toast.error('Backfill failed', { description: e?.message ?? String(e) })
  } finally {
    backfillSaving.value = false
  }
}

watch(() => props.connectionId, () => { void refresh() }, { immediate: true })
</script>
