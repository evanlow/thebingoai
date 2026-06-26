<!--
  SettingsConnectionSync — Parquet sync configuration for one Postgres/MySQL
  connection. Renders inside the connection edit dialog when db_type is
  postgres/mysql. Manages a single Pipeline per connection (MVP); list/create/
  edit/run/delete via /api/pipelines.

  The "Parquet • synced X ago" badge on widgets reads from the same pipeline
  rows this component manages.
-->
<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between">
      <span class="text-xs font-semibold text-gray-400 dark:text-neutral-500 uppercase tracking-widest">
        Parquet sync
      </span>
    </div>

    <!-- Loading existing -->
    <div v-if="loading" class="flex items-center gap-2 text-sm text-gray-400">
      <Loader2 class="h-4 w-4 animate-spin" /> Loading…
    </div>

    <!-- Existing pipeline -->
    <div
      v-else-if="pipeline && !editing"
      class="border border-gray-200 dark:border-neutral-700 rounded-lg p-3 space-y-2"
    >
      <div class="text-sm text-gray-900 dark:text-neutral-100 font-medium">{{ pipeline.name }}</div>
      <dl class="text-xs text-gray-600 dark:text-neutral-400 space-y-1">
        <div class="flex justify-between"><dt>Tables</dt><dd class="font-mono">{{ tableCountLabel }}</dd></div>
        <div class="flex justify-between"><dt>Schedule</dt><dd class="font-mono">{{ (isNewModel ? activeSchedule?.cron : pipeline.cron) ?? 'manual only' }} <span class="text-gray-400">{{ isNewModel ? activeSchedule?.timezone : pipeline.timezone }}</span></dd></div>
        <div class="flex justify-between"><dt>Last run</dt><dd>{{ pipeline.last_run_at ? formatRelative(pipeline.last_run_at) : '—' }}<template v-if="pipeline.last_run_status"> · {{ pipeline.last_run_status }}</template><template v-if="!effectiveEnabled"> · disabled</template></dd></div>
        <div class="flex justify-between"><dt>Next run</dt><dd>{{ pipeline.next_run_at ? formatRelative(pipeline.next_run_at) : '—' }}</dd></div>
      </dl>
      <div class="flex flex-wrap items-center gap-2 pt-1">
        <UiButton variant="outline" size="sm" :loading="running" @click="runNow">
          <Play class="h-3.5 w-3.5" /> Sync now
        </UiButton>
        <UiButton variant="outline" size="sm" @click="startEdit">
          <Pencil class="h-3.5 w-3.5" /> Edit
        </UiButton>
        <UiButton variant="outline" size="sm" :loading="redetecting" @click="redetectCursor">
          <Search class="h-3.5 w-3.5" /> Re-detect cursor
        </UiButton>
        <UiButton variant="outline" size="sm" @click="showLoadHistory = true">
          <History class="h-3.5 w-3.5" /> Load history
        </UiButton>
        <UiButton variant="outline" size="sm" @click="toggleEnabled">
          <Power class="h-3.5 w-3.5" /> {{ effectiveEnabled ? 'Disable' : 'Enable' }}
        </UiButton>
        <UiButton variant="danger" size="sm" :loading="deleting" @click="remove">
          <Trash2 class="h-3.5 w-3.5" /> Delete
        </UiButton>
      </div>

      <!-- Load-history modal -->
      <div
        v-if="showLoadHistory"
        class="mt-2 border border-violet-300 dark:border-violet-700 rounded-lg p-3 space-y-2 bg-violet-50/40 dark:bg-violet-900/10"
      >
        <div class="text-xs font-medium text-gray-900 dark:text-neutral-100">
          Load history from a specific date
        </div>
        <p class="text-[11px] text-gray-500 dark:text-neutral-400">
          Backfills rows with <code class="font-mono">{{ pipeline.incremental_key }} ≥ since</code>. Merge dedup keeps existing partitions intact.
        </p>
        <div class="flex items-center gap-2">
          <input
            v-model="loadHistorySince"
            type="datetime-local"
            class="border border-gray-300 dark:border-neutral-600 rounded px-2 py-1 text-sm bg-white dark:bg-neutral-800 font-mono"
          />
          <UiButton size="sm" :loading="loadingHistory" :disabled="!loadHistorySince" @click="runLoadHistory">
            Backfill
          </UiButton>
          <UiButton variant="outline" size="sm" @click="showLoadHistory = false">Cancel</UiButton>
        </div>
        <div v-if="loadHistoryError" class="text-[11px] text-red-600">{{ loadHistoryError }}</div>
      </div>
    </div>

    <!-- Create / edit form -->
    <form
      v-else
      class="border border-gray-200 dark:border-neutral-700 rounded-lg p-3 space-y-3"
      @submit.prevent="save"
    >
      <p v-if="!pipeline" class="text-xs text-gray-500 dark:text-neutral-400">
        Mirror source tables into Parquet on GCS. Dashboards query the snapshot via DuckDB instead of hitting the source DB live.
      </p>

      <div>
        <label class="block text-xs font-medium text-gray-700 dark:text-neutral-300 mb-1">Pipeline name</label>
        <input
          v-model="form.name"
          type="text"
          required
          maxlength="120"
          class="w-full border border-gray-300 dark:border-neutral-600 rounded px-2 py-1.5 text-sm bg-white dark:bg-neutral-800"
        />
      </div>

      <div>
        <label class="block text-xs font-medium text-gray-700 dark:text-neutral-300 mb-1">Tables to sync</label>
        <select
          v-model="form.tables"
          multiple
          required
          class="w-full border border-gray-300 dark:border-neutral-600 rounded px-2 py-1.5 text-sm bg-white dark:bg-neutral-800 h-32"
        >
          <option v-for="t in availableTables" :key="t" :value="t">{{ t }}</option>
        </select>
        <p class="text-[11px] text-gray-400 mt-0.5">
          Hold ⌘/Ctrl to select multiple.
          <template v-if="!availableTables.length">Refresh the connection schema first.</template>
        </p>
      </div>

      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-medium text-gray-700 dark:text-neutral-300 mb-1">Cron</label>
          <input
            v-model="form.cron"
            type="text"
            placeholder="0 2 * * *"
            class="w-full border border-gray-300 dark:border-neutral-600 rounded px-2 py-1.5 text-sm bg-white dark:bg-neutral-800 font-mono"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-700 dark:text-neutral-300 mb-1">Timezone</label>
          <input
            v-model="form.timezone"
            type="text"
            placeholder="UTC"
            class="w-full border border-gray-300 dark:border-neutral-600 rounded px-2 py-1.5 text-sm bg-white dark:bg-neutral-800"
          />
        </div>
      </div>

      <!-- Mode + cursor overrides (Phase 3). New-model schedules derive per-table
           mode/cursor server-side from the selected tables, so hide these there. -->
      <div v-if="!isNewModel" class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-medium text-gray-700 dark:text-neutral-300 mb-1">Mode</label>
          <select
            v-model="form.mode"
            class="w-full border border-gray-300 dark:border-neutral-600 rounded px-2 py-1.5 text-sm bg-white dark:bg-neutral-800"
          >
            <option value="full">Full snapshot</option>
            <option value="incremental">Incremental</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-700 dark:text-neutral-300 mb-1">Cursor column</label>
          <select
            v-model="form.incremental_key"
            :disabled="form.mode !== 'incremental'"
            class="w-full border border-gray-300 dark:border-neutral-600 rounded px-2 py-1.5 text-sm bg-white dark:bg-neutral-800 disabled:opacity-50"
          >
            <option value="">(none)</option>
            <option v-for="c in cursorCandidates" :key="c" :value="c">{{ c }}</option>
          </select>
          <p v-if="form.mode === 'incremental' && !form.incremental_key" class="text-[11px] text-amber-600 mt-0.5">
            Incremental mode requires a cursor column.
          </p>
        </div>
      </div>

      <div v-if="pkMissingForFirstTable" class="flex items-start gap-1.5 text-[11px] text-red-600 dark:text-red-400">
        <span class="inline-block h-2 w-2 mt-1 rounded-full bg-red-500" />
        <span>
          No PRIMARY KEY on <code class="font-mono">{{ form.tables[0] }}</code>. Merge dedup can't run — rerunning the pipeline may produce duplicates. Add a PK on the source or accept the risk.
        </span>
      </div>

      <div v-if="submitError" class="text-xs text-red-600 dark:text-red-400">{{ submitError }}</div>

      <div class="flex items-center justify-end gap-2 pt-1">
        <UiButton v-if="editing" variant="outline" size="sm" type="button" @click="cancelEdit">Cancel</UiButton>
        <UiButton size="sm" type="submit" :loading="saving">
          <Check class="h-3.5 w-3.5" /> {{ editing ? 'Save changes' : 'Create pipeline' }}
        </UiButton>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useAuthStore } from '~/stores/auth'
