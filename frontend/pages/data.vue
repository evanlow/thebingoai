<template>
  <div class="flex flex-1 flex-col overflow-hidden bg-[var(--paper-0)]">
    <!-- Header -->
    <div class="flex items-end justify-between gap-6 px-8 pt-5 pb-5 border-b border-[var(--line)] flex-shrink-0">
      <div class="min-w-0">
        <p class="eyebrow mb-1.5">Data · Catalog</p>
        <h1 class="settings-h1 text-[34px] leading-[1.02] tracking-[-0.02em] text-[var(--ink-0)]">
          What your AI <em class="font-normal italic text-[var(--ember)]">understands</em>
        </h1>
        <p class="mt-2 max-w-[560px] text-[13.5px] leading-relaxed text-[var(--ink-2)]">
          Document cryptic columns so agents read your data the way you do.
        </p>
      </div>
      <div class="flex items-center gap-2 flex-shrink-0">
        <button
          v-if="dirty"
          @click="saveSemantics"
          :disabled="saving"
          class="inline-flex items-center gap-1.5 rounded-lg bg-[var(--brand-indigo)] px-3.5 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          <Loader2 v-if="saving" class="h-3.5 w-3.5 animate-spin" />
          <Save v-else class="h-3.5 w-3.5" />
          {{ saving ? 'Saving…' : 'Save changes' }}
        </button>
        <button
          v-if="selectedConn && tables.length"
          @click="startGeneration"
          :disabled="generating"
          class="inline-flex items-center gap-1.5 rounded-lg bg-[var(--ember)] px-3.5 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          :title="checkedTables.size ? `Draft docs for ${checkedTables.size} selected table(s)` : 'Draft docs for the current table'"
        >
          <Loader2 v-if="generating" class="h-3.5 w-3.5 animate-spin" />
          <Sparkles v-else class="h-3.5 w-3.5" />
          {{ generating ? `Drafting ${genProgress}…` : `Generate docs${genButtonCount}` }}
        </button>
      </div>
    </div>

    <!-- Generation confirm banner -->
    <div
      v-if="confirmingGen"
      class="mx-7 mt-3 flex items-center gap-3 rounded-lg border border-[var(--ember)] bg-[var(--ember-wash)] px-4 py-2.5 text-sm text-[var(--ink-0)]"
    >
      <Sparkles class="h-4 w-4 flex-shrink-0 text-[var(--ember)]" />
      <span>Send {{ genTargetTables.length }} table schema{{ genTargetTables.length === 1 ? '' : 's' }} to the AI to draft descriptions? Values for columns you marked sensitive are excluded.</span>
      <button @click="confirmGeneration" class="ml-auto flex-shrink-0 rounded-md bg-[var(--ember)] px-2.5 py-1 text-xs font-medium text-white hover:opacity-90">Generate</button>
      <button @click="confirmingGen = false" class="flex-shrink-0 rounded-md px-2.5 py-1 text-xs text-[var(--ink-2)] hover:text-[var(--ink-0)]">Cancel</button>
    </div>

    <div class="flex flex-1 overflow-hidden min-h-0">
      <!-- Master pane: connections, with the active one's tables nested inline -->
      <aside class="w-64 flex-shrink-0 border-r border-[var(--line)] bg-[var(--paper-1)] flex flex-col min-h-0">
        <div class="px-4 pt-4 pb-3 flex-shrink-0">
          <p class="eyebrow mb-2.5">Connections</p>
          <div class="relative">
            <Search class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--ink-3)]" />
            <input
              v-model="tableSearch"
              type="text"
              placeholder="Search tables…"
              class="w-full rounded-md border border-[var(--line)] bg-[var(--paper-2)] pl-8 pr-2.5 py-1.5 text-sm text-[var(--ink-0)] placeholder:text-[var(--ink-3)] focus:outline-none focus:border-[var(--ember)]"
            />
          </div>
          <div class="mt-2.5 flex items-center gap-2 text-xs text-[var(--ink-2)]">
            <span class="font-mono text-[10.5px]">{{ documentedCount }}/{{ tables.length }} documented</span>
            <label class="ml-auto flex items-center gap-1.5 cursor-pointer select-none">
              <input type="checkbox" v-model="onlyUndocumented" class="accent-[var(--ember)]" />
              undocumented
            </label>
          </div>
          <div v-if="checkedTables.size" class="mt-1.5 flex items-center gap-1 text-xs font-medium text-[var(--ember)]">
            <CheckSquare class="h-3 w-3" />{{ checkedTables.size }} selected for generation
          </div>
        </div>

        <div class="flex-1 overflow-y-auto border-t border-[var(--line)] pb-2">
          <div v-if="loadingConns" class="space-y-1 px-3 pt-2">
            <UiSkeleton v-for="i in 5" :key="i" class="h-9 w-full rounded-md" />
          </div>
          <div v-else-if="connections.length === 0" class="px-4 py-6">
            <UiEmptyState title="No connections" description="Add a data source to start documenting it." :icon="Database" />
          </div>

          <template v-for="c in connections" :key="c.id">
            <!-- connection row -->
            <button
              @click="selectConnection(c)"
              class="flex w-full items-center gap-2.5 px-4 py-2.5 text-left transition-colors border-l-2"
              :class="selectedConn?.id === c.id ? 'border-[var(--ember)] bg-[var(--ember-wash)]' : 'border-transparent hover:bg-[var(--paper-2)]'"
            >
              <ConnectorAvatar :db-type="c.db_type" :icon-html="connectorIcons[c.db_type]" size="sm" />
              <span class="min-w-0 flex-1">
                <span
                  class="block truncate text-[12.5px]"
                  :class="selectedConn?.id === c.id ? 'font-semibold text-[var(--ink-0)]' : 'font-medium text-[var(--ink-1)]'"
                >{{ c.name }}</span>
                <span class="block truncate font-mono text-[9.5px] text-[var(--ink-3)]">{{ c.db_type }}</span>
              </span>
              <span class="h-1.5 w-1.5 rounded-full flex-shrink-0" :class="statusDot(c)" />
            </button>

            <!-- nested tables under the active connection -->
            <div v-if="selectedConn?.id === c.id" class="px-3 pb-2 pl-5">
              <div v-if="loadingCtx" class="space-y-1.5 pt-1">
                <UiSkeleton v-for="i in 5" :key="i" class="h-11 w-full rounded-lg" />
              </div>
              <div v-else-if="tables.length === 0" class="px-1 py-4">
                <UiEmptyState title="No profiled tables" description="Profile this connection first." :icon="Table2" />
              </div>
              <div v-else class="space-y-1.5 pt-1">
                <div
                  v-for="t in filteredTables"
                  :key="t.name"
                  @click="selectedTable = t.name"
                  class="flex cursor-pointer items-center gap-2.5 rounded-[9px] border px-3 py-2.5 transition-colors"
                  :class="selectedTable === t.name
                    ? 'border-[var(--ember)] bg-[var(--paper-0)] shadow-[0_0_0_3px_color-mix(in_oklch,var(--ember)_8%,transparent)]'
                    : 'border-[var(--line)] bg-[var(--paper-0)] hover:border-[var(--line-2)]'"
                >
                  <input
                    type="checkbox"
                    :checked="checkedTables.has(t.name)"
                    :disabled="generating"
                    @click.stop="toggleChecked(t.name)"
                    class="accent-[var(--ember)] flex-shrink-0"
                    title="select for doc generation"
                  />
                  <Table2 class="h-3.5 w-3.5 flex-shrink-0" :class="selectedTable === t.name ? 'text-[var(--ember)]' : 'text-[var(--ink-3)]'" />
                  <span class="min-w-0 flex-1">
                    <span class="block truncate font-mono text-[12.5px] font-semibold text-[var(--ink-0)]">{{ t.name }}</span>
                    <span class="block truncate font-mono text-[10px] text-[var(--ink-2)]">{{ Object.keys(t.columns).length }} cols · {{ t.rowCount ?? '?' }} rows</span>
                  </span>
                  <span v-if="tableDocumented(t)" class="h-1.5 w-1.5 rounded-full bg-emerald-500 flex-shrink-0" title="documented" />
                </div>
              </div>
            </div>
          </template>
        </div>
      </aside>

      <!-- Pane 3: table detail -->
      <section class="flex-1 overflow-y-auto min-w-0">
        <template v-if="selectedTableObj">
          <div class="px-7 pt-6 pb-12 max-w-[1180px]">
          <!-- What the AI sees -->
          <div class="rounded-[14px] border border-[var(--line)] bg-[var(--paper-1)] px-[18px] py-4" style="box-shadow: var(--shadow-1)">
            <div class="mb-3 flex items-center gap-2">
              <Eye class="h-3.5 w-3.5 text-[var(--ink-2)]" />
              <span class="eyebrow">What the AI sees for this connection</span>
            </div>
            <div class="mb-3.5 flex flex-wrap gap-x-8 gap-y-3.5">
              <div v-for="s in seeItems" :key="s.name" class="flex items-center gap-2.5">
                <span
                  class="grid h-5 w-5 flex-shrink-0 place-items-center rounded-full text-[12px] font-extrabold leading-none"
                  :class="s.ok ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400' : 'bg-amber-500/15 text-amber-600 dark:text-amber-500'"
                >
                  <Check v-if="s.ok" class="h-3 w-3" />
                  <span v-else>!</span>
                </span>
                <div>
                  <div class="text-[12.5px] font-semibold text-[var(--ink-0)]">{{ s.name }}</div>
                  <div class="mt-px font-mono text-[10px] text-[var(--ink-3)]">{{ s.note }}</div>
                </div>
              </div>
            </div>
            <p class="text-[12.5px] leading-relaxed text-[var(--ink-2)]">
              Mark a column <em class="italic">sensitive</em> below to withhold its values from the AI. Org-wide
              withholding is the <code class="rounded border border-[var(--line)] bg-[var(--paper-2)] px-1.5 py-px font-mono text-[11.5px] text-[var(--ink-1)]">metadata_only_llm</code> setting.
            </p>
          </div>

          <!-- Table identity -->
          <div class="mt-6 flex items-start gap-3">
            <div class="min-w-0 flex-1">
              <div class="font-mono text-2xl font-semibold text-[var(--ink-0)]">{{ selectedTable }}</div>
              <input
                v-model="tableDesc"
                @input="dirty = true"
                type="text"
                placeholder="Describe this table… (optional)"
                class="mt-2 w-full max-w-[720px] rounded-md border border-transparent bg-transparent px-1.5 py-1 text-[14.5px] leading-relaxed text-[var(--ink-1)] placeholder:text-[var(--ink-3)] hover:border-[var(--line)] focus:border-[var(--ember)] focus:outline-none focus:bg-[var(--paper-1)]"
              />
            </div>
          </div>

          <!-- Columns -->
          <div>
            <div class="mt-7 mb-1 flex items-center gap-3.5">
              <span class="eyebrow">Columns · {{ columnRows.length }}</span>
              <div class="h-px flex-1 border-t border-dashed border-[var(--line-2)]"></div>
              <template v-if="draftCount > 0">
                <span class="font-mono text-[11px] text-[var(--ink-2)]">{{ draftCount }} drafts pending review</span>
                <button
                  @click="acceptAllDrafts"
                  class="inline-flex items-center gap-1.5 rounded-lg bg-[var(--ember)] px-2.5 py-1 text-xs font-semibold text-white hover:opacity-90"
                ><CheckCheck class="h-3 w-3" />Accept all</button>
              </template>
            </div>

            <!-- Column header -->
            <div class="sticky top-0 z-[1] grid grid-cols-[190px_150px_minmax(220px,1fr)_76px] gap-5 border-b border-[var(--line-2)] bg-[var(--paper-0)] px-1 py-2.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--ink-2)]">
              <div>Column</div>
              <div>Role / Stats</div>
              <div>Meaning</div>
              <div class="text-center">Sensitive</div>
            </div>

            <!-- Column rows -->
            <div
              v-for="(col, i) in columnRows"
              :key="col.name"
              class="grid grid-cols-[190px_150px_minmax(220px,1fr)_76px] items-start gap-5 px-1 py-3.5"
              :class="i === columnRows.length - 1 ? '' : 'border-b border-[var(--line)]'"
            >
              <!-- identity -->
              <div class="min-w-0">
                <div class="break-words font-mono text-[13.5px] font-semibold text-[var(--ink-0)]">{{ col.name }}</div>
                <div v-if="col.displayName" class="mt-0.5 text-[11.5px] text-[var(--ink-2)]">&ldquo;{{ col.displayName }}&rdquo;</div>
              </div>

              <!-- role + type + stat -->
              <div>
                <span class="text-[11px] font-bold uppercase tracking-[0.06em]" :style="{ color: roleColor(col.role) }">{{ col.role }}</span>
                <div class="mt-1.5 font-mono text-[10.5px] tracking-[0.02em] text-[var(--ink-2)]">{{ col.type }}</div>
                <div v-if="col.stats" class="mt-0.5 font-mono text-[10.5px] text-[var(--ink-3)]">{{ col.stats }}</div>
              </div>

              <!-- meaning + provenance footer -->
              <div class="min-w-0">
                <input
                  v-model="col.description"
                  @input="markEdited(col)"
                  type="text"
                  :placeholder="col.dbComment || 'Add meaning…'"
                  class="w-full rounded-md border border-transparent bg-transparent px-1.5 py-1 text-[13.5px] leading-relaxed placeholder:text-[var(--ink-3)] hover:border-[var(--line)] focus:border-[var(--ember)] focus:outline-none focus:bg-[var(--paper-1)]"
                  :class="col.status === 'confirmed' || col.source === 'human' ? 'text-[var(--ink-0)]' : 'text-[var(--ink-1)]'"
                />
                <div class="mt-1.5 flex items-center gap-3 px-1.5">
                  <input
                    v-model="col.displayName"
                    @input="markEdited(col)"
                    type="text"
                    placeholder="display name"
                    class="w-28 rounded border border-transparent bg-transparent py-0.5 text-[11px] text-[var(--ink-1)] placeholder:text-[var(--ink-3)] hover:border-[var(--line)] focus:border-[var(--ember)] focus:outline-none focus:px-1"
                  />
                  <span v-if="col.source === 'human' || col.status === 'confirmed'" class="inline-flex items-center gap-1.5 text-[11.5px] text-[var(--ink-2)]">
                    <Check class="h-3 w-3 text-emerald-600 dark:text-emerald-400" /> Confirmed
                  </span>
                  <template v-else-if="col.source === 'llm'">
                    <span class="inline-flex items-center gap-1.5 text-[11.5px] text-[var(--ink-2)]">
                      <span class="h-1.5 w-1.5 rounded-full bg-[var(--ember)]" /> AI draft
                    </span>
                    <button @click="confirmDraft(col)" class="inline-flex items-center gap-1 text-xs font-semibold text-[var(--ember)] hover:underline">
                      <Check class="h-3 w-3" /> Confirm
                    </button>
                  </template>
                  <span v-else-if="col.dbComment" class="text-[11px] italic text-[var(--ink-3)]">from database comment</span>
                </div>
              </div>

              <!-- sensitive -->
              <div class="grid place-items-center pt-1">
                <input type="checkbox" v-model="col.sensitive" @change="markEdited(col)" class="h-[18px] w-[18px] rounded accent-[var(--ember)]" title="withhold this column's values from the AI" />
              </div>
            </div>

            <!-- Relationships -->
            <div class="mt-8">
              <div class="mb-3 flex items-center gap-3.5">
                <span class="eyebrow">Relationships · {{ activeRelationships.length }}</span>
                <div class="h-px flex-1 border-t border-dashed border-[var(--line-2)]"></div>
              </div>

              <ul v-if="activeRelationships.length" class="space-y-1.5">
                <li
                  v-for="r in activeRelationships"
                  :key="'rel-' + r.from + '→' + r.to"
                  class="group flex items-center gap-2.5 rounded-md px-1.5 py-1 text-sm text-[var(--ink-1)] hover:bg-[var(--paper-1)]"
                >
                  <span class="font-mono text-xs text-[var(--ink-0)]">{{ r.from }}</span>
                  <ArrowRight class="h-3.5 w-3.5 flex-shrink-0 text-[var(--ink-3)]" />
                  <span class="font-mono text-xs text-[var(--ink-0)]">{{ r.to }}</span>
                  <span v-if="r.guessed" class="rounded-full border border-[var(--line)] bg-[var(--paper-2)] px-2 py-0.5 text-[11px] text-[var(--ink-2)]">guessed</span>
                  <span v-else-if="r.manual" class="rounded-full border border-[var(--ember)] bg-[var(--ember-wash)] px-2 py-0.5 text-[11px] text-[var(--ember)]">manual</span>
                  <span v-else-if="r.confirmed" class="inline-flex items-center gap-1 text-[11px] text-[var(--ink-2)]"><Check class="h-3 w-3 text-emerald-600 dark:text-emerald-400" />confirmed</span>
                  <div class="ml-auto flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      v-if="r.guessed"
                      @click="confirmRel(r)"
                      title="confirm this relationship"
                      class="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-semibold text-[var(--ember)] hover:bg-[var(--ember-wash)]"
                    ><Check class="h-3 w-3" />Confirm</button>
                    <button
                      @click="rejectRel(r)"
                      title="reject this relationship"
                      class="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-[var(--ink-2)] hover:bg-red-500/10 hover:text-red-600"
                    ><X class="h-3 w-3" />Reject</button>
                  </div>
                </li>
              </ul>
              <p v-else class="text-xs text-[var(--ink-3)]">No relationships detected — add one below.</p>

              <!-- rejected -->
              <div v-if="rejectedRelationships.length" class="mt-3">
                <p class="mb-1.5 text-[11px] uppercase tracking-[0.08em] text-[var(--ink-3)]">Rejected · {{ rejectedRelationships.length }}</p>
                <ul class="space-y-1">
                  <li
                    v-for="r in rejectedRelationships"
                    :key="'rej-' + r.from + '→' + r.to"
                    class="flex items-center gap-2.5 px-1.5 py-1 text-sm text-[var(--ink-3)]"
                  >
                    <span class="font-mono text-xs line-through">{{ r.from }}</span>
                    <ArrowRight class="h-3.5 w-3.5 flex-shrink-0" />
                    <span class="font-mono text-xs line-through">{{ r.to }}</span>
                    <button
                      @click="restoreRel(r)"
                      class="ml-auto inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-[var(--ink-2)] hover:bg-[var(--ember-wash)] hover:text-[var(--ember)]"
                    ><RotateCcw class="h-3 w-3" />Restore</button>
                  </li>
                </ul>
              </div>

              <!-- add manual -->
              <div class="mt-3 flex items-center gap-2">
                <input
                  v-model="relFrom"
                  @keydown.enter="addRel"
                  placeholder="orders.user_id"
                  class="w-40 rounded-md border border-[var(--line)] bg-[var(--paper-1)] px-2 py-1 font-mono text-xs text-[var(--ink-0)] placeholder:text-[var(--ink-3)] focus:border-[var(--ember)] focus:outline-none"
                />
                <ArrowRight class="h-3.5 w-3.5 flex-shrink-0 text-[var(--ink-3)]" />
                <input
                  v-model="relTo"
                  @keydown.enter="addRel"
                  placeholder="users.id"
                  class="w-40 rounded-md border border-[var(--line)] bg-[var(--paper-1)] px-2 py-1 font-mono text-xs text-[var(--ink-0)] placeholder:text-[var(--ink-3)] focus:border-[var(--ember)] focus:outline-none"
                />
                <button
                  @click="addRel"
                  :disabled="!relFrom.trim() || !relTo.trim()"
                  class="inline-flex items-center gap-1 rounded-md border border-[var(--line-2)] px-2.5 py-1 text-xs font-medium text-[var(--ink-1)] hover:border-[var(--ember)] hover:text-[var(--ember)] disabled:opacity-40"
                ><Plus class="h-3 w-3" />Add</button>
              </div>
            </div>
          </div>
          </div>
        </template>
        <div v-else class="flex h-full items-center justify-center p-8">
          <UiEmptyState
            :title="selectedConn ? 'Select a table' : 'Explore your data'"
            :description="selectedConn ? 'Pick a table to review and document its columns.' : 'Select a connection to see what your AI understands about it.'"
            :icon="selectedConn ? Table2 : DatabaseZap"
          />
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  Sparkles, Save, Search, Database, Table2, DatabaseZap,
  Eye, Check, CheckCheck, CheckSquare, ArrowRight, Loader2,
  X, RotateCcw, Plus,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'

