<template>
  <div class="h-full overflow-y-auto p-5 space-y-5 [&>*+*]:border-t [&>*+*]:border-gray-200 dark:[&>*+*]:border-neutral-700 [&>*+*]:pt-5">

    <!-- 1. Title -->
    <StyleSection title="Title">
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Show title</span>
        <button type="button" role="switch" :aria-checked="!!localOpts.showTitle" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.showTitle ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
          @click="editMode && toggle('showTitle')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.showTitle ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <template v-if="localOpts.showTitle">
        <div class="space-y-1">
          <label class="text-sm text-gray-700 dark:text-neutral-200">Title text</label>
          <input v-model="localTitle" type="text" placeholder="Chart title…" :readonly="!editMode"
            class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300"
            :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''"
            @input="emitUpdate()" />
        </div>
        <div class="flex gap-3">
          <div class="flex-1 space-y-1">
            <label class="text-sm text-gray-700 dark:text-neutral-200">Position</label>
            <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
              <button v-for="opt in [{ value: 'top', label: 'Top' }, { value: 'bottom', label: 'Bottom' }]" :key="opt.value"
                type="button" :disabled="!editMode"
                class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="(localOpts.titlePosition ?? 'top') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
                @click="editMode && setOpt('titlePosition', opt.value)">{{ opt.label }}</button>
            </div>
          </div>
          <div class="flex-1 space-y-1">
            <label class="text-sm text-gray-700 dark:text-neutral-200">Align</label>
            <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
              <button v-for="opt in [{ value: 'left', label: 'L' }, { value: 'center', label: 'C' }, { value: 'right', label: 'R' }]" :key="opt.value"
                type="button" :disabled="!editMode"
                class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="(localOpts.titleAlignment ?? 'center') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
                @click="editMode && setOpt('titleAlignment', opt.value)">{{ opt.label }}</button>
            </div>
          </div>
        </div>
        <div class="flex items-center justify-between gap-2">
          <span class="text-sm text-gray-700 dark:text-neutral-200">Family</span>
          <select v-model="localOpts.titleFontFamily" :disabled="!editMode"
            class="rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @change="emitUpdate()">
            <option value="system">System</option>
            <option value="sans">Sans-serif</option>
            <option value="serif">Serif</option>
            <option value="mono">Monospace</option>
          </select>
        </div>
        <div class="space-y-1.5">
          <label class="text-sm text-gray-700 dark:text-neutral-200">Size</label>
          <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
            <button
              v-for="opt in fontSizeOptions"
              :key="opt.value"
              type="button"
              :disabled="!editMode"
              class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="(localOpts.titleFontSize ?? 'sm') === opt.value
                ? 'bg-indigo-600 text-white'
                : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
              @click="editMode && setOpt('titleFontSize', opt.value)"
            >{{ opt.label }}</button>
          </div>
        </div>
        <div class="flex items-center justify-between gap-2">
          <span class="text-sm text-gray-700 dark:text-neutral-200">Color</span>
          <ColorPickerPopover v-model="localOpts.titleFontColor" :disabled="!editMode" @update:model-value="emitUpdate()" />
        </div>
      </template>
    </StyleSection>

    <!-- Funnel options -->
    <StyleSection v-if="isFunnel" title="Funnel" body-class="space-y-3">
      <div class="space-y-1.5">
        <label class="text-sm text-gray-700 dark:text-neutral-200">Funnel shape</label>
        <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
          <button v-for="opt in [{ value: 'smoothed', label: 'Smoothed' }, { value: 'stepped', label: 'Stepped' }]" :key="opt.value"
            type="button" :disabled="!editMode"
            class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localOpts.funnelShape ?? 'smoothed') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
            @click="editMode && setOpt('funnelShape', opt.value)">{{ opt.label }}</button>
        </div>
      </div>
      <div class="space-y-1.5">
        <label class="text-sm text-gray-700 dark:text-neutral-200">Show data labels as</label>
        <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
          <button v-for="opt in [{ value: 'number', label: 'Number' }, { value: 'percentage', label: '%' }, { value: 'numberPercentage', label: 'Num + %' }]" :key="opt.value"
            type="button" :disabled="!editMode"
            class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localOpts.funnelLabelMode ?? 'numberPercentage') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
            @click="editMode && setOpt('funnelLabelMode', opt.value)">{{ opt.label }}</button>
        </div>
      </div>
      <div v-if="(localOpts.funnelLabelMode ?? 'numberPercentage') !== 'number'" class="space-y-1.5">
        <label class="text-sm text-gray-700 dark:text-neutral-200">Percentage type</label>
        <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
          <button v-for="opt in [{ value: 'max', label: '% of max' }, { value: 'previous', label: '% of previous' }]" :key="opt.value"
            type="button" :disabled="!editMode"
            class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localOpts.funnelPercentType ?? 'max') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
            @click="editMode && setOpt('funnelPercentType', opt.value)">{{ opt.label }}</button>
        </div>
      </div>
      <div class="space-y-1.5">
        <label class="text-sm text-gray-700 dark:text-neutral-200">Color by</label>
        <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
          <button v-for="opt in [{ value: 'single', label: 'Single color' }, { value: 'byValue', label: 'By value' }]" :key="opt.value"
            type="button" :disabled="!editMode"
            class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localOpts.funnelColorMode ?? 'byValue') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
            @click="editMode && setOpt('funnelColorMode', opt.value)">{{ opt.label }}</button>
        </div>
      </div>
    </StyleSection>

    <!-- Timeline options -->
    <StyleSection v-if="isTimeline" title="Timeline" body-class="space-y-3">
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Group by row label</span>
        <button type="button" role="switch" :aria-checked="!!localOpts.timelineGroupByRowLabel" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.timelineGroupByRowLabel ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
          @click="editMode && toggle('timelineGroupByRowLabel')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.timelineGroupByRowLabel ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <div class="space-y-1.5">
        <label class="text-sm text-gray-700 dark:text-neutral-200">Color by</label>
        <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
          <button v-for="opt in [{ value: 'row', label: 'Row label' }, { value: 'bar', label: 'Bar label' }]" :key="opt.value"
            type="button" :disabled="!editMode"
            class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localOpts.timelineColorBy ?? 'row') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
            @click="editMode && setOpt('timelineColorBy', opt.value)">{{ opt.label }}</button>
        </div>
      </div>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Alternating row colors</span>
        <button type="button" role="switch" :aria-checked="!!localOpts.timelineAltRows" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.timelineAltRows ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
          @click="editMode && toggle('timelineAltRows')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.timelineAltRows ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
    </StyleSection>

    <!-- 2. Series -->
    <StyleSection v-if="isStandardChart" title="Series" body-class="space-y-3">
      <p v-if="!localDatasets.length" class="text-sm text-gray-400 dark:text-neutral-500">No datasets yet. Connect a data source first.</p>
      <div v-for="(ds, i) in localDatasets" :key="i" class="rounded-lg border border-gray-100 dark:border-neutral-800 overflow-hidden">
        <!-- Series header: tinted bar + color dot so series names read as headers, not fields -->
        <button
          type="button"
          class="flex w-full items-center justify-between gap-2 bg-gray-50 dark:bg-neutral-800/80 px-3 py-2 text-left hover:bg-gray-100 dark:hover:bg-neutral-700/70 transition-colors"
          @click="toggleSeriesExpanded(i)"
        >
          <span class="flex min-w-0 items-center gap-2">
            <span
              class="h-2.5 w-2.5 flex-shrink-0 rounded-full border border-black/10 dark:border-white/20"
              :style="{ background: seriesSwatch(ds, i) }"
            />
            <span class="truncate text-sm font-semibold text-gray-800 dark:text-neutral-100">{{ ds.label || `Series ${i + 1}` }}</span>
          </span>
          <ChevronDown
            class="h-3.5 w-3.5 flex-shrink-0 text-gray-400 dark:text-neutral-500 transition-transform"
            :class="expandedSeries.has(i) ? 'rotate-180' : ''"
          />
        </button>

        <div v-if="expandedSeries.has(i)" class="p-3 space-y-2.5">
          <!-- Series type (combo) — cartesian charts only -->
          <div v-if="!isPie" class="space-y-1">
            <label class="text-sm text-gray-700 dark:text-neutral-200">Series type</label>
            <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
              <button v-for="opt in seriesTypeOptions" :key="opt.value" type="button" :disabled="!editMode"
                class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="(ds.seriesType ?? defaultSeriesType) === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
                @click="editMode && setDatasetProp(i, 'seriesType', opt.value)">{{ opt.label }}</button>
            </div>
          </div>

          <!-- Color -->
          <div class="flex items-center justify-between gap-2">
            <span class="text-sm text-gray-700 dark:text-neutral-200">Color</span>
            <ColorPickerPopover :model-value="ds.borderColor as string | undefined" :disabled="!editMode"
              @update:model-value="setDatasetColor(i, $event)" />
          </div>

          <!-- Line-only options -->
          <template v-if="(ds.seriesType ?? defaultSeriesType) === 'line'">
            <div class="space-y-1">
              <label class="text-sm text-gray-700 dark:text-neutral-200">Line style</label>
              <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
                <button v-for="opt in lineStyleOptions" :key="opt.value" type="button" :disabled="!editMode"
                  class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
                  :class="(ds.lineStyle ?? 'solid') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
                  @click="editMode && setDatasetProp(i, 'lineStyle', opt.value)">{{ opt.label }}</button>
              </div>
            </div>
            <div class="flex items-center justify-between gap-2">
              <span class="text-sm text-gray-700 dark:text-neutral-200">Line weight</span>
              <input v-model.number="localDatasets[i].lineWeight" type="range" min="1" max="6" step="1"
                :disabled="!editMode" class="w-24 accent-indigo-600" @input="emitUpdate()" />
              <span class="text-sm text-gray-500 dark:text-neutral-400 w-4">{{ ds.lineWeight ?? 2 }}</span>
            </div>
            <div class="flex items-center justify-between py-0.5">
              <span class="text-sm text-gray-700 dark:text-neutral-200">Smooth</span>
              <button type="button" role="switch" :aria-checked="(ds.tension ?? 0.4) > 0" :disabled="!editMode"
                class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="(ds.tension ?? 0.4) > 0 ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
                @click="editMode && setDatasetProp(i, 'tension', (ds.tension ?? 0.4) > 0 ? 0 : 0.4)">
                <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
                  :class="(ds.tension ?? 0.4) > 0 ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
              </button>
            </div>
            <div class="flex items-center justify-between py-0.5">
              <span class="text-sm text-gray-700 dark:text-neutral-200">Show points</span>
              <button type="button" role="switch" :aria-checked="ds.showPoints === true" :disabled="!editMode"
                class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="ds.showPoints === true ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
                @click="editMode && setDatasetProp(i, 'showPoints', !(ds.showPoints === true))">
                <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
                  :class="ds.showPoints === true ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
              </button>
            </div>
            <div class="flex items-center justify-between py-0.5">
              <span class="text-sm text-gray-700 dark:text-neutral-200">Stepped lines</span>
              <button type="button" role="switch" :aria-checked="!!ds.stepped" :disabled="!editMode"
                class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="ds.stepped ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
                @click="editMode && setDatasetProp(i, 'stepped', !ds.stepped)">
                <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
                  :class="ds.stepped ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
              </button>
            </div>
            <div class="flex items-center justify-between py-0.5">
              <span class="text-sm text-gray-700 dark:text-neutral-200">Gradient fill</span>
              <button type="button" role="switch" :aria-checked="!!ds.gradient" :disabled="!editMode"
                class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="ds.gradient ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
                @click="editMode && setDatasetProp(i, 'gradient', !ds.gradient)">
                <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
                  :class="ds.gradient ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
              </button>
            </div>
          </template>

          <!-- Cumulative — cartesian charts only -->
          <div v-if="!isPie" class="flex items-center justify-between py-0.5">
            <span class="text-sm text-gray-700 dark:text-neutral-200">Cumulative</span>
            <button type="button" role="switch" :aria-checked="!!ds.cumulative" :disabled="!editMode"
              class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="ds.cumulative ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
              @click="editMode && setDatasetProp(i, 'cumulative', !ds.cumulative)">
              <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
                :class="ds.cumulative ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
            </button>
          </div>

          <!-- Show data labels (hidden for pie — use Slice label in General instead) -->
          <div v-if="!isPie" class="flex items-center justify-between py-0.5">
            <span class="text-sm text-gray-700 dark:text-neutral-200">Show data labels</span>
            <button type="button" role="switch" :aria-checked="!!ds.showDataLabels" :disabled="!editMode"
              class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="ds.showDataLabels ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
              @click="editMode && setDatasetProp(i, 'showDataLabels', !ds.showDataLabels)">
              <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
                :class="ds.showDataLabels ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
            </button>
          </div>

          <!-- Y-axis assignment -->
          <div v-if="localDatasets.length > 1" class="space-y-1">
            <label class="text-sm text-gray-700 dark:text-neutral-200">Y-axis</label>
            <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
              <button v-for="opt in [{ value: 'left', label: 'Left' }, { value: 'right', label: 'Right' }]" :key="opt.value"
                type="button" :disabled="!editMode"
                class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="(ds.yAxisID ?? 'left') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
                @click="editMode && setDatasetProp(i, 'yAxisID', opt.value)">{{ opt.label }}</button>
            </div>
          </div>

          <!-- Trendline — cartesian charts only -->
          <div v-if="!isPie" class="space-y-1.5 pt-1 border-t border-gray-100 dark:border-neutral-800">
            <label class="text-sm font-medium text-gray-600 dark:text-neutral-400">Trendline</label>
            <select :value="ds.trendline?.type ?? 'none'" :disabled="!editMode"
              class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @change="setTrendlineType(i, ($event.target as HTMLSelectElement).value)">
              <option value="none">None</option>
              <option value="linear">Linear</option>
              <option value="movingAverage">Moving average</option>
              <option value="exponential">Exponential</option>
              <option value="polynomial" disabled>Polynomial (coming soon)</option>
            </select>
            <template v-if="ds.trendline?.type && ds.trendline.type !== 'none'">
              <div v-if="ds.trendline.type === 'movingAverage'" class="flex items-center justify-between gap-2">
                <span class="text-sm text-gray-700 dark:text-neutral-200">Period</span>
                <input :value="ds.trendline.period ?? 3" type="number" min="2" max="50" :disabled="!editMode"
                  class="w-16 rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm text-center text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
                  @input="setTrendlineProp(i, 'period', +($event.target as HTMLInputElement).value)" />
              </div>
              <div class="flex items-center justify-between gap-2">
                <span class="text-sm text-gray-700 dark:text-neutral-200">Color</span>
                <ColorPickerPopover :model-value="ds.trendline.color" :disabled="!editMode"
                  @update:model-value="setTrendlineProp(i, 'color', $event)" />
              </div>
              <div class="space-y-1">
                <label class="text-sm text-gray-700 dark:text-neutral-200">Style</label>
                <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
                  <button v-for="opt in lineStyleOptions" :key="opt.value" type="button" :disabled="!editMode"
                    class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
                    :class="(ds.trendline.style ?? 'dashed') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
                    @click="editMode && setTrendlineProp(i, 'style', opt.value)">{{ opt.label }}</button>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </StyleSection>

    <!-- 3. General -->
    <StyleSection v-if="isStandardChart" title="General">
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Show legend</span>
        <button type="button" role="switch" :aria-checked="localOpts.showLegend !== false" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.showLegend !== false ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
          @click="editMode && toggle('showLegend')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.showLegend !== false ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Show tooltips</span>
        <button type="button" role="switch" :aria-checked="localOpts.showTooltips !== false" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.showTooltips !== false ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
          @click="editMode && toggle('showTooltips')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.showTooltips !== false ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <!-- Pie/doughnut: slice label type (Data Studio parity) -->
      <div v-if="isPie" class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Slice label</span>
        <select :value="localOpts.sliceLabel ?? 'percentage'" :disabled="!editMode"
          class="w-32 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
          @change="setOpt('sliceLabel', ($event.target as HTMLSelectElement).value)">
          <option v-for="opt in sliceLabelOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
      <!-- Data labels for non-pie charts are controlled per-series in the Series tab
           ("Show data labels"). The old chart-wide "Show values" toggle was removed
           to avoid two controls doing the same thing. -->
      <!-- Round Values — applies to axes, tooltips, and labels -->
      <div class="flex items-center justify-between py-1">
        <div>
          <span class="text-sm text-gray-700 dark:text-neutral-200">Round values</span>
          <p class="text-sm text-gray-400 dark:text-neutral-500 mt-0.5">Abbreviate to K / M / B on axes, tooltips, and labels</p>
        </div>
        <button type="button" role="switch" :aria-checked="!!localOpts.roundValues" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.roundValues ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
          @click="editMode && toggle('roundValues')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.roundValues ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Decimal places</span>
        <input v-model.number="localOpts.decimalPlaces" type="number" min="0" max="10" :disabled="!editMode"
          class="w-16 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm text-center text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
          @input="emitUpdate()" />
      </div>
    </StyleSection>

    <!-- 4. Missing data (date mode only) -->
    <StyleSection v-if="chartConfig.options?.xAxisMode === 'date'" title="Missing Data">
      <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
        <button v-for="opt in missingDataOptions" :key="opt.value" type="button" :title="opt.hint" :disabled="!editMode"
          class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="(localOpts.missingData ?? 'lineToZero') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
          @click="editMode && setOpt('missingData', opt.value)">{{ opt.label }}</button>
      </div>
    </StyleSection>

    <!-- 5. Reference Lines -->
    <StyleSection v-if="hasAxes" title="Reference Lines">
      <template #action>
          <button v-if="editMode" type="button"
            class="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-200"
            @click.stop.prevent="addReferenceLine()">+ Add</button>
      </template>
      <div v-if="!localOpts.referenceLines?.length" class="text-sm text-gray-400 dark:text-neutral-500">No reference lines.</div>
      <div v-for="(rl, ri) in (localOpts.referenceLines ?? [])" :key="rl.id ?? ri"
        class="rounded border border-gray-100 dark:border-neutral-800 p-2.5 space-y-2">
        <div class="grid grid-cols-2 gap-2">
          <input :value="rl.value" type="number" placeholder="Value" :disabled="!editMode"
            class="w-full min-w-0 rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @input="setRefLineProp(ri, 'value', +($event.target as HTMLInputElement).value)" />
          <input :value="rl.label ?? ''" type="text" placeholder="Label" :disabled="!editMode"
            class="w-full min-w-0 rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @input="setRefLineProp(ri, 'label', ($event.target as HTMLInputElement).value)" />
        </div>
        <div class="flex items-center gap-2">
          <div class="flex flex-1 min-w-0 rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
            <button v-for="opt in lineStyleOptions" :key="opt.value" type="button" :disabled="!editMode"
              class="flex-1 py-1 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="(rl.style ?? 'dashed') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
              @click="editMode && setRefLineProp(ri, 'style', opt.value)">{{ opt.label }}</button>
          </div>
          <ColorPickerPopover :model-value="rl.color" :disabled="!editMode"
            @update:model-value="setRefLineProp(ri, 'color', $event)" />
          <button v-if="editMode" type="button" title="Remove reference line"
            class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded text-gray-400 dark:text-neutral-500 hover:bg-rose-50 dark:hover:bg-rose-950/40 hover:text-rose-500 dark:hover:text-rose-400 transition-colors"
            @click="removeReferenceLine(ri)">
            <Trash2 class="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </StyleSection>

    <!-- 6. Reference Bands -->
    <StyleSection v-if="hasAxes" title="Reference Bands">
      <template #action>
          <button v-if="editMode" type="button"
            class="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-200"
            @click.stop.prevent="addReferenceBand()">+ Add</button>
      </template>
      <div v-if="!localOpts.referenceBands?.length" class="text-sm text-gray-400 dark:text-neutral-500">No reference bands.</div>
      <div v-for="(rb, rbi) in (localOpts.referenceBands ?? [])" :key="rb.id ?? rbi"
        class="rounded border border-gray-100 dark:border-neutral-800 p-2.5 space-y-2">
        <div class="grid grid-cols-2 gap-2">
          <input :value="rb.from" type="number" placeholder="From" :disabled="!editMode"
            class="w-full min-w-0 rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @input="setRefBandProp(rbi, 'from', +($event.target as HTMLInputElement).value)" />
          <input :value="rb.to" type="number" placeholder="To" :disabled="!editMode"
            class="w-full min-w-0 rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @input="setRefBandProp(rbi, 'to', +($event.target as HTMLInputElement).value)" />
        </div>
        <div class="flex items-center gap-2">
          <input :value="rb.label ?? ''" type="text" placeholder="Label" :disabled="!editMode"
            class="flex-1 min-w-0 rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @input="setRefBandProp(rbi, 'label', ($event.target as HTMLInputElement).value)" />
          <ColorPickerPopover :model-value="rb.color" :disabled="!editMode"
            @update:model-value="setRefBandProp(rbi, 'color', $event)" />
          <button v-if="editMode" type="button" title="Remove reference band"
            class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded text-gray-400 dark:text-neutral-500 hover:bg-rose-50 dark:hover:bg-rose-950/40 hover:text-rose-500 dark:hover:text-rose-400 transition-colors"
            @click="removeReferenceBand(rbi)">
            <Trash2 class="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </StyleSection>

    <!-- 7. Axes -->
    <StyleSection v-if="hasAxes" title="Axes" body-class="space-y-3">
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Reverse X-axis</span>
        <button type="button" role="switch" :aria-checked="!!localOpts.reverseXAxis" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.reverseXAxis ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
          @click="editMode && toggle('reverseXAxis')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.reverseXAxis ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Reverse Y-axis</span>
        <button type="button" role="switch" :aria-checked="!!localOpts.reverseYAxis" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.reverseYAxis ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
          @click="editMode && toggle('reverseYAxis')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.reverseYAxis ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>

      <!-- Left Y-axis -->
      <div class="space-y-2 pt-1">
        <p class="text-sm font-medium text-gray-500 dark:text-neutral-400">Left Y-axis</p>
        <div class="space-y-1">
          <label class="text-sm text-gray-700 dark:text-neutral-200">Title</label>
          <input :value="localOpts.yAxisLeft?.title ?? ''" type="text" placeholder="Axis title…" :disabled="!editMode"
            class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @input="setAxisProp('yAxisLeft', 'title', ($event.target as HTMLInputElement).value); setAxisProp('yAxisLeft', 'showTitle', true)" />
        </div>
        <div class="flex gap-2">
          <div class="flex-1 space-y-1">
            <label class="text-sm text-gray-700 dark:text-neutral-200">Min</label>
            <input :value="localOpts.yAxisLeft?.min ?? ''" type="number" placeholder="Auto" :disabled="!editMode"
              class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @input="setAxisProp('yAxisLeft', 'min', ($event.target as HTMLInputElement).value ? +($event.target as HTMLInputElement).value : undefined)" />
          </div>
          <div class="flex-1 space-y-1">
            <label class="text-sm text-gray-700 dark:text-neutral-200">Max</label>
            <input :value="localOpts.yAxisLeft?.max ?? ''" type="number" placeholder="Auto" :disabled="!editMode"
              class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @input="setAxisProp('yAxisLeft', 'max', ($event.target as HTMLInputElement).value ? +($event.target as HTMLInputElement).value : undefined)" />
          </div>
        </div>
        <div class="flex items-center justify-between py-0.5">
          <span class="text-sm text-gray-700 dark:text-neutral-200">Log scale</span>
          <button type="button" role="switch" :aria-checked="!!(localOpts.yAxisLeft?.logScale)" :disabled="!editMode"
            class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="localOpts.yAxisLeft?.logScale ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
            @click="editMode && setAxisProp('yAxisLeft', 'logScale', !localOpts.yAxisLeft?.logScale)">
            <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
              :class="localOpts.yAxisLeft?.logScale ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
          </button>
        </div>
      </div>

      <!-- Right Y-axis (only when multi-series) -->
      <div v-if="hasRightAxis" class="space-y-2 pt-1">
        <p class="text-sm font-medium text-gray-500 dark:text-neutral-400">Right Y-axis</p>
        <div class="space-y-1">
          <label class="text-sm text-gray-700 dark:text-neutral-200">Title</label>
          <input :value="localOpts.yAxisRight?.title ?? ''" type="text" placeholder="Axis title…" :disabled="!editMode"
            class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @input="setAxisProp('yAxisRight', 'title', ($event.target as HTMLInputElement).value); setAxisProp('yAxisRight', 'showTitle', true)" />
        </div>
        <div class="flex gap-2">
          <div class="flex-1 space-y-1">
            <label class="text-sm text-gray-700 dark:text-neutral-200">Min</label>
            <input :value="localOpts.yAxisRight?.min ?? ''" type="number" placeholder="Auto" :disabled="!editMode"
              class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @input="setAxisProp('yAxisRight', 'min', ($event.target as HTMLInputElement).value ? +($event.target as HTMLInputElement).value : undefined)" />
          </div>
          <div class="flex-1 space-y-1">
            <label class="text-sm text-gray-700 dark:text-neutral-200">Max</label>
            <input :value="localOpts.yAxisRight?.max ?? ''" type="number" placeholder="Auto" :disabled="!editMode"
              class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
              @input="setAxisProp('yAxisRight', 'max', ($event.target as HTMLInputElement).value ? +($event.target as HTMLInputElement).value : undefined)" />
          </div>
        </div>
        <div class="flex items-center justify-between py-0.5">
          <span class="text-sm text-gray-700 dark:text-neutral-200">Align both to 0</span>
          <button type="button" role="switch" :aria-checked="!!localOpts.alignBothAxesToZero" :disabled="!editMode"
            class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="localOpts.alignBothAxesToZero ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
            @click="editMode && toggle('alignBothAxesToZero')">
            <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
              :class="localOpts.alignBothAxesToZero ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
          </button>
        </div>
      </div>

      <!-- X-axis title -->
      <div class="space-y-1">
        <label class="text-sm text-gray-700 dark:text-neutral-200">X-axis title</label>
        <input :value="localOpts.xAxis?.title ?? ''" type="text" placeholder="X axis label…" :disabled="!editMode"
          class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
          @input="setAxisProp('xAxis', 'title', ($event.target as HTMLInputElement).value); setAxisProp('xAxis', 'showTitle', true)" />
      </div>
    </StyleSection>

    <!-- 8. Grid -->
    <StyleSection v-if="hasAxes" title="Grid">
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Show X-axis grid lines</span>
        <button type="button" role="switch" :aria-checked="localOpts.showXGridLines !== false" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.showXGridLines !== false ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
          @click="editMode && toggle('showXGridLines')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.showXGridLines !== false ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Show Y-axis grid lines</span>
        <button type="button" role="switch" :aria-checked="localOpts.showYGridLines !== false" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.showYGridLines !== false ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
          @click="editMode && toggle('showYGridLines')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.showYGridLines !== false ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <div class="flex items-center justify-between gap-2">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Grid line color</span>
        <ColorPickerPopover v-model="localOpts.gridLineColor" :disabled="!editMode" @update:model-value="emitUpdate()" />
      </div>
      <div class="space-y-1">
        <label class="text-sm text-gray-700 dark:text-neutral-200">Grid line style</label>
        <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
          <button v-for="opt in lineStyleOptions" :key="opt.value" type="button" :disabled="!editMode"
            class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localOpts.gridLineStyle ?? 'solid') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
            @click="editMode && setOpt('gridLineStyle', opt.value)">{{ opt.label }}</button>
        </div>
      </div>
    </StyleSection>

    <!-- 9. Legend -->
    <StyleSection v-if="isStandardChart" title="Legend">
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Show legend</span>
        <button type="button" role="switch" :aria-checked="localOpts.showLegend !== false" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.showLegend !== false ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
          @click="editMode && toggle('showLegend')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.showLegend !== false ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <template v-if="localOpts.showLegend !== false">
        <div class="space-y-1">
          <label class="text-sm text-gray-700 dark:text-neutral-200">Position</label>
          <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
            <button v-for="opt in legendPositionOptions" :key="opt.value" type="button" :disabled="!editMode"
              class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="(localOpts.legendPosition ?? 'top') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
              @click="editMode && setOpt('legendPosition', opt.value)">{{ opt.label }}</button>
          </div>
        </div>
        <div class="space-y-1">
          <label class="text-sm text-gray-700 dark:text-neutral-200">Alignment</label>
          <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
            <button v-for="opt in [{ value: 'start', label: 'Start' }, { value: 'center', label: 'Center' }, { value: 'end', label: 'End' }]" :key="opt.value"
              type="button" :disabled="!editMode"
              class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="(localOpts.legendAlignment ?? 'center') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
              @click="editMode && setOpt('legendAlignment', opt.value)">{{ opt.label }}</button>
          </div>
        </div>
        <div class="flex items-center justify-between gap-2">
          <span class="text-sm text-gray-700 dark:text-neutral-200">Family</span>
          <select v-model="localOpts.legendFontFamily" :disabled="!editMode"
            class="rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @change="emitUpdate()">
            <option value="system">System</option>
            <option value="sans">Sans-serif</option>
            <option value="serif">Serif</option>
            <option value="mono">Monospace</option>
          </select>
        </div>
        <div class="space-y-1.5">
          <label class="text-sm text-gray-700 dark:text-neutral-200">Size</label>
          <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
            <button
              v-for="opt in fontSizeOptions"
              :key="opt.value"
              type="button"
              :disabled="!editMode"
              class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="(localOpts.legendFontSize ?? 'sm') === opt.value
                ? 'bg-indigo-600 text-white'
                : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
              @click="editMode && setOpt('legendFontSize', opt.value)"
            >{{ opt.label }}</button>
          </div>
        </div>
        <div class="flex items-center justify-between gap-2">
          <span class="text-sm text-gray-700 dark:text-neutral-200">Color</span>
          <ColorPickerPopover v-model="localOpts.legendFontColor" :disabled="!editMode" @update:model-value="emitUpdate()" />
        </div>
      </template>
    </StyleSection>

    <!-- Font (base — applies to legend, axis labels & title unless overridden per-element) -->
    <StyleSection title="Font" body-class="space-y-3">
      <div class="flex items-center justify-between gap-2">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Family</span>
        <select v-model="localOpts.fontFamily" :disabled="!editMode"
          class="rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
          @change="emitUpdate()">
          <option value="system">System</option>
          <option value="sans">Sans-serif</option>
          <option value="serif">Serif</option>
          <option value="mono">Monospace</option>
        </select>
      </div>
      <div class="space-y-1.5">
        <label class="text-sm text-gray-700 dark:text-neutral-200">Size</label>
        <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
          <button
            v-for="opt in fontSizeOptions"
            :key="opt.value"
            type="button"
            :disabled="!editMode"
            class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localOpts.fontSize ?? 'sm') === opt.value
              ? 'bg-indigo-600 text-white'
              : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
            @click="editMode && setOpt('fontSize', opt.value)"
          >{{ opt.label }}</button>
        </div>
      </div>
      <div class="flex items-center justify-between">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Color</span>
        <ColorPickerPopover v-model="localOpts.fontColor" :disabled="!editMode" @update:model-value="emitUpdate()" />
      </div>
    </StyleSection>

    <!-- 10. Background & border -->
    <StyleSection title="Background & Border" body-class="space-y-3">
      <div class="flex items-center justify-between gap-2">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Background</span>
        <ColorPickerPopover v-model="localOpts.backgroundColor" :disabled="!editMode" @update:model-value="emitUpdate()" />
      </div>
      <div class="flex items-center justify-between gap-2">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Opacity</span>
        <div class="flex items-center gap-2">
          <input v-model.number="localOpts.opacity" type="range" min="0" max="100" step="1"
            :disabled="!editMode" class="w-24 accent-indigo-600" @input="emitUpdate()" />
          <span class="text-sm text-gray-500 dark:text-neutral-400 w-8 text-right">{{ localOpts.opacity ?? 100 }}%</span>
        </div>
      </div>
      <div class="space-y-1">
        <label class="text-sm text-gray-700 dark:text-neutral-200">Border style</label>
        <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
          <button v-for="opt in borderStyleOptions" :key="opt.value" type="button" :disabled="!editMode"
            class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localOpts.borderStyle ?? 'none') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
            @click="editMode && setOpt('borderStyle', opt.value)">{{ opt.label }}</button>
        </div>
      </div>
      <template v-if="localOpts.borderStyle && localOpts.borderStyle !== 'none'">
        <div class="flex items-center justify-between gap-2">
          <span class="text-sm text-gray-700 dark:text-neutral-200">Border color</span>
          <ColorPickerPopover v-model="localOpts.borderColor" :disabled="!editMode" @update:model-value="emitUpdate()" />
        </div>
        <div class="flex items-center justify-between gap-2">
          <span class="text-sm text-gray-700 dark:text-neutral-200">Border width</span>
          <div class="flex items-center gap-2">
            <input v-model.number="localOpts.borderWidth" type="range" min="0" max="5" step="1"
              :disabled="!editMode" class="w-24 accent-indigo-600" @input="emitUpdate()" />
            <span class="text-sm text-gray-500 dark:text-neutral-400 w-4">{{ localOpts.borderWidth ?? 1 }}</span>
          </div>
        </div>
      </template>
      <div class="flex items-center justify-between gap-2">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Border radius</span>
        <div class="flex items-center gap-2">
          <input v-model.number="localOpts.borderRadius" type="range" min="0" max="16" step="1"
            :disabled="!editMode" class="w-24 accent-indigo-600" @input="emitUpdate()" />
          <span class="text-sm text-gray-500 dark:text-neutral-400 w-4">{{ localOpts.borderRadius ?? 0 }}</span>
        </div>
      </div>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Border shadow</span>
        <button type="button" role="switch" :aria-checked="!!localOpts.addBorderShadow" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.addBorderShadow ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
          @click="editMode && toggle('addBorderShadow')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.addBorderShadow ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
    </StyleSection>

  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Trash2, ChevronDown } from 'lucide-vue-next'
