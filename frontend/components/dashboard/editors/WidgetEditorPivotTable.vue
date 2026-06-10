<template>
  <div class="h-full overflow-y-auto p-5 space-y-5">

    <!-- Title -->
    <div class="space-y-1.5">
      <label class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Title</label>
      <input
        v-model="localTitle"
        type="text"
        placeholder="e.g. Revenue by Region and Quarter"
        class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
        :readonly="!editMode"
        :class="!editMode ? 'cursor-default bg-gray-50' : ''"
        @input="emitConfig()"
      />
    </div>

    <div v-if="sourceColumns && sourceColumns.length > 0" class="space-y-5">

      <!-- Row dimensions -->
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Row Dimensions</h3>
          <button v-if="editMode" type="button" class="text-[11px] font-medium text-indigo-600 hover:text-indigo-700"
            @click="addDim('row')">+ Add</button>
        </div>
        <p v-if="!localRowDims.length" class="text-xs text-gray-400">Add a dimension to break down the rows.</p>
        <div v-for="(d, i) in localRowDims" :key="'r'+i" class="rounded-lg border border-gray-200 p-2 space-y-1.5">
          <div class="flex gap-2">
            <select :value="d.column" :disabled="!editMode"
              class="flex-1 rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:bg-gray-50"
              @change="setDimColumn('row', i, ($event.target as HTMLSelectElement).value)">
              <option value="" disabled>Column…</option>
              <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
            </select>
            <button v-if="editMode" type="button" class="px-2 text-gray-400 hover:text-rose-500" @click="removeDim('row', i)">✕</button>
          </div>
          <input :value="d.label || ''" type="text" placeholder="Label (optional)" :readonly="!editMode"
            class="w-full rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm disabled:bg-gray-50"
            @input="setDimLabel('row', i, ($event.target as HTMLInputElement).value)" />
        </div>
        <div v-if="localRowDims.length" class="space-y-2 pt-1">
          <div class="flex items-center justify-between py-0.5">
            <span class="text-xs text-gray-700">Expand-collapse hierarchy</span>
            <button type="button" role="switch" :aria-checked="localExpand" :disabled="!editMode"
              class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors disabled:opacity-40"
              :class="localExpand ? 'bg-indigo-600' : 'bg-gray-200'"
              @click="editMode && (localExpand = !localExpand, emitConfig())">
              <span class="inline-block h-4 w-4 rounded-full bg-white shadow transition mt-0.5"
                :class="localExpand ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
            </button>
          </div>
          <div v-if="localExpand && localRowDims.length > 1" class="flex items-center justify-between">
            <span class="text-xs text-gray-700">Default expand level</span>
            <select v-model.number="localExpandLevel" :disabled="!editMode"
              class="w-28 rounded-lg border border-gray-200 bg-white px-2 py-1 text-sm disabled:bg-gray-50"
              @change="emitConfig()">
              <option v-for="(d, i) in localRowDims" :key="i" :value="i">{{ d.column || ('Level ' + (i+1)) }}</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Column dimensions -->
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Column Dimensions</h3>
          <button v-if="editMode && localColDims.length < 2" type="button" class="text-[11px] font-medium text-indigo-600 hover:text-indigo-700"
            @click="addDim('col')">+ Add</button>
        </div>
        <p v-if="!localColDims.length" class="text-xs text-gray-400">Optional. Each distinct value becomes a column group (max 2).</p>
        <div v-for="(d, i) in localColDims" :key="'c'+i" class="rounded-lg border border-gray-200 p-2 space-y-1.5">
          <div class="flex gap-2">
            <select :value="d.column" :disabled="!editMode"
              class="flex-1 rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:bg-gray-50"
              @change="setDimColumn('col', i, ($event.target as HTMLSelectElement).value)">
              <option value="" disabled>Column…</option>
              <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
            </select>
            <button v-if="editMode" type="button" class="px-2 text-gray-400 hover:text-rose-500" @click="removeDim('col', i)">✕</button>
          </div>
          <input :value="d.label || ''" type="text" placeholder="Label (optional)" :readonly="!editMode"
            class="w-full rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm disabled:bg-gray-50"
            @input="setDimLabel('col', i, ($event.target as HTMLInputElement).value)" />
        </div>
      </div>

      <!-- Values / metrics -->
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Metrics</h3>
          <button v-if="editMode" type="button" class="text-[11px] font-medium text-indigo-600 hover:text-indigo-700"
            @click="addValue()">+ Add</button>
        </div>
        <p v-if="!localValues.length" class="text-xs text-gray-400">Add at least one metric to show in the cells.</p>
        <div v-for="(v, i) in localValues" :key="'v'+i" class="rounded-lg border border-gray-200 p-2.5 space-y-2">
          <div class="flex gap-2">
            <select :value="v.column" :disabled="!editMode"
              class="flex-1 rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:bg-gray-50"
              @change="setValueField(i, 'column', ($event.target as HTMLSelectElement).value)">
              <option value="" disabled>Column…</option>
              <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
            </select>
            <button v-if="editMode" type="button" class="px-2 text-gray-400 hover:text-rose-500" @click="removeValue(i)">✕</button>
          </div>
          <div class="flex gap-2">
            <select :value="v.aggregation || 'sum'" :disabled="!editMode"
              class="w-32 rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm disabled:bg-gray-50"
              @change="setValueField(i, 'aggregation', ($event.target as HTMLSelectElement).value)">
              <option v-for="a in aggregationOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
            </select>
            <select :value="v.format || 'number'" :disabled="!editMode"
              class="w-28 rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm disabled:bg-gray-50"
              @change="setValueField(i, 'format', ($event.target as HTMLSelectElement).value)">
              <option v-for="f in formatOptions" :key="f.value" :value="f.value">{{ f.label }}</option>
            </select>
          </div>
          <input :value="v.label || ''" type="text" placeholder="Label (optional)" :readonly="!editMode"
            class="w-full rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm disabled:bg-gray-50"
            @input="setValueField(i, 'label', ($event.target as HTMLInputElement).value)" />
        </div>
      </div>

      <!-- Totals -->
      <div class="space-y-2">
        <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Totals</h3>
        <div class="flex items-center justify-between py-0.5">
          <span class="text-xs text-gray-700">Row totals (grand-total column)</span>
          <button type="button" role="switch" :aria-checked="localShowRowTotals" :disabled="!editMode"
            class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors disabled:opacity-40"
            :class="localShowRowTotals ? 'bg-indigo-600' : 'bg-gray-200'"
            @click="editMode && (localShowRowTotals = !localShowRowTotals, emitConfig())">
            <span class="inline-block h-4 w-4 rounded-full bg-white shadow transition mt-0.5"
              :class="localShowRowTotals ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
          </button>
        </div>
        <div class="flex items-center justify-between py-0.5">
          <span class="text-xs text-gray-700">Column totals (grand-total row)</span>
          <button type="button" role="switch" :aria-checked="localShowColTotals" :disabled="!editMode"
            class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors disabled:opacity-40"
            :class="localShowColTotals ? 'bg-indigo-600' : 'bg-gray-200'"
            @click="editMode && (localShowColTotals = !localShowColTotals, emitConfig())">
            <span class="inline-block h-4 w-4 rounded-full bg-white shadow transition mt-0.5"
              :class="localShowColTotals ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
          </button>
        </div>
      </div>

      <!-- Sort & limits -->
      <div class="space-y-2">
        <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Sort &amp; Limits</h3>
        <div class="flex items-center justify-between">
          <span class="text-xs text-gray-700">Sort rows by</span>
          <select v-model="localSortBy" :disabled="!editMode"
            class="w-36 rounded-lg border border-gray-200 bg-white px-2 py-1 text-sm disabled:bg-gray-50"
            @change="emitConfig()">
            <option value="">First row dimension</option>
            <option v-for="(v, i) in localValues" :key="i" :value="v.column">{{ v.label || v.column }}</option>
          </select>
        </div>
        <div v-if="localSortBy" class="flex items-center justify-between">
          <span class="text-xs text-gray-700">Direction</span>
          <select v-model="localSortDir" :disabled="!editMode"
            class="w-28 rounded-lg border border-gray-200 bg-white px-2 py-1 text-sm disabled:bg-gray-50"
            @change="emitConfig()">
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select>
        </div>
        <div class="flex items-center justify-between">
          <span class="text-xs text-gray-700">Number of rows</span>
          <input v-model.number="localRowLimit" type="number" min="1" placeholder="All" :disabled="!editMode"
            class="w-20 rounded-lg border border-gray-200 bg-white px-2 py-1 text-sm text-center disabled:bg-gray-50"
            @input="emitConfig()" />
        </div>
        <div class="flex items-center justify-between">
          <span class="text-xs text-gray-700">Number of columns</span>
          <input v-model.number="localColLimit" type="number" min="1" placeholder="All" :disabled="!editMode"
            class="w-20 rounded-lg border border-gray-200 bg-white px-2 py-1 text-sm text-center disabled:bg-gray-50"
            @input="emitConfig()" />
        </div>
      </div>
    </div>

    <p v-else class="text-xs text-gray-400">Connect a data source (Data Source tab) to configure the pivot.</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { WidgetConfig, PivotTableWidgetConfig, PivotDimension, PivotValue, WidgetDataSource } from '~/types/dashboard'