definePageMeta({ middleware: 'auth' })

const api = useApi()
const connectorIcons = useConnectorIcons()

const connections = ref<any[]>([])
const loadingConns = ref(true)
const selectedConn = ref<any>(null)

const context = ref<any>(null)      // data_context (roles/stats/db-comment descriptions)
const semantics = ref<any>({ glossary: {}, relationships: [], definitions: [] })
const loadingCtx = ref(false)

const selectedTable = ref<string | null>(null)
const tableSearch = ref('')
const onlyUndocumented = ref(false)
const tableDesc = ref('')

const dirty = ref(false)
const saving = ref(false)

// LLM doc generation
const checkedTables = ref<Set<string>>(new Set())
const generating = ref(false)
const genProgress = ref('')
const confirmingGen = ref(false)
const genTargetTables = ref<string[]>([])
let genPollTimer: any = null

// editable per-column glossary state, keyed "table.column"
const edits = ref<Record<string, any>>({})

onMounted(async () => {
  try {
    const data: any = await api.connections.list()
    connections.value = Array.isArray(data) ? data : (data?.connections ?? [])
  } finally {
    loadingConns.value = false
  }
})

async function selectConnection(c: any) {
  selectedConn.value = c
  selectedTable.value = null
  context.value = null
  edits.value = {}
  dirty.value = false
  checkedTables.value = new Set()
  stopGenPoll()
  generating.value = false
  confirmingGen.value = false
  loadingCtx.value = true
  try {
    const [ctx, sem]: any = await Promise.all([
      api.connections.getContext(c.id).catch(() => null),
      api.connections.getSemantics(c.id).catch(() => ({ glossary: {}, relationships: [], definitions: [] })),
    ])
    context.value = ctx
    semantics.value = sem || { glossary: {}, relationships: [], definitions: [] }
    // seed editable state from saved glossary + relationship overlay
    edits.value = JSON.parse(JSON.stringify(sem?.glossary || {}))
    relOverlay.value = JSON.parse(JSON.stringify(sem?.relationships || []))
    relFrom.value = ''
    relTo.value = ''
    const tnames = Object.keys(ctx?.tables || {})
    if (tnames.length) selectedTable.value = tnames[0]
  } finally {
    loadingCtx.value = false
  }
}

