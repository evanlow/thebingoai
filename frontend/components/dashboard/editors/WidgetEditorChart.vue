<template>
  <div class="h-full overflow-y-auto p-5 space-y-5">

    <!-- Label -->
    <div class="space-y-1.5">
      <label class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Label</label>
      <input
        v-model="localTitle"
        type="text"
        placeholder="e.g. Monthly Revenue"
        class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
        :readonly="!editMode"
        :class="!editMode ? 'cursor-default bg-gray-50' : ''"
        @input="emitDebounced()"
      />
    </div>

    <!-- Chart Type -->
    <div class="space-y-2">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Chart Type</h3>
      <div class="grid grid-cols-3 gap-2">
        <button
          v-for="ct in chartTypes"
          :key="ct.value"
          class="flex flex-col items-center gap-1.5 rounded-lg border p-2.5 text-xs font-medium transition-colors"
          :class="localType === ct.value
            ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
            : 'border-gray-200 bg-white text-gray-500 hover:bg-gray-50'"
          :disabled="!editMode"
          @click="editMode && setType(ct.value)"
        >
          <component :is="ct.icon" class="h-4 w-4" />
          {{ ct.label }}
        </button>
      </div>
    </div>

    <!-- Dimensions & Metrics (only when data source is connected) -->
    <div v-if="chartMapping && sourceColumns && sourceColumns.length > 0" class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Dimensions & Metrics</h3>

      <!-- SCATTER: X + Y metric pickers -->
      <template v-if="localType === 'scatter'">
        <div class="space-y-3">
          <div class="space-y-1.5">
            <label class="text-xs text-gray-600">X Metric</label>
            <div class="flex gap-2">
              <select
                :value="chartMapping.xMetricColumn || ''"
                :disabled="!editMode"
                class="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
                @change="emitMappingPatch({ xMetricColumn: ($event.target as HTMLSelectElement).value || undefined })"
              >
                <option value="" disabled>Select column…</option>
                <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
              </select>
              <select
                :value="chartMapping.xAggregation || 'none'"
                :disabled="!editMode"
                class="w-28 rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
                @change="emitMappingPatch({ xAggregation: ($event.target as HTMLSelectElement).value as any })"
              >
                <option v-for="a in aggregationOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
              </select>
            </div>
          </div>
          <div class="space-y-1.5">
            <label class="text-xs text-gray-600">Y Metric</label>
            <div class="flex gap-2">
              <select
                :value="chartMapping.yMetricColumn || ''"
                :disabled="!editMode"
                class="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
                @change="emitMappingPatch({ yMetricColumn: ($event.target as HTMLSelectElement).value || undefined })"
              >
                <option value="" disabled>Select column…</option>
                <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
              </select>
              <select
                :value="chartMapping.yAggregation || 'none'"
                :disabled="!editMode"
                class="w-28 rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
                @change="emitMappingPatch({ yAggregation: ($event.target as HTMLSelectElement).value as any })"
              >
                <option v-for="a in aggregationOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
              </select>
            </div>
          </div>
        </div>
      </template>

      <!-- PIE / DOUGHNUT: 1 dimension + 1 metric -->
      <template v-else-if="localType === 'pie' || localType === 'doughnut'">
        <div class="space-y-3">
          <div class="space-y-1.5">
            <label class="text-xs text-gray-600">Dimension</label>
            <select
              :value="chartMapping.labelColumn || ''"
              :disabled="!editMode"
              class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
              @change="emitMappingPatch({ labelColumn: ($event.target as HTMLSelectElement).value || undefined })"
            >
              <option value="" disabled>Select column…</option>
              <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
            </select>
          </div>
          <div class="space-y-1.5">
            <label class="text-xs text-gray-600">Metric</label>
            <div class="flex gap-2">
              <select
                :value="chartMapping.datasetColumns[0]?.column || ''"
                :disabled="!editMode"
                class="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
                @change="updateDatasetColumn(0, 'column', ($event.target as HTMLSelectElement).value)"
              >
                <option value="" disabled>Select column…</option>
                <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
              </select>
              <select
                :value="chartMapping.datasetColumns[0]?.aggregation || 'sum'"
                :disabled="!editMode"
                class="w-28 rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
                @change="updateDatasetColumn(0, 'aggregation', ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="a in aggregationOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
              </select>
            </div>
            <input
              :value="chartMapping.datasetColumns[0]?.label || ''"
              type="text"
              placeholder="Label (optional)"
              :readonly="!editMode"
              class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
              :class="!editMode ? 'cursor-default bg-gray-50' : ''"
              @input="updateDatasetColumn(0, 'label', ($event.target as HTMLInputElement).value)"
            />
          </div>
        </div>
      </template>

      <!-- LINE / AREA / BAR: 1 dimension + N metrics -->
      <template v-else>
        <div class="space-y-3">
          <div class="space-y-1.5">
            <label class="text-xs text-gray-600">Dimension (X-axis)</label>
            <select
              :value="chartMapping.labelColumn || ''"
              :disabled="!editMode"
              class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
              @change="emitMappingPatch({ labelColumn: ($event.target as HTMLSelectElement).value || undefined })"
            >
              <option value="" disabled>Select column…</option>
              <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
            </select>
          </div>

          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <label class="text-xs text-gray-600">Metrics (Y-axis)</label>
              <button
                v-if="editMode"
                type="button"
                class="flex items-center gap-1 text-[11px] font-medium text-indigo-600 hover:text-indigo-700 transition-colors"
                @click="addDatasetColumn()"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
                Add Metric
              </button>
            </div>

            <!-- Empty state: guide user to add first metric -->
            <div
              v-if="!chartMapping.datasetColumns || chartMapping.datasetColumns.length === 0"
              class="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-3 py-4 text-center"
            >
              <p class="text-xs text-gray-400 mb-2">No metrics added yet</p>
              <button
                v-if="editMode"
                type="button"
                class="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 transition-colors"
                @click="addDatasetColumn()"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
                Add Metric (Y-axis)
              </button>
            </div>

            <div
              v-for="(ds, idx) in chartMapping.datasetColumns"
              :key="idx"
              class="rounded-lg border border-gray-200 p-2.5 space-y-2"
            >
              <div class="flex gap-2 items-start">
                <div class="flex-1 space-y-1.5">
                  <select
                    :value="ds.column || ''"
                    :disabled="!editMode"
                    class="w-full rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
                    @change="updateDatasetColumn(idx, 'column', ($event.target as HTMLSelectElement).value)"
                  >
                    <option value="" disabled>Column…</option>
                    <option v-for="col in sourceColumns" :key="col" :value="col">{{ col }}</option>
                  </select>
                  <select
                    :value="ds.aggregation || 'sum'"
                    :disabled="!editMode"
                    class="w-full rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50"
                    @change="updateDatasetColumn(idx, 'aggregation', ($event.target as HTMLSelectElement).value)"
                  >
                    <option v-for="a in aggregationOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
                  </select>
                  <input
                    :value="ds.label || ''"
                    type="text"
                    placeholder="Label"
                    :readonly="!editMode"
                    class="w-full rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
                    :class="!editMode ? 'cursor-default bg-gray-50' : ''"
                    @input="updateDatasetColumn(idx, 'label', ($event.target as HTMLInputElement).value)"
                  />
                </div>
                <button
                  v-if="editMode && chartMapping.datasetColumns.length > 1"
                  type="button"
                  class="mt-1 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded text-gray-400 hover:bg-rose-50 hover:text-rose-500 transition-colors"
                  @click="removeDatasetColumn(idx)"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- Sort (hidden for scatter) -->
    <div
      v-if="localType !== 'scatter'"
      class="space-y-3"
    >
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Sort</h3>
      <div class="space-y-2">
        <div class="space-y-1.5">
          <label class="text-[11px] text-gray-500">Sort by</label>
          <select
            v-model="localOptions.sortBy"
            class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
            :disabled="!editMode"
            :class="!editMode ? 'cursor-default bg-gray-50' : ''"
            @change="emitDebounced()"
          >
            <option value="none">None</option>
            <option value="label">Label</option>
            <option value="value">Value</option>
          </select>
        </div>
        <div v-if="localOptions.sortBy && localOptions.sortBy !== 'none'" class="space-y-1.5">
          <label class="text-[11px] text-gray-500">Direction</label>
          <select
            v-model="localOptions.sortDirection"
            class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
            :disabled="!editMode"
            :class="!editMode ? 'cursor-default bg-gray-50' : ''"
            @change="emitDebounced()"
          >
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Number of points (line/area) -->
    <div
      v-if="localType === 'line' || localType === 'area'"
      class="space-y-1.5"
    >
      <label class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Number of Points</label>
      <input
        v-model.number="localOptions.numberOfPoints"
        type="number"
        min="1"
        placeholder="All"
        class="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
        :readonly="!editMode"
        :class="!editMode ? 'cursor-default bg-gray-50' : ''"
        @input="emitDebounced()"
      />
      <p class="text-[11px] text-gray-400">Limits to the last N data points. Leave blank to show all.</p>
    </div>

    <!-- Stacked (bar / line / area) — 3-option segmented -->
    <div
      v-if="localType === 'bar' || localType === 'line' || localType === 'area'"
      class="space-y-2"
    >
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Stacked</h3>
      <div class="flex rounded border border-gray-200 overflow-hidden">
        <button
          v-for="opt in stackedOptions"
          :key="opt.value"
          type="button"
          :disabled="!editMode"
          class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="currentStacked === opt.value
            ? 'bg-indigo-600 text-white'
            : 'bg-white text-gray-500 hover:bg-gray-50'"
          @click="editMode && setStacked(opt.value as 'none' | 'standard' | 'percentage')"
        >{{ opt.label }}</button>
      </div>
    </div>

    <!-- Horizontal bars (bar only) -->
    <div
      v-if="localType === 'bar'"
      class="flex items-center justify-between py-1"
    >
      <span class="text-sm text-gray-700">Horizontal bars</span>
      <button
        type="button"
        role="switch"
        :aria-checked="localOptions.indexAxis === 'y'"
        :disabled="!editMode"
        class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
        :class="localOptions.indexAxis === 'y' ? 'bg-indigo-600' : 'bg-gray-200'"
        @click="editMode && (localOptions.indexAxis = localOptions.indexAxis === 'y' ? 'x' : 'y', emitDebounced())"
      >
        <span
          class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
          :class="localOptions.indexAxis === 'y' ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'"
        />
      </button>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, h } from 'vue'