import ColorPickerPopover from './ColorPickerPopover.vue'
import StyleSection from './StyleSection.vue'
import { FONT_SIZE_OPTIONS } from './styleOptions'
import { DEFAULT_PALETTE } from '~/composables/useChart'
import type { WidgetConfig, ChartWidgetConfig } from '~/types/dashboard'
import type { ChartOptions, DatasetConfig, ChartAxisConfig, ReferenceLine, ReferenceBand } from '~/types/chart'
import { DATASET_STYLE_KEYS } from '~/utils/widgetMerge'

const props = defineProps<{
  modelValue: WidgetConfig
  editMode: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WidgetConfig]
}>()

const chartConfig = computed(() => props.modelValue.config as ChartWidgetConfig)

const _rawOpts: ChartOptions = JSON.parse(JSON.stringify(chartConfig.value.options ?? {}))
// Normalize xl → lg for the three font-size fields (no segmented button for xl)
const _normFontSize = (v?: string) => (v === 'xl' ? 'lg' : v) as ChartOptions['fontSize']
if (_rawOpts.fontSize === 'xl') _rawOpts.fontSize = _normFontSize('xl')
if ((_rawOpts as any).titleFontSize === 'xl') (_rawOpts as any).titleFontSize = 'lg'
if ((_rawOpts as any).legendFontSize === 'xl') (_rawOpts as any).legendFontSize = 'lg'
// Round values default ON — reflect the rendered default in the toggle.
if (_rawOpts.roundValues === undefined) _rawOpts.roundValues = true
const localOpts = ref<ChartOptions>(_rawOpts)
const localDatasets = ref<DatasetConfig[]>(
  (JSON.parse(JSON.stringify(chartConfig.value.data?.datasets ?? [])) as DatasetConfig[])
    // Data labels default ON, except line/area series default OFF — mirror the
    // rendered default (useChart.ts) so the toggle reflects what's drawn.
    .map(ds => {
      const t = (ds as any).seriesType ?? chartConfig.value.type
      const isLine = t === 'line' || t === 'area'
      return { ...ds, showDataLabels: ds.showDataLabels ?? !isLine }
    }),
)
const localTitle = ref(chartConfig.value.title ?? '')