const tables = computed(() => {
  const t = context.value?.tables || {}
  return Object.entries(t).map(([name, data]: [string, any]) => ({
    name,
    rowCount: data.rowCount,
    columns: data.columns || {},
    description: data.description,
  }))
})

const filteredTables = computed(() => {
  const q = tableSearch.value.trim().toLowerCase()
  return tables.value.filter((t) => {
    if (q && !t.name.toLowerCase().includes(q)) return false
    if (onlyUndocumented.value && tableDocumented(t)) return false
    return true
  })
})

const documentedCount = computed(() => tables.value.filter(tableDocumented).length)

function tableDocumented(t: any): boolean {
  for (const cname of Object.keys(t.columns)) {
    const e = edits.value[`${t.name}.${cname}`]
    if (e && (e.description || e.display_name)) return true
  }
  return false
}

const selectedTableObj = computed(() => tables.value.find((t) => t.name === selectedTable.value) || null)

// Built once per table selection (NOT a computed off `edits`, so typing into a
// row input doesn't rebuild the list and steal focus). Each row holds live
// v-model state; markEdited syncs it back into `edits`.
const columnRows = ref<any[]>([])

watch(selectedTable, (name) => {
  if (!name) {
    columnRows.value = []
    return
  }
  const entry = edits.value[name]
  tableDesc.value = entry?.description || selectedTableObj.value?.description || ''
  refreshColumnRows()
}, { immediate: true })