import { LineChart, BarChart2, PieChart, TrendingUp } from 'lucide-vue-next'
import type { WidgetConfig, ChartWidgetConfig, ChartDataSourceMapping, ChartDatasetColumn, WidgetDataSource } from '~/types/dashboard'
import type { ChartType, ChartOptions } from '~/types/chart'

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

const chartConfig = computed(() => props.modelValue.config as ChartWidgetConfig)

const localTitle = ref(chartConfig.value.title ?? '')
const localType = ref<ChartType>(chartConfig.value.type)
const localOptions = ref<ChartOptions>(JSON.parse(JSON.stringify(chartConfig.value.options ?? {})))

const chartMapping = computed(() => {
  if (props.dataSource?.mapping?.type === 'chart') {
    return props.dataSource.mapping as ChartDataSourceMapping
  }
  return null
})

let debounceTimer: ReturnType<typeof setTimeout> | null = null

function emitDebounced() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    emit('update:modelValue', buildConfig())
  }, 150)
}

function buildConfig(): WidgetConfig {
  return {
    type: 'chart',
    config: {
      ...chartConfig.value,
      type: localType.value,
      title: localTitle.value || undefined,
      options: Object.keys(localOptions.value).length > 0 ? localOptions.value : undefined,
    },
  }
}

function setType(t: string) {
  localType.value = t as ChartType
  emitDebounced()
}