// Track which series panels are expanded — all open by default so every
// per-series control (e.g. "Show data labels") is visible on multi-metric charts.
const expandedSeries = ref<Set<number>>(new Set(localDatasets.value.map((_, i) => i)))

function toggleSeriesExpanded(i: number) {
  if (expandedSeries.value.has(i)) expandedSeries.value.delete(i)
  else expandedSeries.value.add(i)
}

// Re-sync datasets when the number of datasets changes externally
watch(
  () => chartConfig.value.data?.datasets?.length,
  (newLen, oldLen) => {
    if (newLen !== oldLen) {
      // Merge style properties from localDatasets into freshly-loaded datasets
      const fresh = JSON.parse(JSON.stringify(chartConfig.value.data?.datasets ?? []))
      localDatasets.value = fresh.map((ds: DatasetConfig, i: number) => ({
        ...ds,
        ...(localDatasets.value[i] ? {
          seriesType: localDatasets.value[i].seriesType,
          lineWeight: localDatasets.value[i].lineWeight,
          lineStyle: localDatasets.value[i].lineStyle,
          showPoints: localDatasets.value[i].showPoints,
          stepped: localDatasets.value[i].stepped,
          gradient: localDatasets.value[i].gradient,
          cumulative: localDatasets.value[i].cumulative,
          showDataLabels: localDatasets.value[i].showDataLabels,
          yAxisID: localDatasets.value[i].yAxisID,
          trendline: localDatasets.value[i].trendline,
          borderColor: localDatasets.value[i].borderColor,
          backgroundColor: localDatasets.value[i].backgroundColor,
        } : {}),
      }))
    }
  }
)