// --- relationship curation ---------------------------------------------------
// Editable overlay of curation entries {from,to,status,inferred?}. The backend
// merge (semantic_layer.merge_semantics_into_context) applies it: status
// 'rejected' drops an auto-detected pair, any non-rejected new pair is added.
// Seeded per-connection from saved semantics; saved alongside the glossary.
const relOverlay = ref<any[]>([])
const relFrom = ref('')
const relTo = ref('')

const relKey = (r: any) => `${r.from}→${r.to}`

const activeRelationships = computed(() => {
  const overlay = new Map(relOverlay.value.map((r) => [relKey(r), r]))
  const baseRels = context.value?.relationships || []
  const base = baseRels.filter((r: any) => overlay.get(relKey(r))?.status !== 'rejected')
  const seen = new Set(base.map(relKey))
  const basePairs = new Set(baseRels.map(relKey))
  const manual = relOverlay.value.filter((r: any) => r.status !== 'rejected' && !seen.has(relKey(r)))
  return [...base, ...manual].map((r: any) => {
    const confirmed = overlay.get(relKey(r))?.status === 'confirmed'
    return {
      from: r.from,
      to: r.to,
      inferred: !!r.inferred,
      guessed: !!r.inferred && !confirmed,
      confirmed,
      manual: !r.inferred && !basePairs.has(relKey(r)),
    }
  })
})