import { useApi } from '~/composables/useApi'
import type { DatabaseConnection, DatabaseSchema } from '~/types/connection'
import type { Pipeline, PipelineSchedule } from '~/utils/api/pipelinesApi'
import { Check, History, Loader2, Pencil, Play, Power, Search, Trash2 } from 'lucide-vue-next'

const props = defineProps<{
  connection: DatabaseConnection
  schema: DatabaseSchema | null
}>()

const auth = useAuthStore()
const api = useApi()

const loading = ref(true)
const saving = ref(false)
const deleting = ref(false)
const running = ref(false)
const redetecting = ref(false)
const editing = ref(false)
const submitError = ref<string | null>(null)
const pipeline = ref<Pipeline | null>(null)

const showLoadHistory = ref(false)
const loadingHistory = ref(false)
const loadHistorySince = ref('')
const loadHistoryError = ref<string | null>(null)

const form = ref({
  name: '',
  tables: [] as string[],
  cron: '0 2 * * *',
  timezone: 'UTC',
  mode: 'full' as 'full' | 'incremental',
  incremental_key: '' as string,
})

const availableTables = computed<string[]>(() => props.schema?.table_names ?? [])

// New-model pipelines carry cron + per-table specs on a PipelineSchedule row
// instead of Pipeline.cron / extraction_config.tables. Edit that schedule when present.
const activeSchedule = computed<PipelineSchedule | null>(() => pipeline.value?.schedules?.[0] ?? null)
const isNewModel = computed<boolean>(() => !!activeSchedule.value)
const scheduleTableNames = computed<string[]>(
  () => (activeSchedule.value?.tables ?? []).map((t) => t.source_table),
)
const effectiveEnabled = computed<boolean>(
  () => (isNewModel.value ? !!activeSchedule.value?.enabled : !!pipeline.value?.enabled),
)