const hasRightAxis = computed(() => localDatasets.value.some(ds => ds.yAxisID === 'right'))

/** Color shown in the series-header dot: explicit style, else the palette color
 *  the renderer would assign by index. */
function seriesSwatch(ds: DatasetConfig, i: number): string {
  const bg = Array.isArray(ds.backgroundColor) ? ds.backgroundColor[0] : ds.backgroundColor
  return (ds.borderColor as string) || (bg as string) || DEFAULT_PALETTE[i % DEFAULT_PALETTE.length]
}

const isPie = computed(() => chartConfig.value.type === 'pie' || chartConfig.value.type === 'doughnut')
const isFunnel = computed(() => chartConfig.value.type === 'funnel')
const isTimeline = computed(() => chartConfig.value.type === 'timeline')
// Funnel/timeline render with custom components, so the Chart.js-oriented
// sections (series, axes, grid, legend, reference lines…) don't apply to them.
const isStandardChart = computed(() => !isFunnel.value && !isTimeline.value)
// Pie/doughnut have no cartesian axes — axis-anchored sections do nothing there.
const hasAxes = computed(() => isStandardChart.value && !isPie.value)

const sliceLabelOptions = [
  { value: 'none', label: 'None' },
  { value: 'percentage', label: 'Percentage' },
  { value: 'value', label: 'Value' },
  { value: 'label', label: 'Label' },
]