const rejectedRelationships = computed(() =>
  relOverlay.value.filter((r: any) => r.status === 'rejected')
)

function setRelOverlay(from: string, to: string, patch: any) {
  const key = `${from}→${to}`
  const i = relOverlay.value.findIndex((r) => `${r.from}→${r.to}` === key)
  const inferred = i >= 0 ? relOverlay.value[i].inferred : patch.inferred
  const entry = { from, to, ...(inferred ? { inferred: true } : {}), ...patch }
  if (i >= 0) relOverlay.value.splice(i, 1, entry)
  else relOverlay.value.push(entry)
  dirty.value = true
}

function confirmRel(r: any) { setRelOverlay(r.from, r.to, { status: 'confirmed', inferred: r.inferred }) }
function rejectRel(r: any) { setRelOverlay(r.from, r.to, { status: 'rejected', inferred: r.inferred }) }
function restoreRel(r: any) {
  const key = relKey(r)
  relOverlay.value = relOverlay.value.filter((x) => relKey(x) !== key)
  dirty.value = true
}
function addRel() {
  const from = relFrom.value.trim()
  const to = relTo.value.trim()
  if (!from || !to) return
  const key = `${from}→${to}`
  const dup =
    relOverlay.value.some((r) => `${r.from}→${r.to}` === key) ||
    (context.value?.relationships || []).some((r: any) => `${r.from}→${r.to}` === key)
  if (!dup) relOverlay.value.push({ from, to, status: 'confirmed' })
  relFrom.value = ''
  relTo.value = ''
  dirty.value = true
}