// ── Stacked segmented ────────────────────────────────────────────────────────

const stackedOptions = [
  { value: 'none', label: 'None' },
  { value: 'standard', label: 'Stacked' },
  { value: 'percentage', label: '100%' },
]

const currentStacked = computed(() => {
  const s = localOptions.value.stacked
  if (s === 'standard' || s === true) return 'standard'
  if (s === 'percentage') return 'percentage'
  return 'none'
})

function setStacked(value: 'none' | 'standard' | 'percentage') {
  localOptions.value.stacked = value === 'none' ? undefined : value
  emitDebounced()
}

// ── Mapping updates (dimension / metrics) ────────────────────────────────────

function emitMappingPatch(patch: Record<string, any>) {
  emit('update:mapping', patch)
}

function updateDatasetColumn(idx: number, field: keyof ChartDatasetColumn, value: any) {
  const cols = [...(chartMapping.value?.datasetColumns ?? [])]
  if (!cols[idx]) return
  cols[idx] = { ...cols[idx], [field]: value }
  emit('update:mapping', { datasetColumns: cols })
}

function addDatasetColumn() {
  const cols = [...(chartMapping.value?.datasetColumns ?? [])]
  cols.push({ column: '', label: `Metric ${cols.length + 1}`, aggregation: 'sum' })
  emit('update:mapping', { datasetColumns: cols })
}

function removeDatasetColumn(idx: number) {
  const cols = (chartMapping.value?.datasetColumns ?? []).filter((_, i) => i !== idx)
  emit('update:mapping', { datasetColumns: cols })
}

// ── Static data ──────────────────────────────────────────────────────────────

const aggregationOptions = [
  { value: 'sum', label: 'Sum' },
  { value: 'avg', label: 'Average' },
  { value: 'count', label: 'Count' },
  { value: 'countDistinct', label: 'Count Distinct' },
  { value: 'min', label: 'Min' },
  { value: 'max', label: 'Max' },
  { value: 'none', label: 'None (raw)' },
]

const DoughnutIcon = {
  render() {
    return h('svg', { xmlns: 'http://www.w3.org/2000/svg', width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
      h('circle', { cx: 12, cy: 12, r: 10 }),
      h('circle', { cx: 12, cy: 12, r: 4 }),
    ])
  },
}

const ScatterIcon = {
  render() {
    return h('svg', { xmlns: 'http://www.w3.org/2000/svg', width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
      h('circle', { cx: 7, cy: 17, r: 1.5, fill: 'currentColor' }),
      h('circle', { cx: 14, cy: 7, r: 1.5, fill: 'currentColor' }),
      h('circle', { cx: 18, cy: 14, r: 1.5, fill: 'currentColor' }),
      h('circle', { cx: 10, cy: 12, r: 1.5, fill: 'currentColor' }),
    ])
  },
}

const chartTypes = [
  { value: 'line', label: 'Line', icon: LineChart },
  { value: 'bar', label: 'Bar', icon: BarChart2 },
  { value: 'pie', label: 'Pie', icon: PieChart },
  { value: 'doughnut', label: 'Doughnut', icon: DoughnutIcon },
  { value: 'area', label: 'Area', icon: TrendingUp },
  { value: 'scatter', label: 'Scatter', icon: ScatterIcon },
]
</script>
