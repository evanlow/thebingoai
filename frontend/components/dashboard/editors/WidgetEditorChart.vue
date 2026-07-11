<template>
  <div class="h-full overflow-y-auto p-5 space-y-5">

    <!-- Label -->
    <div class="space-y-1.5">
      <label class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Label</label>
      <input
        v-model="localTitle"
        type="text"
        placeholder="e.g. Monthly Revenue"
        class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
        :readonly="!editMode"
        :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''"
        @input="emitDebounced()"
      />
    </div>

    <!-- Chart Type -->
    <div class="space-y-2">
      <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Chart Type</h3>
      <div class="grid grid-cols-3 gap-2">
        <button
          v-for="ct in chartTypes"
          :key="ct.value"
          class="flex flex-col items-center gap-1.5 rounded-lg border p-2.5 text-sm font-medium transition-colors"
          :class="localType === ct.value
            ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300'
            : 'border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
          :disabled="!editMode"
          @click="editMode && setType(ct.value)"
        >
          <component :is="ct.icon" class="h-4 w-4" />
          {{ ct.label }}
        </button>
      </div>
    </div>

    <!-- Dimensions & Metrics (only when data source is connected) -->
    <div v-if="chartMapping && columnOptions.length > 0" class="space-y-3">
      <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Dimensions & Metrics</h3>

      <!-- Incomplete mapping: tell the user exactly what's missing -->
      <div
        v-if="requiredMissing.length"
        class="rounded-lg border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-300"
      >
        Select {{ requiredMissing.join(', ') }} to display data.
      </div>

      <!-- SCATTER / BUBBLE: dimension + X/Y metric pickers (+ size for bubble) -->
      <template v-if="localType === 'scatter' || localType === 'bubble'">
        <div class="space-y-3">
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400"><span class="mr-1.5 inline-block h-2 w-2 rounded-full bg-emerald-500 align-middle" />Dimension (optional — groups &amp; colors points)</label>
            <select
              :value="chartMapping.labelColumn || ''"
              :disabled="!editMode"
              class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @change="emitMappingPatch({ labelColumn: ($event.target as HTMLSelectElement).value || undefined })"
            >
              <option value="">None</option>
              <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
            </select>
          </div>
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400"><span class="mr-1.5 inline-block h-2 w-2 rounded-full bg-sky-500 align-middle" />X Metric</label>
            <div class="flex gap-2">
              <select
                :value="chartMapping.xMetricColumn || ''"
                :disabled="!editMode"
                class="flex-1 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
                @change="emitMappingPatch({ xMetricColumn: ($event.target as HTMLSelectElement).value || undefined })"
              >
                <option value="" disabled>Select column…</option>
                <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
              </select>
              <select
                :value="chartMapping.xAggregation || 'none'"
                :disabled="!editMode"
                class="w-28 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
                @change="emitMappingPatch({ xAggregation: ($event.target as HTMLSelectElement).value as any })"
              >
                <option v-for="a in aggregationOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
              </select>
            </div>
          </div>
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400"><span class="mr-1.5 inline-block h-2 w-2 rounded-full bg-sky-500 align-middle" />Y Metric</label>
            <div class="flex gap-2">
              <select
                :value="chartMapping.yMetricColumn || ''"
                :disabled="!editMode"
                class="flex-1 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
                @change="emitMappingPatch({ yMetricColumn: ($event.target as HTMLSelectElement).value || undefined })"
              >
                <option value="" disabled>Select column…</option>
                <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
              </select>
              <select
                :value="chartMapping.yAggregation || 'none'"
                :disabled="!editMode"
                class="w-28 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
                @change="emitMappingPatch({ yAggregation: ($event.target as HTMLSelectElement).value as any })"
              >
                <option v-for="a in aggregationOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
              </select>
            </div>
          </div>
          <div v-if="localType === 'bubble'" class="space-y-1.5">
            <label class="text-xs text-gray-600 dark:text-neutral-400"><span class="mr-1.5 inline-block h-2 w-2 rounded-full bg-sky-500 align-middle" />Bubble Size Metric <span class="text-red-500">*</span></label>
            <select
              :value="chartMapping.sizeMetricColumn || ''"
              :disabled="!editMode"
              class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @change="emitMappingPatch({ sizeMetricColumn: ($event.target as HTMLSelectElement).value || undefined })"
            >
              <option value="" disabled>Select column…</option>
              <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
            </select>
            <p class="text-[11px] text-gray-400 dark:text-neutral-500">Point size scales with this metric.</p>
          </div>
        </div>
      </template>

      <!-- PIE / DOUGHNUT: 1 dimension + 1 metric -->
      <template v-else-if="localType === 'pie' || localType === 'doughnut'">
        <div class="space-y-3">
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400"><span class="mr-1.5 inline-block h-2 w-2 rounded-full bg-emerald-500 align-middle" />Dimension</label>
            <select
              :value="chartMapping.labelColumn || ''"
              :disabled="!editMode"
              class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @change="emitMappingPatch({ labelColumn: ($event.target as HTMLSelectElement).value || undefined })"
            >
              <option value="" disabled>Select column…</option>
              <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
            </select>
          </div>
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400"><span class="mr-1.5 inline-block h-2 w-2 rounded-full bg-sky-500 align-middle" />Metric</label>
            <div class="flex gap-2">
              <select
                :value="chartMapping.datasetColumns?.[0]?.column || ''"
                :disabled="!editMode"
                class="flex-1 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
                @change="updateDatasetColumn(0, 'column', ($event.target as HTMLSelectElement).value)"
              >
                <option value="" disabled>Select column…</option>
                <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
              </select>
              <select
                :value="chartMapping.datasetColumns?.[0]?.aggregation || 'sum'"
                :disabled="!editMode"
                class="w-28 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
                @change="updateDatasetColumn(0, 'aggregation', ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="a in aggregationOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
              </select>
            </div>
            <input
              :value="chartMapping.datasetColumns?.[0]?.label || ''"
              type="text"
              placeholder="Label (optional)"
              :readonly="!editMode"
              class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
              :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''"
              @input="updateDatasetColumn(0, 'label', ($event.target as HTMLInputElement).value)"
            />
          </div>
        </div>
      </template>

      <!-- FUNNEL: 1 dimension (stage) + 1 metric -->
      <template v-else-if="localType === 'funnel'">
        <div class="space-y-3">
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400"><span class="mr-1.5 inline-block h-2 w-2 rounded-full bg-emerald-500 align-middle" />Dimension (stage)</label>
            <select
              :value="chartMapping.labelColumn || ''"
              :disabled="!editMode"
              class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @change="emitMappingPatch({ labelColumn: ($event.target as HTMLSelectElement).value || undefined })"
            >
              <option value="" disabled>Select column…</option>
              <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
            </select>
          </div>
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400"><span class="mr-1.5 inline-block h-2 w-2 rounded-full bg-sky-500 align-middle" />Metric</label>
            <div class="flex gap-2">
              <select
                :value="chartMapping.datasetColumns?.[0]?.column || ''"
                :disabled="!editMode"
                class="flex-1 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
                @change="updateDatasetColumn(0, 'column', ($event.target as HTMLSelectElement).value)"
              >
                <option value="" disabled>Select column…</option>
                <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
              </select>
              <select
                :value="chartMapping.datasetColumns?.[0]?.aggregation || 'sum'"
                :disabled="!editMode"
                class="w-28 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
                @change="updateDatasetColumn(0, 'aggregation', ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="a in aggregationOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
              </select>
            </div>
          </div>
        </div>
      </template>

      <!-- TIMELINE: row label + start/end dates (+ optional bar label, tooltip) -->
      <template v-else-if="localType === 'timeline'">
        <div class="space-y-3">
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400">Row label</label>
            <select
              :value="chartMapping.labelColumn || ''"
              :disabled="!editMode"
              class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @change="emitMappingPatch({ labelColumn: ($event.target as HTMLSelectElement).value || undefined })"
            >
              <option value="" disabled>Select column…</option>
              <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
            </select>
          </div>
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400">Bar label (optional)</label>
            <select
              :value="chartMapping.barLabelColumn || ''"
              :disabled="!editMode"
              class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @change="emitMappingPatch({ barLabelColumn: ($event.target as HTMLSelectElement).value || undefined })"
            >
              <option value="">None</option>
              <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
            </select>
          </div>
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400">Start time</label>
            <select
              :value="chartMapping.startColumn || ''"
              :disabled="!editMode"
              class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @change="emitMappingPatch({ startColumn: ($event.target as HTMLSelectElement).value || undefined })"
            >
              <option value="" disabled>Select column…</option>
              <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
            </select>
          </div>
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400">End time</label>
            <select
              :value="chartMapping.endColumn || ''"
              :disabled="!editMode"
              class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @change="emitMappingPatch({ endColumn: ($event.target as HTMLSelectElement).value || undefined })"
            >
              <option value="" disabled>Select column…</option>
              <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
            </select>
          </div>
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400">Tooltip (optional)</label>
            <select
              :value="chartMapping.tooltipColumn || ''"
              :disabled="!editMode"
              class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @change="emitMappingPatch({ tooltipColumn: ($event.target as HTMLSelectElement).value || undefined })"
            >
              <option value="">None</option>
              <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
            </select>
          </div>
        </div>
      </template>

      <!-- LINE / AREA / BAR: 1 dimension + N metrics -->
      <template v-else>
        <div class="space-y-3">
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400"><span class="mr-1.5 inline-block h-2 w-2 rounded-full bg-emerald-500 align-middle" />Dimension (X-axis)</label>
            <select
              :value="chartMapping.labelColumn || ''"
              :disabled="!editMode"
              class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @change="emitMappingPatch({ labelColumn: ($event.target as HTMLSelectElement).value || undefined })"
            >
              <option value="" disabled>Select column…</option>
              <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
            </select>
          </div>

          <!-- Datetime drill-down -->
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400">Time granularity</label>
            <select
              :value="chartMapping?.dateGranularity || 'none'"
              :disabled="!editMode"
              class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @change="emitMappingPatch({ dateGranularity: ($event.target as HTMLSelectElement).value === 'none' ? undefined : ($event.target as HTMLSelectElement).value })"
            >
              <option v-for="g in dateGranularityOptions" :key="g.value" :value="g.value">{{ g.label }}</option>
            </select>
            <p class="text-sm text-gray-400 dark:text-neutral-500">Bucket a date/timestamp dimension. Leave "None" for plain categories.</p>
          </div>

          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <label class="text-sm text-gray-600 dark:text-neutral-400"><span class="mr-1.5 inline-block h-2 w-2 rounded-full bg-sky-500 align-middle" />Metrics (Y-axis)</label>
              <button
                v-if="editMode"
                type="button"
                class="flex items-center gap-1 text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors"
                @click="addDatasetColumn()"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
                Add Metric
              </button>
            </div>

            <!-- Empty state: guide user to add first metric -->
            <div
              v-if="!chartMapping.datasetColumns || chartMapping.datasetColumns.length === 0"
              class="rounded-lg border border-dashed border-gray-200 dark:border-neutral-700 bg-gray-50 dark:bg-neutral-900 px-3 py-4 text-center"
            >
              <p class="text-sm text-gray-400 dark:text-neutral-500 mb-2">No metrics added yet</p>
              <button
                v-if="editMode"
                type="button"
                class="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
                @click="addDatasetColumn()"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>
                Add Metric (Y-axis)
              </button>
            </div>

            <!-- Collapsible metric cards (Table-style) -->
            <div
              v-for="(ds, idx) in chartMapping.datasetColumns"
              :key="idx"
              class="relative rounded-lg border border-gray-200 dark:border-neutral-700 bg-gray-50 dark:bg-neutral-900 transition-shadow"
              :class="expandedDatasets.has(idx) ? 'p-3 space-y-2' : ''"
            >
              <!-- Collapsed header -->
              <button
                v-if="!expandedDatasets.has(idx)"
                type="button"
                class="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-gray-100 dark:hover:bg-neutral-700 rounded-lg transition-colors"
                @click="expandDataset(idx)"
              >
                <div class="flex items-center gap-2 min-w-0">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 text-gray-400 dark:text-neutral-500 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>
                  <span class="text-sm font-medium text-gray-700 dark:text-neutral-200 truncate">{{ ds.label || ds.column || 'Untitled metric' }}</span>
                  <span class="text-sm px-1.5 py-0.5 rounded bg-indigo-50 dark:bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 flex-shrink-0">{{ ds.aggregation || 'sum' }}</span>
                </div>
                <button
                  v-if="editMode && chartMapping.datasetColumns.length > 1"
                  type="button"
                  class="flex h-5 w-5 items-center justify-center rounded text-gray-300 dark:text-neutral-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 hover:text-rose-500 dark:hover:text-rose-400 transition-colors flex-shrink-0"
                  @click.stop="removeDatasetColumn(idx)"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
                </button>
              </button>

              <!-- Expanded body -->
              <template v-if="expandedDatasets.has(idx)">
                <button
                  type="button"
                  class="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded text-gray-400 dark:text-neutral-500 hover:bg-gray-200 dark:hover:bg-neutral-600 hover:text-gray-600 dark:hover:text-neutral-300 transition-colors z-10"
                  @click="collapseDataset(idx)"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 15-6-6-6 6"/></svg>
                </button>
                <div class="flex-1 space-y-1.5 pt-5">
                  <select
                    :value="ds.column || ''"
                    :disabled="!editMode"
                    class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
                    @change="updateDatasetColumn(idx, 'column', ($event.target as HTMLSelectElement).value)"
                  >
                    <option value="" disabled>Column…</option>
                    <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
                  </select>
                  <select
                    :value="ds.aggregation || 'sum'"
                    :disabled="!editMode"
                    class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
                    @change="updateDatasetColumn(idx, 'aggregation', ($event.target as HTMLSelectElement).value)"
                  >
                    <option v-for="a in aggregationOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
                  </select>
                  <input
                    :value="ds.label || ''"
                    type="text"
                    placeholder="Label"
                    :readonly="!editMode"
                    class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 transition-colors"
                    :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''"
                    @input="updateDatasetColumn(idx, 'label', ($event.target as HTMLInputElement).value)"
                  />
                  <button
                    v-if="editMode && chartMapping.datasetColumns.length > 1"
                    type="button"
                    class="flex h-5 w-5 items-center justify-center rounded text-gray-300 dark:text-neutral-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 hover:text-rose-500 dark:hover:text-rose-400 transition-colors"
                    @click="removeDatasetColumn(idx)"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
                  </button>
                </div>
              </template>
            </div>
          </div>

          <!-- Series breakdown -->
          <div class="space-y-1.5">
            <label class="text-sm text-gray-600 dark:text-neutral-400"><span class="mr-1.5 inline-block h-2 w-2 rounded-full bg-emerald-500 align-middle" />Break down by (optional)</label>
            <select
              :value="chartMapping?.breakdownColumn || ''"
              :disabled="!editMode"
              class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @change="emitMappingPatch({ breakdownColumn: ($event.target as HTMLSelectElement).value || undefined })"
            >
              <option value="">None</option>
              <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
            </select>
            <p v-if="chartMapping?.breakdownColumn" class="text-sm text-gray-400 dark:text-neutral-500">Splits the first metric into one series per value. Use Stacked / 100% (below) for stacked bars.</p>
          </div>
        </div>
      </template>
    </div>

    <!-- No data source / no columns yet: explain instead of hiding the section -->
    <div v-else class="space-y-2">
      <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Dimensions & Metrics</h3>
      <div class="rounded-lg border border-dashed border-gray-200 dark:border-neutral-700 bg-gray-50 dark:bg-neutral-900 px-3 py-4 text-center text-sm text-gray-400 dark:text-neutral-500">
        {{ dataSource ? 'No columns available from the query yet.' : 'Connect a data source in the Data Source tab to configure dimensions and metrics.' }}
      </div>
    </div>

    <!-- Sort (hidden for scatter / timeline) -->
    <div
      v-if="localType !== 'scatter' && localType !== 'bubble' && localType !== 'timeline'"
      class="space-y-3"
    >
      <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Sort</h3>
      <div class="space-y-2">
        <div class="space-y-1.5">
          <label class="text-sm text-gray-500 dark:text-neutral-400">Sort by</label>
          <select
            v-model="localOptions.sortBy"
            class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
            :disabled="!editMode"
            :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''"
            @change="emitDebounced()"
          >
            <option value="none">None</option>
            <option value="label">Label</option>
            <option value="value">Value</option>
          </select>
        </div>
        <div v-if="localOptions.sortBy && localOptions.sortBy !== 'none'" class="space-y-1.5">
          <label class="text-sm text-gray-500 dark:text-neutral-400">Direction</label>
          <select
            v-model="localOptions.sortDirection"
            class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
            :disabled="!editMode"
            :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''"
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
      <label class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Number of Points</label>
      <input
        v-model.number="localOptions.numberOfPoints"
        type="number"
        min="1"
        placeholder="All"
        class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-colors"
        :readonly="!editMode"
        :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''"
        @input="emitDebounced()"
      />
      <p class="text-sm text-gray-400 dark:text-neutral-500">Limits to the last N data points. Leave blank to show all.</p>
    </div>

    <!-- Stacked (bar / line / area) — 3-option segmented -->
    <div
      v-if="localType === 'bar' || localType === 'line' || localType === 'area'"
      class="space-y-2"
    >
      <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Stacked</h3>
      <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
        <button
          v-for="opt in stackedOptions"
          :key="opt.value"
          type="button"
          :title="opt.hint"
          :disabled="!editMode"
          class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="currentStacked === opt.value
            ? 'bg-indigo-600 text-white'
            : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
          @click="editMode && setStacked(opt.value as 'none' | 'standard' | 'percentage')"
        >{{ opt.label }}</button>
      </div>
    </div>

    <!-- Horizontal bars (bar only) -->
    <div
      v-if="localType === 'bar'"
      class="flex items-center justify-between py-1"
    >
      <span class="text-sm text-gray-700 dark:text-neutral-200">Horizontal bars</span>
      <button
        type="button"
        role="switch"
        :aria-checked="localOptions.indexAxis === 'y'"
        :disabled="!editMode"
        class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
        :class="localOptions.indexAxis === 'y' ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
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
import { LineChart, BarChart2, PieChart, TrendingUp, Filter, GanttChart } from 'lucide-vue-next'
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