function buildStats(c: any): string {
  const parts: string[] = []
  if (c.cardinality != null) parts.push(`${c.cardinality} distinct`)
  if (c.min != null && c.max != null) parts.push(`${c.min}–${c.max}`)
  if (c.topValues?.length) parts.push(`e.g. ${c.topValues.slice(0, 2).join(', ')}`)
  return parts.join(' · ')
}

function markEdited(col: any) {
  const key = col._key
  const prev = edits.value[key] || {}
  edits.value[key] = {
    ...prev,
    description: col.description || undefined,
    display_name: col.displayName || undefined,
    sensitive: col.sensitive || undefined,
    // any user edit becomes human/confirmed and wins precedence
    source: 'human',
    status: 'confirmed',
  }
  col.source = 'human'
  col.status = 'confirmed'
  dirty.value = true
}

function confirmDraft(col: any) {
  const key = col._key
  edits.value[key] = { ...(edits.value[key] || {}), status: 'confirmed' }
  col.status = 'confirmed'
  dirty.value = true
}

async function saveSemantics() {
  if (!selectedConn.value) return
  saving.value = true
  try {
    // fold table-level description into glossary under the bare table key
    const glossary = JSON.parse(JSON.stringify(edits.value))
    if (selectedTable.value) {
      const tkey = selectedTable.value
      if (tableDesc.value) {
        glossary[tkey] = { ...(glossary[tkey] || {}), description: tableDesc.value, source: 'human', status: 'confirmed' }
      }
    }
    const relationships = JSON.parse(JSON.stringify(relOverlay.value))
    await api.connections.putSemantics(selectedConn.value.id, { glossary, relationships })
    semantics.value.glossary = glossary
    semantics.value.relationships = relationships
    dirty.value = false
    toast.success('Documentation saved')
  } catch (e) {
    toast.error('Could not save documentation')
  } finally {
    saving.value = false
  }
}