// Summary shown in the Parquet sync panel — never the raw list. The Database
// Schema panel above renders the full tree with row counts; this row just
// reports how many tables the pipeline covers.
const tableCountLabel = computed<string>(() => {
  if (!pipeline.value) return '—'
  if (isNewModel.value) {
    const n = scheduleTableNames.value.length
    return n === 1 ? '1 table' : `${n} tables`
  }
  const cfg = pipeline.value.extraction_config || {}
  const list = Array.isArray(cfg.tables) ? cfg.tables : []
  if (list.length) return list.length === 1 ? '1 table' : `${list.length} tables`
  return pipeline.value.target_table || '—'
})

// Columns of the first selected table — drive cursor dropdown + PK check.
// `schema.schemas[<schemaName>].tables[<table>].columns` is the canonical
// shape from DatabaseSchema; fall back to `schema.tables[table]` for any
// alternate shape the older connector serializers emit.
function _columnsForTable(name: string): Array<Record<string, any>> {
  if (!name || !props.schema) return []
  const schemas = (props.schema as any).schemas || {}
  for (const schemaName of Object.keys(schemas)) {
    const t = schemas[schemaName]?.tables?.[name]
    if (t?.columns) return t.columns
  }
  const tables = (props.schema as any).tables || {}
  return tables?.[name]?.columns ?? []
}