// Infer default series type from chart type
const defaultSeriesType = computed(() => {
  const t = chartConfig.value.type
  return (t === 'bar') ? 'bars' : 'line'
})

// ── Static option lists ───────────────────────────────────────────────────────

const lineStyleOptions = [
  { value: 'solid', label: 'Solid' },
  { value: 'dashed', label: 'Dashed' },
  { value: 'dotted', label: 'Dotted' },
]

const seriesTypeOptions = [
  { value: 'line', label: 'Line' },
  { value: 'bars', label: 'Bars' },
]

const missingDataOptions = [
  { value: 'lineToZero', label: 'Zero', hint: 'Treat missing dates as 0' },
  { value: 'breaks', label: 'Break', hint: 'Leave a gap in the line where data is missing' },
  { value: 'linearInterpolation', label: 'Interpolate', hint: 'Connect across the gap with a straight line' },
]

const legendPositionOptions = [
  { value: 'top', label: 'Top' },
  { value: 'bottom', label: 'Bottom' },
  { value: 'left', label: 'Left' },
  { value: 'right', label: 'Right' },
]

const borderStyleOptions = [
  { value: 'none', label: 'None' },
  { value: 'solid', label: 'Solid' },
  { value: 'dashed', label: 'Dashed' },
  { value: 'dotted', label: 'Dotted' },
]