// --- LLM doc generation ---
const genButtonCount = computed(() => (checkedTables.value.size ? ` (${checkedTables.value.size})` : ''))

const draftCount = computed(() =>
  columnRows.value.filter((c) => c.source === 'llm' && c.status === 'draft').length
)

function toggleChecked(name: string) {
  const s = new Set(checkedTables.value)
  s.has(name) ? s.delete(name) : s.add(name)
  checkedTables.value = s
}

function startGeneration() {
  const targets = checkedTables.value.size
    ? [...checkedTables.value]
    : selectedTable.value ? [selectedTable.value] : []
  if (!targets.length) return
  genTargetTables.value = targets
  confirmingGen.value = true
}

async function confirmGeneration() {
  confirmingGen.value = false
  if (!selectedConn.value || !genTargetTables.value.length) return
  generating.value = true
  genProgress.value = `0/${genTargetTables.value.length}`
  try {
    await api.connections.generateDescriptions(selectedConn.value.id, genTargetTables.value)
    toast.info(`Drafting docs for ${genTargetTables.value.length} table${genTargetTables.value.length === 1 ? '' : 's'}…`)
    pollGeneration()
  } catch (e) {
    generating.value = false
    toast.error('Could not start generation')
  }
}

function pollGeneration() {
  stopGenPoll()
  genPollTimer = setInterval(async () => {
    if (!selectedConn.value) return stopGenPoll()
    let st: any
    try {
      st = await api.connections.getGenerationStatus(selectedConn.value.id)
    } catch {
      return
    }
    if (st?.progress) genProgress.value = st.progress
    if (st?.status === 'done' || st?.status === 'failed' || st?.status === 'idle') {
      stopGenPoll()
      generating.value = false
      if (st?.status === 'done') {
        await reloadDrafts()
        toast.success('Draft docs ready — review and confirm below')
      } else if (st?.status === 'failed') {
        toast.error(st?.error ? `Generation failed: ${st.error}` : 'Generation failed')
      }
    }
  }, 2000)
}