const cursorCandidates = computed<string[]>(() => {
  const cols = _columnsForTable(form.value.tables[0] || '')
  // Filter to plausible cursor columns — temporal types or auto-increment ids.
  return cols
    .filter((c: any) => {
      const t = String(c.type || '').toLowerCase()
      const n = String(c.name || '').toLowerCase()
      if (t.includes('date') || t.includes('time') || t.includes('timestamp')) return true
      if (/_at$|_ts$|_date$|_time$/.test(n)) return true
      if ((t.includes('int') || t.includes('serial')) && n.endsWith('_id')) return true
      return false
    })
    .map((c: any) => String(c.name))
})

const pkMissingForFirstTable = computed<boolean>(() => {
  const cols = _columnsForTable(form.value.tables[0] || '')
  if (!cols.length) return false
  return !cols.some((c: any) => c.primary_key === true)
})

function formatRelative(ts: string): string {
  const t = new Date(ts).getTime()
  const diff = Date.now() - t
  if (Number.isNaN(t)) return ts
  const future = diff < 0
  const abs = Math.abs(diff)
  const m = Math.floor(abs / 60000)
  if (m < 1) return future ? 'in <1 min' : 'just now'
  if (m < 60) return future ? `in ${m}m` : `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return future ? `in ${h}h` : `${h}h ago`
  const d = Math.floor(h / 24)
  return future ? `in ${d}d` : `${d}d ago`
}

async function load() {
  loading.value = true
  try {
    const list = await api.pipelines.listForConnection(props.connection.id)
    pipeline.value = list[0] ?? null
    if (pipeline.value) hydrateFormFromPipeline()
    else seedDefaultForm()
  } catch (e) {
    console.error('Failed to load pipelines for connection', e)
  } finally {
    loading.value = false
  }
}

function seedDefaultForm() {
  form.value = {
    name: `${props.connection.name} sync`,
    tables: [],
    cron: '0 2 * * *',
    timezone: 'UTC',
    mode: 'full',
    incremental_key: '',
  }
}

function hydrateFormFromPipeline() {
  if (!pipeline.value) return
  // New-model: read cron + tables from the schedule, not the legacy Pipeline fields.
  if (activeSchedule.value) {
    const s = activeSchedule.value
    form.value = {
      name: pipeline.value.name,
      tables: scheduleTableNames.value,
      cron: s.cron ?? '',
      timezone: s.timezone || 'UTC',
      mode: 'full',
      incremental_key: '',
    }
    return
  }
  const cfg = pipeline.value.extraction_config || {}
  form.value = {
    name: pipeline.value.name,
    tables: Array.isArray(cfg.tables) ? cfg.tables : [],
    cron: pipeline.value.cron ?? '',
    timezone: pipeline.value.timezone || 'UTC',
    mode: (pipeline.value.mode === 'incremental' ? 'incremental' : 'full') as 'full' | 'incremental',
    incremental_key: pipeline.value.incremental_key ?? '',
  }
}

function startEdit() {
  hydrateFormFromPipeline()
  editing.value = true
  submitError.value = null
}

function cancelEdit() {
  editing.value = false
  submitError.value = null
}

async function save() {
  submitError.value = null
  if (!form.value.tables.length) {
    submitError.value = 'Pick at least one table to sync.'
    return
  }
  if (form.value.mode === 'incremental' && !form.value.incremental_key) {
    submitError.value = 'Incremental mode requires a cursor column.'
    return
  }
  saving.value = true
  try {
    if (pipeline.value && isNewModel.value && activeSchedule.value) {
      // New-model: edit the schedule (cron / timezone / tables). Per-table mode +
      // cursor are re-derived server-side from the selected tables.
      pipeline.value = await api.pipelines.updateSchedule(pipeline.value.id, activeSchedule.value.id, {
        cron: form.value.cron || null,
        timezone: form.value.timezone || 'UTC',
        tables: form.value.tables,
      })
      editing.value = false
    } else if (pipeline.value) {
      // PATCH covers schedule + name + enabled + mode/cursor overrides.
      // Table changes still require delete + recreate.
      pipeline.value = await api.pipelines.update(pipeline.value.id, {
        name: form.value.name,
        cron: form.value.cron || null,
        timezone: form.value.timezone || 'UTC',
        mode: form.value.mode,
        // Empty string explicitly clears the cursor (full snapshot).
        incremental_key: form.value.mode === 'incremental' ? form.value.incremental_key : '',
      })
      editing.value = false
    } else {
      // Create — pipeline owner is the current user (user-scoped sync)
      if (!auth.user?.id) throw new Error('Not authenticated')
      pipeline.value = await api.pipelines.create({
        name: form.value.name,
        source_connection_id: props.connection.id,
        owner_scope_kind: 'user',
        owner_scope_id: auth.user.id,
        target_table: form.value.tables[0],
        cron: form.value.cron || null,
        timezone: form.value.timezone || 'UTC',
        mode: form.value.mode,
        incremental_key: form.value.mode === 'incremental' ? form.value.incremental_key : null,
        extraction_config: { tables: form.value.tables },
      })
    }
  } catch (e: any) {
    submitError.value = e?.message ?? String(e)
  } finally {
    saving.value = false
  }
}

async function redetectCursor() {
  if (!pipeline.value) return
  redetecting.value = true
  try {
    pipeline.value = await api.pipelines.redetectWatermark(pipeline.value.id)
  } catch (e: any) {
    console.error('redetect_watermark failed', e)
    alert(`Re-detect failed: ${e?.message ?? String(e)}`)
  } finally {
    redetecting.value = false
  }
}

async function runLoadHistory() {
  if (!pipeline.value || !loadHistorySince.value) return
  loadHistoryError.value = null
  loadingHistory.value = true
  try {
    // datetime-local has no timezone — interpret as UTC.
    const sinceIso = new Date(loadHistorySince.value + 'Z').toISOString()
    await api.pipelines.loadHistory(pipeline.value.id, sinceIso)
    showLoadHistory.value = false
    loadHistorySince.value = ''
    setTimeout(load, 1500)
  } catch (e: any) {
    loadHistoryError.value = e?.message ?? String(e)
  } finally {
    loadingHistory.value = false
  }
}

async function runNow() {
  if (!pipeline.value) return
  running.value = true
  try {
    await api.pipelines.run(pipeline.value.id)
    // Refresh status after a brief delay (run is async)
    setTimeout(load, 1500)
  } catch (e) {
    console.error('Pipeline run trigger failed', e)
  } finally {
    running.value = false
  }
}

async function toggleEnabled() {
  if (!pipeline.value) return
  if (isNewModel.value && activeSchedule.value) {
    pipeline.value = await api.pipelines.updateSchedule(pipeline.value.id, activeSchedule.value.id, {
      enabled: !activeSchedule.value.enabled,
    })
    return
  }
  pipeline.value = await api.pipelines.update(pipeline.value.id, {
    enabled: !pipeline.value.enabled,
  })
}

async function remove() {
  if (!pipeline.value) return
  if (!confirm(`Delete pipeline "${pipeline.value.name}"? Materialized Parquet stays in place.`)) return
  deleting.value = true
  try {
    await api.pipelines.delete(pipeline.value.id)
    pipeline.value = null
    seedDefaultForm()
  } catch (e) {
    console.error('Pipeline delete failed', e)
  } finally {
    deleting.value = false
  }
}

watch(() => props.connection.id, () => { load() })
onMounted(load)
</script>