// Column picker options: source columns plus any column the mapping already
// references — selections stay visible even when the source-columns fetch
// fails or the list is missing a SQL alias.
const columnOptions = computed(() => {
  const cols = new Set(props.sourceColumns ?? [])
  const m = chartMapping.value
  if (m) {
    for (const c of [m.labelColumn, m.xMetricColumn, m.yMetricColumn, m.sizeMetricColumn, m.breakdownColumn,
                     m.startColumn, m.endColumn, m.barLabelColumn, m.tooltipColumn]) {
      if (c) cols.add(c)
    }
    for (const dc of m.datasetColumns ?? []) if (dc.column) cols.add(dc.column)
  }
  return [...cols]
})

// Required fields still unset for the current chart type — drives the inline
// "Select … to display data" hint (Looker-style guidance instead of a blank chart).
const requiredMissing = computed<string[]>(() => {
  const m = chartMapping.value
  if (!m) return []
  const missing: string[] = []
  const t = localType.value
  if (t === 'scatter' || t === 'bubble') {
    if (!m.xMetricColumn) missing.push('an X metric')
    if (!m.yMetricColumn) missing.push('a Y metric')
    if (t === 'bubble' && !m.sizeMetricColumn) missing.push('a bubble size metric')
  } else if (t === 'timeline') {
    if (!m.labelColumn) missing.push('a row label')
    if (!m.startColumn) missing.push('a start time')
    if (!m.endColumn) missing.push('an end time')
  } else {
    if (!m.labelColumn) missing.push('a dimension')
    if (!m.datasetColumns?.some(d => d.column)) missing.push('a metric')
  }
  return missing
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
  const prev = localType.value
  localType.value = t as ChartType
  // Leaving bubble: drop the size metric so points return to fixed radius.
  if (prev === 'bubble' && t !== 'bubble' && chartMapping.value?.sizeMetricColumn) {
    emitMappingPatch({ sizeMetricColumn: undefined })
  }
  emitDebounced()
}

// ── Stacked segmented ────────────────────────────────────────────────────────

const stackedOptions = [
  { value: 'none', label: 'None', hint: 'Series drawn side by side' },
  { value: 'standard', label: 'Stacked', hint: 'Series stacked on top of each other (absolute values)' },
  { value: 'percentage', label: '100%', hint: 'Each stack normalized to 100% — shows share, not absolute values' },
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
  // Single-metric types (pie/doughnut/funnel) have no "Add Metric" button, so
  // the first selection must create the entry rather than silently no-op.
  while (cols.length <= idx) cols.push({ column: '', label: '', aggregation: 'sum' })
  cols[idx] = { ...cols[idx], [field]: value }
  emit('update:mapping', { datasetColumns: cols })
}

function addDatasetColumn() {
  const cols = [...(chartMapping.value?.datasetColumns ?? [])]
  const newIdx = cols.length
  cols.push({ column: '', label: `Metric ${cols.length + 1}`, aggregation: 'sum' })
  emit('update:mapping', { datasetColumns: cols })
  expandDataset(newIdx)
}

function removeDatasetColumn(idx: number) {
  const cols = (chartMapping.value?.datasetColumns ?? []).filter((_, i) => i !== idx)
  emit('update:mapping', { datasetColumns: cols })
  expandedDatasets.value.delete(idx)
}

// ── Collapsible metric cards ─────────────────────────────────────────────────
const expandedDatasets = ref<Set<number>>(new Set())
function expandDataset(idx: number) {
  expandedDatasets.value = new Set(expandedDatasets.value).add(idx)
}
function collapseDataset(idx: number) {
  const next = new Set(expandedDatasets.value)
  next.delete(idx)
  expandedDatasets.value = next
}

// ── Static data ──────────────────────────────────────────────────────────────

const dateGranularityOptions = [
  { value: 'none', label: 'None' },
  { value: 'year', label: 'Year' },
  { value: 'quarter', label: 'Quarter' },
  { value: 'month', label: 'Month' },
  { value: 'week', label: 'Week' },
  { value: 'day', label: 'Day' },
  { value: 'hour', label: 'Hour' },
  { value: 'hour_of_day', label: 'Hour of day' },
  { value: 'day_of_week', label: 'Day of week' },
  { value: 'month_of_year', label: 'Month of year' },
]

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

const BubbleIcon = {
  render() {
    return h('svg', { xmlns: 'http://www.w3.org/2000/svg', width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
      h('circle', { cx: 8, cy: 15, r: 4 }),
      h('circle', { cx: 16, cy: 8, r: 2.5 }),
      h('circle', { cx: 18.5, cy: 16.5, r: 1.5 }),
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
  { value: 'bubble', label: 'Bubble', icon: BubbleIcon },
  { value: 'funnel', label: 'Funnel', icon: Filter },
  { value: 'timeline', label: 'Timeline', icon: GanttChart },
]
</script>