const props = defineProps<{
  modelValue: WidgetConfig
  editMode: boolean
  dataSource?: WidgetDataSource
  sourceColumns?: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WidgetConfig]
  'update:mapping': [patch: Record<string, any>]
}>()

const pivotConfig = computed(() => props.modelValue.config as PivotTableWidgetConfig)

const localTitle = ref(pivotConfig.value.title ?? '')
const localRowDims = ref<PivotDimension[]>(JSON.parse(JSON.stringify(pivotConfig.value.rowDimensions ?? [])))
const localColDims = ref<PivotDimension[]>(JSON.parse(JSON.stringify(pivotConfig.value.columnDimensions ?? [])))
const localValues = ref<PivotValue[]>(JSON.parse(JSON.stringify(pivotConfig.value.values ?? [])))
const localExpand = ref(pivotConfig.value.expandCollapse !== false)
const localExpandLevel = ref(pivotConfig.value.defaultExpandLevel ?? 0)
const localShowRowTotals = ref(pivotConfig.value.showRowTotals !== false)
const localShowColTotals = ref(pivotConfig.value.showColumnTotals !== false)
const localRowLimit = ref<number | undefined>(pivotConfig.value.rowLimit)
const localColLimit = ref<number | undefined>(pivotConfig.value.columnLimit)
const localSortBy = ref(pivotConfig.value.sortBy ?? '')
const localSortDir = ref<'asc' | 'desc'>(pivotConfig.value.sortDir ?? 'desc')