const fontSizeOptions = FONT_SIZE_OPTIONS

// ── Mutation helpers ──────────────────────────────────────────────────────────

function toggle(key: keyof ChartOptions) {
  (localOpts.value as any)[key] = !((localOpts.value as any)[key])
  emitUpdate()
}

function setOpt(key: keyof ChartOptions, value: any) {
  (localOpts.value as any)[key] = value
  emitUpdate()
}

function setDatasetProp(i: number, key: keyof DatasetConfig, value: any) {
  ;(localDatasets.value[i] as any)[key] = value
  emitUpdate()
}

function setDatasetColor(i: number, color: string | undefined) {
  localDatasets.value[i].borderColor = color
  // Set bg to the same color with alpha for area/gradient
  localDatasets.value[i].backgroundColor = color ? `${color}33` : undefined
  emitUpdate()
}

function setTrendlineType(i: number, type: string) {
  if (!localDatasets.value[i].trendline) {
    localDatasets.value[i].trendline = { type: type as any }
  } else {
    localDatasets.value[i].trendline!.type = type as any
  }
  emitUpdate()
}

function setTrendlineProp(i: number, key: string, value: any) {
  if (!localDatasets.value[i].trendline) {
    localDatasets.value[i].trendline = { type: 'none' }
  }
  ;(localDatasets.value[i].trendline as any)[key] = value
  emitUpdate()
}