function stopGenPoll() {
  if (genPollTimer) { clearInterval(genPollTimer); genPollTimer = null }
}

onBeforeUnmount(stopGenPoll)

async function reloadDrafts() {
  if (!selectedConn.value) return
  const sem: any = await api.connections.getSemantics(selectedConn.value.id).catch(() => null)
  const newGloss = sem?.glossary || {}
  // Merge server drafts in, but never clobber a key the user is actively editing.
  for (const [key, entry] of Object.entries(newGloss)) {
    const local = edits.value[key]
    if (local && (local.source === 'human' || local.status === 'confirmed')) continue
    edits.value[key] = entry
  }
  semantics.value = sem || semantics.value
  refreshColumnRows()
  checkedTables.value = new Set()
}

// Rebuild the visible column rows from `edits` (used after generation lands).
function refreshColumnRows() {
  const t = selectedTableObj.value
  if (!t) return
  columnRows.value = Object.entries(t.columns).map(([cname, cdata]: [string, any]) => {
    const key = `${t.name}.${cname}`
    const e = edits.value[key] || {}
    return {
      name: cname,
      type: cdata.type,
      role: cdata.role || 'attribute',
      stats: buildStats(cdata),
      dbComment: cdata.description,
      description: e.description ?? '',
      displayName: e.display_name ?? '',
      sensitive: !!e.sensitive,
      source: e.source,
      status: e.status,
      _key: key,
    }
  })
}

function acceptAllDrafts() {
  for (const col of columnRows.value) {
    if (col.source === 'llm' && col.status === 'draft') {
      confirmDraft(col)
    }
  }
}

// --- presentation helpers ---
function statusDot(c: any): string {
  const s = c.profiling_status
  if (s === 'ready') return 'bg-emerald-500'
  if (s === 'in_progress' || s === 'pending') return 'bg-amber-500'
  if (s === 'failed') return 'bg-red-500'
  return 'bg-[var(--ink-2)]'
}

// role → data-palette colour, rendered as plain coloured uppercase text (design)
const ROLE_COLOR: Record<string, string> = {
  key: 'var(--brand-indigo)',
  measure: 'var(--ember)',
  dimension: 'var(--brand-peri)',
  attribute: 'var(--d-slate)',
}
function roleColor(role: string): string {
  return ROLE_COLOR[role] || 'var(--d-slate)'
}

// "What the AI sees" rows — static per connection (privacy posture)
const seeItems = [
  { ok: true, name: 'Schema', note: 'column names & types' },
  { ok: true, name: 'Derived stats', note: 'distinct · null · ranges' },
  { ok: false, name: 'Top values', note: 'real data' },
  { ok: false, name: 'Sample rows', note: 'real data' },
]
</script>