const aggregationOptions = [
  { value: 'sum', label: 'Sum' },
  { value: 'average', label: 'Average' },
  { value: 'count', label: 'Count' },
  { value: 'countDistinct', label: 'Count Distinct' },
  { value: 'min', label: 'Min' },
  { value: 'max', label: 'Max' },
  { value: 'median', label: 'Median' },
  { value: 'stdDev', label: 'Std Dev' },
  { value: 'variance', label: 'Variance' },
]
const formatOptions = [
  { value: 'number', label: 'Number' },
  { value: 'currency', label: 'Currency' },
  { value: 'percent', label: 'Percent' },
  { value: 'text', label: 'Text' },
  { value: 'date', label: 'Date' },
]

let debounce: ReturnType<typeof setTimeout> | null = null
function emitConfig() {
  if (debounce) clearTimeout(debounce)
  debounce = setTimeout(() => {
    emit('update:modelValue', {
      type: 'pivot_table',
      config: {
        ...pivotConfig.value,
        title: localTitle.value || undefined,
        rowDimensions: localRowDims.value,
        columnDimensions: localColDims.value,
        values: localValues.value,
        expandCollapse: localExpand.value,
        defaultExpandLevel: localExpandLevel.value || undefined,
        showRowTotals: localShowRowTotals.value,
        showColumnTotals: localShowColTotals.value,
        rowLimit: localRowLimit.value || undefined,
        columnLimit: localColLimit.value || undefined,
        sortBy: localSortBy.value || undefined,
        sortDir: localSortDir.value,
      } as PivotTableWidgetConfig,
    })
  }, 120)
}

// Mapping = union of every referenced column → feeds the passthrough transform.
function emitMapping() {
  const seen = new Set<string>()
  const columnConfig: { column: string; label?: string }[] = []
  for (const d of [...localRowDims.value, ...localColDims.value]) {
    if (d.column && !seen.has(d.column)) { seen.add(d.column); columnConfig.push({ column: d.column, label: d.label }) }
  }
  for (const v of localValues.value) {
    if (v.column && !seen.has(v.column)) { seen.add(v.column); columnConfig.push({ column: v.column, label: v.label }) }
  }
  emit('update:mapping', { columnConfig })
}

function emitBoth() { emitConfig(); emitMapping() }

function addDim(kind: 'row' | 'col') {
  const arr = kind === 'row' ? localRowDims : localColDims
  if (kind === 'col' && arr.value.length >= 2) return
  arr.value.push({ column: '' })
  emitConfig()
}
function setDimColumn(kind: 'row' | 'col', i: number, column: string) {
  const arr = kind === 'row' ? localRowDims : localColDims
  arr.value[i] = { ...arr.value[i], column }
  emitBoth()
}
function setDimLabel(kind: 'row' | 'col', i: number, label: string) {
  const arr = kind === 'row' ? localRowDims : localColDims
  arr.value[i] = { ...arr.value[i], label }
  emitConfig()
}
function removeDim(kind: 'row' | 'col', i: number) {
  const arr = kind === 'row' ? localRowDims : localColDims
  arr.value.splice(i, 1)
  emitBoth()
}

function addValue() {
  localValues.value.push({ column: '', aggregation: 'sum', format: 'number' })
  emitConfig()
}
function setValueField(i: number, field: keyof PivotValue, value: any) {
  localValues.value[i] = { ...localValues.value[i], [field]: value }
  if (field === 'column') emitBoth()
  else emitConfig()
}
function removeValue(i: number) {
  localValues.value.splice(i, 1)
  emitBoth()
}
</script>