function setAxisProp(axis: 'xAxis' | 'yAxisLeft' | 'yAxisRight', key: keyof ChartAxisConfig, value: any) {
  if (!localOpts.value[axis]) localOpts.value[axis] = {}
  ;(localOpts.value[axis] as any)[key] = value
  emitUpdate()
}

function setRefLineProp(i: number, key: keyof ReferenceLine, value: any) {
  if (!localOpts.value.referenceLines) return
  ;(localOpts.value.referenceLines[i] as any)[key] = value
  emitUpdate()
}

function setRefBandProp(i: number, key: keyof ReferenceBand, value: any) {
  if (!localOpts.value.referenceBands) return
  ;(localOpts.value.referenceBands[i] as any)[key] = value
  emitUpdate()
}

function addReferenceLine() {
  if (!localOpts.value.referenceLines) localOpts.value.referenceLines = []
  localOpts.value.referenceLines.push({ id: `rl-${Date.now()}`, value: 0, style: 'dashed' })
  emitUpdate()
}

function removeReferenceLine(i: number) {
  localOpts.value.referenceLines?.splice(i, 1)
  emitUpdate()
}

function addReferenceBand() {
  if (!localOpts.value.referenceBands) localOpts.value.referenceBands = []
  localOpts.value.referenceBands.push({ id: `rb-${Date.now()}`, from: 0, to: 0 })
  emitUpdate()
}

function removeReferenceBand(i: number) {
  localOpts.value.referenceBands?.splice(i, 1)
  emitUpdate()
}

function emitUpdate() {
  emit('update:modelValue', buildConfig())
}

function buildConfig(): WidgetConfig {
  // Use live datasets (always fresh after Test Query) as base; overlay only style
  // fields from localDatasets so numeric data arrays are never wiped by stale snapshots.
  const liveDatasets = chartConfig.value.data?.datasets ?? []
  const mergedDatasets = liveDatasets.map((live, i) => {
    const local = localDatasets.value[i]
    if (!local) return live
    const merged: any = { ...live }
    for (const k of DATASET_STYLE_KEYS) {
      if (k in (local as any)) merged[k] = (local as any)[k]
    }
    return merged
  })
  return {
    type: 'chart',
    config: {
      ...chartConfig.value,
      title: localTitle.value || chartConfig.value.title,
      options: localOpts.value,
      data: {
        ...chartConfig.value.data,
        datasets: mergedDatasets,
      },
    },
  }
}
</script>
