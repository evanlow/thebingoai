<template>
  <div class="h-full overflow-y-auto p-5 space-y-5">

    <!-- Title -->
    <div class="space-y-1.5">
      <label class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Title</label>
      <input
        v-model="localTitle"
        type="text"
        placeholder="e.g. Revenue by Region and Quarter"
        class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
        :readonly="!editMode"
        :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''"
        @input="emitConfig()"
      />
    </div>

    <div v-if="sourceColumns && sourceColumns.length > 0" class="space-y-5">

      <!-- Row dimensions -->
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Row Dimensions</h3>
          <button v-if="editMode" type="button" class="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300"
            @click="addDim('row')">+ Add</button>
        </div>
        <p v-if="!localRowDims.length" class="text-sm text-gray-400 dark:text-neutral-500">Add a dimension to break down the rows.</p>
        <PivotDimCard
          v-for="(d, i) in localRowDims"
          :key="'r'+i"
          :model-value="d"
          :edit-mode="editMode"
          :available-columns="sourceColumns"
          @update:model-value="updateDim('row', i, $event)"
          @remove="removeDim('row', i)"
        />
        <div v-if="localRowDims.length" class="space-y-2 pt-1">
          <div class="flex items-center justify-between py-0.5">
            <span class="text-sm text-gray-700 dark:text-neutral-200">Expand-collapse hierarchy</span>
            <button type="button" role="switch" :aria-checked="localExpand" :disabled="!editMode"
              class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors disabled:opacity-40"
              :class="localExpand ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
              @click="editMode && (localExpand = !localExpand, emitConfig())">
              <span class="inline-block h-4 w-4 rounded-full bg-white shadow transition mt-0.5"
                :class="localExpand ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
            </button>
          </div>
          <div v-if="localExpand && localRowDims.length > 1" class="flex items-center justify-between">
            <span class="text-sm text-gray-700 dark:text-neutral-200">Default expand level</span>
            <select v-model.number="localExpandLevel" :disabled="!editMode"
              class="w-28 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @change="emitConfig()">
              <option v-for="(d, i) in localRowDims" :key="i" :value="i">{{ d.column || ('Level ' + (i+1)) }}</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Column dimensions -->
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Column Dimensions</h3>
          <button v-if="editMode && localColDims.length < 2" type="button" class="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300"
            @click="addDim('col')">+ Add</button>
        </div>
        <p v-if="!localColDims.length" class="text-sm text-gray-400 dark:text-neutral-500">Optional. Each distinct value becomes a column group (max 2).</p>
        <PivotDimCard
          v-for="(d, i) in localColDims"
          :key="'c'+i"
          :model-value="d"
          :edit-mode="editMode"
          :available-columns="sourceColumns"
          @update:model-value="updateDim('col', i, $event)"
          @remove="removeDim('col', i)"
        />
      </div>

      <!-- Values / metrics -->
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Metrics</h3>
          <button v-if="editMode" type="button" class="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300"
            @click="addValue()">+ Add</button>
        </div>
        <p v-if="!localValues.length" class="text-sm text-gray-400 dark:text-neutral-500">Add at least one metric to show in the cells.</p>
        <PivotFieldCard
          v-for="(v, i) in localValues"
          :key="'v'+i"
          :model-value="v"
          :edit-mode="editMode"
          :available-columns="sourceColumns"
          @update:model-value="updateValue(i, $event)"
          @remove="removeValue(i)"
        />
      </div>

      <!-- Totals -->
      <div class="space-y-2">
        <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Totals</h3>
        <div class="flex items-center justify-between py-0.5">
          <span class="text-sm text-gray-700 dark:text-neutral-200">Row totals (grand-total column)</span>
          <button type="button" role="switch" :aria-checked="localShowRowTotals" :disabled="!editMode"
            class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors disabled:opacity-40"
            :class="localShowRowTotals ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
            @click="editMode && (localShowRowTotals = !localShowRowTotals, emitConfig())">
            <span class="inline-block h-4 w-4 rounded-full bg-white shadow transition mt-0.5"
              :class="localShowRowTotals ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
          </button>
        </div>
        <div class="flex items-center justify-between py-0.5">
          <span class="text-sm text-gray-700 dark:text-neutral-200">Column totals (grand-total row)</span>
          <button type="button" role="switch" :aria-checked="localShowColTotals" :disabled="!editMode"
            class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors disabled:opacity-40"
            :class="localShowColTotals ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
            @click="editMode && (localShowColTotals = !localShowColTotals, emitConfig())">
            <span class="inline-block h-4 w-4 rounded-full bg-white shadow transition mt-0.5"
              :class="localShowColTotals ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
          </button>
        </div>
      </div>

      <!-- Sort & limits -->
      <div class="space-y-2">
        <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Sort &amp; Limits</h3>
        <div class="flex items-center justify-between">
          <span class="text-sm text-gray-700 dark:text-neutral-200">Sort rows by</span>
          <select v-model="localSortBy" :disabled="!editMode"
            class="w-36 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @change="emitConfig()">
            <option value="">First row dimension</option>
            <option v-for="(v, i) in localValues" :key="i" :value="v.column">{{ v.label || v.column }}</option>
          </select>
        </div>
        <div v-if="localSortBy" class="flex items-center justify-between">
          <span class="text-sm text-gray-700 dark:text-neutral-200">Direction</span>
          <select v-model="localSortDir" :disabled="!editMode"
            class="w-28 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @change="emitConfig()">
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select>
        </div>
        <div class="flex items-center justify-between">
          <span class="text-sm text-gray-700 dark:text-neutral-200">Number of rows</span>
          <input v-model.number="localRowLimit" type="number" min="1" placeholder="All" :disabled="!editMode"
            class="w-20 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm text-center disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @input="emitConfig()" />
        </div>
        <div class="flex items-center justify-between">
          <span class="text-sm text-gray-700 dark:text-neutral-200">Number of columns</span>
          <input v-model.number="localColLimit" type="number" min="1" placeholder="All" :disabled="!editMode"
            class="w-20 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm text-center disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @input="emitConfig()" />
        </div>
      </div>
    </div>

    <p v-else class="text-sm text-gray-400 dark:text-neutral-500">Connect a data source (Data Source tab) to configure the pivot.</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { WidgetConfig, PivotTableWidgetConfig, PivotDimension, PivotValue, WidgetDataSource } from '~/types/dashboard'
import PivotFieldCard from './PivotFieldCard.vue'
import PivotDimCard from './PivotDimCard.vue'

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
function updateDim(kind: 'row' | 'col', i: number, updated: PivotDimension) {
  const arr = kind === 'row' ? localRowDims : localColDims
  const prev = arr.value[i]
  arr.value[i] = updated
  if (updated.column !== prev.column) emitBoth()
  else emitConfig()
}
function removeDim(kind: 'row' | 'col', i: number) {
  const arr = kind === 'row' ? localRowDims : localColDims
  arr.value.splice(i, 1)
  emitBoth()
}

function addValue() {
  localValues.value.push({ column: '', aggregation: 'sum', format: 'number', decimalPlaces: 0 })
  emitConfig()
}
function updateValue(i: number, updated: PivotValue) {
  const prev = localValues.value[i]
  localValues.value[i] = updated
  if (updated.column !== prev.column) emitBoth()
  else emitConfig()
}
function removeValue(i: number) {
  localValues.value.splice(i, 1)
  emitBoth()
}
</script>
