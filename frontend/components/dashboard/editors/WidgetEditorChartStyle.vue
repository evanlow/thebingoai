<template>
  <div class="h-full overflow-y-auto p-5 space-y-5 [&>*+*]:border-t [&>*+*]:border-gray-200 [&>*+*]:pt-5">

    <!-- 1. Title -->
    <div class="space-y-2">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Title</h3>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Show title</span>
        <button type="button" role="switch" :aria-checked="!!localOpts.showTitle" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.showTitle ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('showTitle')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.showTitle ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <template v-if="localOpts.showTitle">
        <div class="space-y-1">
          <label class="text-xs text-gray-700">Title text</label>
          <input v-model="localTitle" type="text" placeholder="Chart title…" :readonly="!editMode"
            class="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300"
            :class="!editMode ? 'cursor-default bg-gray-50' : ''"
            @input="emitUpdate()" />
        </div>
        <div class="flex gap-3">
          <div class="flex-1 space-y-1">
            <label class="text-xs text-gray-700">Position</label>
            <div class="flex rounded border border-gray-200 overflow-hidden">
              <button v-for="opt in [{ value: 'top', label: 'Top' }, { value: 'bottom', label: 'Bottom' }]" :key="opt.value"
                type="button" :disabled="!editMode"
                class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="(localOpts.titlePosition ?? 'top') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
                @click="editMode && setOpt('titlePosition', opt.value)">{{ opt.label }}</button>
            </div>
          </div>
          <div class="flex-1 space-y-1">
            <label class="text-xs text-gray-700">Align</label>
            <div class="flex rounded border border-gray-200 overflow-hidden">
              <button v-for="opt in [{ value: 'left', label: 'L' }, { value: 'center', label: 'C' }, { value: 'right', label: 'R' }]" :key="opt.value"
                type="button" :disabled="!editMode"
                class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="(localOpts.titleAlignment ?? 'center') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
                @click="editMode && setOpt('titleAlignment', opt.value)">{{ opt.label }}</button>
            </div>
          </div>
        </div>
        <div class="flex items-center justify-between gap-2">
          <span class="text-xs text-gray-700">Family</span>
          <select v-model="localOpts.titleFontFamily" :disabled="!editMode"
            class="rounded border border-gray-200 bg-white px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50"
            @change="emitUpdate()">
            <option value="system">System</option>
            <option value="sans">Sans-serif</option>
            <option value="serif">Serif</option>
            <option value="mono">Monospace</option>
          </select>
        </div>
        <div class="space-y-1.5">
          <label class="text-xs text-gray-700">Size</label>
          <div class="flex rounded border border-gray-200 overflow-hidden">
            <button
              v-for="opt in fontSizeOptions"
              :key="opt.value"
              type="button"
              :disabled="!editMode"
              class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="(localOpts.titleFontSize ?? 'sm') === opt.value
                ? 'bg-indigo-600 text-white'
                : 'bg-white text-gray-500 hover:bg-gray-50'"
              @click="editMode && setOpt('titleFontSize', opt.value)"
            >{{ opt.label }}</button>
          </div>
        </div>
        <div class="flex items-center justify-between gap-2">
          <span class="text-xs text-gray-700">Color</span>
          <ColorPickerPopover v-model="localOpts.titleFontColor" :disabled="!editMode" @update:model-value="emitUpdate()" />
        </div>
      </template>
    </div>

    <!-- 2. Series -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Series</h3>
      <p v-if="!localDatasets.length" class="text-xs text-gray-400">No datasets yet. Connect a data source first.</p>
      <div v-for="(ds, i) in localDatasets" :key="i" class="rounded-lg border border-gray-100 p-3 space-y-2.5">
        <!-- Series header -->
        <div class="flex items-center justify-between gap-2">
          <span class="text-xs font-medium text-gray-700 truncate">{{ ds.label || `Series ${i + 1}` }}</span>
          <button type="button" class="text-[11px] text-gray-400 hover:text-gray-600"
            @click="toggleSeriesExpanded(i)">{{ expandedSeries.has(i) ? 'Collapse' : 'Expand' }}</button>
        </div>

        <template v-if="expandedSeries.has(i)">
          <!-- Series type (combo) -->
          <div class="space-y-1">
            <label class="text-xs text-gray-700">Series type</label>
            <div class="flex rounded border border-gray-200 overflow-hidden">
              <button v-for="opt in seriesTypeOptions" :key="opt.value" type="button" :disabled="!editMode"
                class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="(ds.seriesType ?? defaultSeriesType) === opt.value ? 'bg-indigo-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
                @click="editMode && setDatasetProp(i, 'seriesType', opt.value)">{{ opt.label }}</button>
            </div>
          </div>

          <!-- Color -->
          <div class="flex items-center justify-between gap-2">
            <span class="text-xs text-gray-700">Color</span>
            <ColorPickerPopover :model-value="ds.borderColor as string | undefined" :disabled="!editMode"
              @update:model-value="setDatasetColor(i, $event)" />
          </div>

          <!-- Line-only options -->
          <template v-if="(ds.seriesType ?? defaultSeriesType) === 'line'">
            <div class="space-y-1">
              <label class="text-xs text-gray-700">Line style</label>
              <div class="flex rounded border border-gray-200 overflow-hidden">
                <button v-for="opt in lineStyleOptions" :key="opt.value" type="button" :disabled="!editMode"
                  class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
                  :class="(ds.lineStyle ?? 'solid') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
                  @click="editMode && setDatasetProp(i, 'lineStyle', opt.value)">{{ opt.label }}</button>
              </div>
            </div>
            <div class="flex items-center justify-between gap-2">
              <span class="text-xs text-gray-700">Line weight</span>
              <input v-model.number="localDatasets[i].lineWeight" type="range" min="1" max="6" step="1"
                :disabled="!editMode" class="w-24 accent-indigo-600" @input="emitUpdate()" />
              <span class="text-xs text-gray-500 w-4">{{ ds.lineWeight ?? 2 }}</span>
            </div>
            <div class="flex items-center justify-between py-0.5">
              <span class="text-xs text-gray-700">Smooth</span>
              <button type="button" role="switch" :aria-checked="(ds.tension ?? 0.4) > 0" :disabled="!editMode"
                class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="(ds.tension ?? 0.4) > 0 ? 'bg-indigo-600' : 'bg-gray-200'"
                @click="editMode && setDatasetProp(i, 'tension', (ds.tension ?? 0.4) > 0 ? 0 : 0.4)">
                <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
                  :class="(ds.tension ?? 0.4) > 0 ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
              </button>
            </div>
            <div class="flex items-center justify-between py-0.5">
              <span class="text-xs text-gray-700">Show points</span>
              <button type="button" role="switch" :aria-checked="ds.showPoints !== false" :disabled="!editMode"
                class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="ds.showPoints !== false ? 'bg-indigo-600' : 'bg-gray-200'"
                @click="editMode && setDatasetProp(i, 'showPoints', !(ds.showPoints !== false))">
                <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
                  :class="ds.showPoints !== false ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
              </button>
            </div>
            <div class="flex items-center justify-between py-0.5">
              <span class="text-xs text-gray-700">Stepped lines</span>
              <button type="button" role="switch" :aria-checked="!!ds.stepped" :disabled="!editMode"
                class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="ds.stepped ? 'bg-indigo-600' : 'bg-gray-200'"
                @click="editMode && setDatasetProp(i, 'stepped', !ds.stepped)">
                <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
                  :class="ds.stepped ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
              </button>
            </div>
            <div class="flex items-center justify-between py-0.5">
              <span class="text-xs text-gray-700">Gradient fill</span>
              <button type="button" role="switch" :aria-checked="!!ds.gradient" :disabled="!editMode"
                class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="ds.gradient ? 'bg-indigo-600' : 'bg-gray-200'"
                @click="editMode && setDatasetProp(i, 'gradient', !ds.gradient)">
                <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
                  :class="ds.gradient ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
              </button>
            </div>
          </template>

          <!-- Cumulative -->
          <div class="flex items-center justify-between py-0.5">
            <span class="text-xs text-gray-700">Cumulative</span>
            <button type="button" role="switch" :aria-checked="!!ds.cumulative" :disabled="!editMode"
              class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="ds.cumulative ? 'bg-indigo-600' : 'bg-gray-200'"
              @click="editMode && setDatasetProp(i, 'cumulative', !ds.cumulative)">
              <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
                :class="ds.cumulative ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
            </button>
          </div>

          <!-- Show data labels (hidden for pie — use Slice label in General instead) -->
          <div v-if="!isPie" class="flex items-center justify-between py-0.5">
            <span class="text-xs text-gray-700">Show data labels</span>
            <button type="button" role="switch" :aria-checked="!!ds.showDataLabels" :disabled="!editMode"
              class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="ds.showDataLabels ? 'bg-indigo-600' : 'bg-gray-200'"
              @click="editMode && setDatasetProp(i, 'showDataLabels', !ds.showDataLabels)">
              <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
                :class="ds.showDataLabels ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
            </button>
          </div>

          <!-- Y-axis assignment -->
          <div v-if="localDatasets.length > 1" class="space-y-1">
            <label class="text-xs text-gray-700">Y-axis</label>
            <div class="flex rounded border border-gray-200 overflow-hidden">
              <button v-for="opt in [{ value: 'left', label: 'Left' }, { value: 'right', label: 'Right' }]" :key="opt.value"
                type="button" :disabled="!editMode"
                class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
                :class="(ds.yAxisID ?? 'left') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
                @click="editMode && setDatasetProp(i, 'yAxisID', opt.value)">{{ opt.label }}</button>
            </div>
          </div>

          <!-- Trendline -->
          <div class="space-y-1.5 pt-1 border-t border-gray-100">
            <label class="text-xs font-medium text-gray-600">Trendline</label>
            <select :value="ds.trendline?.type ?? 'none'" :disabled="!editMode"
              class="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50"
              @change="setTrendlineType(i, ($event.target as HTMLSelectElement).value)">
              <option value="none">None</option>
              <option value="linear">Linear</option>
              <option value="movingAverage">Moving average</option>
              <option value="exponential">Exponential</option>
              <option value="polynomial" disabled>Polynomial (coming soon)</option>
            </select>
            <template v-if="ds.trendline?.type && ds.trendline.type !== 'none'">
              <div v-if="ds.trendline.type === 'movingAverage'" class="flex items-center justify-between gap-2">
                <span class="text-xs text-gray-700">Period</span>
                <input :value="ds.trendline.period ?? 3" type="number" min="2" max="50" :disabled="!editMode"
                  class="w-16 rounded border border-gray-200 bg-white px-2 py-1 text-xs text-center text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50"
                  @input="setTrendlineProp(i, 'period', +($event.target as HTMLInputElement).value)" />
              </div>
              <div class="flex items-center justify-between gap-2">
                <span class="text-xs text-gray-700">Color</span>
                <ColorPickerPopover :model-value="ds.trendline.color" :disabled="!editMode"
                  @update:model-value="setTrendlineProp(i, 'color', $event)" />
              </div>
              <div class="space-y-1">
                <label class="text-xs text-gray-700">Style</label>
                <div class="flex rounded border border-gray-200 overflow-hidden">
                  <button v-for="opt in lineStyleOptions" :key="opt.value" type="button" :disabled="!editMode"
                    class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
                    :class="(ds.trendline.style ?? 'dashed') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
                    @click="editMode && setTrendlineProp(i, 'style', opt.value)">{{ opt.label }}</button>
                </div>
              </div>
            </template>
          </div>
        </template>
      </div>
    </div>

    <!-- 3. General -->
    <div class="space-y-2">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">General</h3>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Show legend</span>
        <button type="button" role="switch" :aria-checked="localOpts.showLegend !== false" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.showLegend !== false ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('showLegend')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.showLegend !== false ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Show tooltips</span>
        <button type="button" role="switch" :aria-checked="localOpts.showTooltips !== false" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.showTooltips !== false ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('showTooltips')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.showTooltips !== false ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <!-- Pie/doughnut: slice label type (Data Studio parity) -->
      <div v-if="isPie" class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Slice label</span>
        <select :value="localOpts.sliceLabel ?? 'percentage'" :disabled="!editMode"
          class="w-32 rounded-lg border border-gray-200 bg-white px-2 py-1 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:bg-gray-50"
          @change="setOpt('sliceLabel', ($event.target as HTMLSelectElement).value)">
          <option v-for="opt in sliceLabelOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
      <!-- Non-pie: show values toggle -->
      <div v-else class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Show values</span>
        <button type="button" role="switch" :aria-checked="!!localOpts.showValues" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.showValues ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('showValues')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.showValues ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <!-- Round Values: independent of Show values — applies to axes, tooltips, and labels -->
      <div class="flex items-center justify-between py-1">
        <div>
          <span class="text-sm text-gray-700">Round values</span>
          <p class="text-[11px] text-gray-400 mt-0.5">Rounds values on axes, tooltips, and labels</p>
        </div>
        <button type="button" role="switch" :aria-checked="!!localOpts.roundValues" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.roundValues ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('roundValues')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.roundValues ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <div v-if="localOpts.roundValues" class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Decimal places</span>
        <input v-model.number="localOpts.decimalPlaces" type="number" min="0" max="10" :disabled="!editMode"
          class="w-16 rounded-lg border border-gray-200 bg-white px-2 py-1 text-sm text-center text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:bg-gray-50"
          @input="emitUpdate()" />
      </div>
    </div>

    <!-- 4. Missing data (date mode only) -->
    <div v-if="chartConfig.options?.xAxisMode === 'date'" class="space-y-2">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Missing Data</h3>
      <div class="flex rounded border border-gray-200 overflow-hidden">
        <button v-for="opt in missingDataOptions" :key="opt.value" type="button" :disabled="!editMode"
          class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="(localOpts.missingData ?? 'lineToZero') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
          @click="editMode && setOpt('missingData', opt.value)">{{ opt.label }}</button>
      </div>
    </div>

    <!-- 5. Reference Lines -->
    <div class="space-y-2">
      <div class="flex items-center justify-between">
        <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Reference Lines</h3>
        <button v-if="editMode" type="button"
          class="text-[11px] font-medium text-indigo-600 hover:text-indigo-800"
          @click="addReferenceLine()">+ Add</button>
      </div>
      <div v-if="!localOpts.referenceLines?.length" class="text-[11px] text-gray-400">No reference lines.</div>
      <div v-for="(rl, ri) in (localOpts.referenceLines ?? [])" :key="rl.id ?? ri"
        class="rounded border border-gray-100 p-2.5 space-y-2">
        <div class="flex items-center gap-2">
          <input :value="rl.value" type="number" placeholder="Value" :disabled="!editMode"
            class="flex-1 rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50"
            @input="setRefLineProp(ri, 'value', +($event.target as HTMLInputElement).value)" />
          <input :value="rl.label ?? ''" type="text" placeholder="Label" :disabled="!editMode"
            class="flex-1 rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50"
            @input="setRefLineProp(ri, 'label', ($event.target as HTMLInputElement).value)" />
          <ColorPickerPopover :model-value="rl.color" :disabled="!editMode"
            @update:model-value="setRefLineProp(ri, 'color', $event)" />
          <button v-if="editMode" type="button" class="text-gray-400 hover:text-rose-500"
            @click="removeReferenceLine(ri)">✕</button>
        </div>
        <div class="flex rounded border border-gray-200 overflow-hidden">
          <button v-for="opt in lineStyleOptions" :key="opt.value" type="button" :disabled="!editMode"
            class="flex-1 py-1 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(rl.style ?? 'dashed') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
            @click="editMode && setRefLineProp(ri, 'style', opt.value)">{{ opt.label }}</button>
        </div>
      </div>
    </div>

    <!-- 6. Reference Bands -->
    <div class="space-y-2">
      <div class="flex items-center justify-between">
        <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Reference Bands</h3>
        <button v-if="editMode" type="button"
          class="text-[11px] font-medium text-indigo-600 hover:text-indigo-800"
          @click="addReferenceBand()">+ Add</button>
      </div>
      <div v-if="!localOpts.referenceBands?.length" class="text-[11px] text-gray-400">No reference bands.</div>
      <div v-for="(rb, rbi) in (localOpts.referenceBands ?? [])" :key="rb.id ?? rbi"
        class="rounded border border-gray-100 p-2.5 space-y-2">
        <div class="flex items-center gap-2">
          <input :value="rb.from" type="number" placeholder="From" :disabled="!editMode"
            class="flex-1 rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50"
            @input="setRefBandProp(rbi, 'from', +($event.target as HTMLInputElement).value)" />
          <input :value="rb.to" type="number" placeholder="To" :disabled="!editMode"
            class="flex-1 rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50"
            @input="setRefBandProp(rbi, 'to', +($event.target as HTMLInputElement).value)" />
          <input :value="rb.label ?? ''" type="text" placeholder="Label" :disabled="!editMode"
            class="flex-1 rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50"
            @input="setRefBandProp(rbi, 'label', ($event.target as HTMLInputElement).value)" />
          <ColorPickerPopover :model-value="rb.color" :disabled="!editMode"
            @update:model-value="setRefBandProp(rbi, 'color', $event)" />
          <button v-if="editMode" type="button" class="text-gray-400 hover:text-rose-500"
            @click="removeReferenceBand(rbi)">✕</button>
        </div>
      </div>
    </div>

    <!-- 7. Axes -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Axes</h3>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Reverse X-axis</span>
        <button type="button" role="switch" :aria-checked="!!localOpts.reverseXAxis" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.reverseXAxis ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('reverseXAxis')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.reverseXAxis ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Reverse Y-axis</span>
        <button type="button" role="switch" :aria-checked="!!localOpts.reverseYAxis" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.reverseYAxis ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('reverseYAxis')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.reverseYAxis ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>

      <!-- Left Y-axis -->
      <div class="space-y-2 pt-1">
        <p class="text-xs font-medium text-gray-500">Left Y-axis</p>
        <div class="space-y-1">
          <label class="text-xs text-gray-700">Title</label>
          <input :value="localOpts.yAxisLeft?.title ?? ''" type="text" placeholder="Axis title…" :disabled="!editMode"
            class="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50"
            @input="setAxisProp('yAxisLeft', 'title', ($event.target as HTMLInputElement).value); setAxisProp('yAxisLeft', 'showTitle', true)" />
        </div>
        <div class="flex gap-2">
          <div class="flex-1 space-y-1">
            <label class="text-xs text-gray-700">Min</label>
            <input :value="localOpts.yAxisLeft?.min ?? ''" type="number" placeholder="Auto" :disabled="!editMode"
              class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50"
              @input="setAxisProp('yAxisLeft', 'min', ($event.target as HTMLInputElement).value ? +($event.target as HTMLInputElement).value : undefined)" />
          </div>
          <div class="flex-1 space-y-1">
            <label class="text-xs text-gray-700">Max</label>
            <input :value="localOpts.yAxisLeft?.max ?? ''" type="number" placeholder="Auto" :disabled="!editMode"
              class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50"
              @input="setAxisProp('yAxisLeft', 'max', ($event.target as HTMLInputElement).value ? +($event.target as HTMLInputElement).value : undefined)" />
          </div>
        </div>
        <div class="flex items-center justify-between py-0.5">
          <span class="text-xs text-gray-700">Log scale</span>
          <button type="button" role="switch" :aria-checked="!!(localOpts.yAxisLeft?.logScale)" :disabled="!editMode"
            class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="localOpts.yAxisLeft?.logScale ? 'bg-indigo-600' : 'bg-gray-200'"
            @click="editMode && setAxisProp('yAxisLeft', 'logScale', !localOpts.yAxisLeft?.logScale)">
            <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
              :class="localOpts.yAxisLeft?.logScale ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
          </button>
        </div>
      </div>

      <!-- Right Y-axis (only when multi-series) -->
      <div v-if="hasRightAxis" class="space-y-2 pt-1">
        <p class="text-xs font-medium text-gray-500">Right Y-axis</p>
        <div class="space-y-1">
          <label class="text-xs text-gray-700">Title</label>
          <input :value="localOpts.yAxisRight?.title ?? ''" type="text" placeholder="Axis title…" :disabled="!editMode"
            class="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50"
            @input="setAxisProp('yAxisRight', 'title', ($event.target as HTMLInputElement).value); setAxisProp('yAxisRight', 'showTitle', true)" />
        </div>
        <div class="flex gap-2">
          <div class="flex-1 space-y-1">
            <label class="text-xs text-gray-700">Min</label>
            <input :value="localOpts.yAxisRight?.min ?? ''" type="number" placeholder="Auto" :disabled="!editMode"
              class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50"
              @input="setAxisProp('yAxisRight', 'min', ($event.target as HTMLInputElement).value ? +($event.target as HTMLInputElement).value : undefined)" />
          </div>
          <div class="flex-1 space-y-1">
            <label class="text-xs text-gray-700">Max</label>
            <input :value="localOpts.yAxisRight?.max ?? ''" type="number" placeholder="Auto" :disabled="!editMode"
              class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50"
              @input="setAxisProp('yAxisRight', 'max', ($event.target as HTMLInputElement).value ? +($event.target as HTMLInputElement).value : undefined)" />
          </div>
        </div>
        <div class="flex items-center justify-between py-0.5">
          <span class="text-xs text-gray-700">Align both to 0</span>
          <button type="button" role="switch" :aria-checked="!!localOpts.alignBothAxesToZero" :disabled="!editMode"
            class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="localOpts.alignBothAxesToZero ? 'bg-indigo-600' : 'bg-gray-200'"
            @click="editMode && toggle('alignBothAxesToZero')">
            <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
              :class="localOpts.alignBothAxesToZero ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
          </button>
        </div>
      </div>

      <!-- X-axis title -->
      <div class="space-y-1">
        <label class="text-xs text-gray-700">X-axis title</label>
        <input :value="localOpts.xAxis?.title ?? ''" type="text" placeholder="X axis label…" :disabled="!editMode"
          class="w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50"
          @input="setAxisProp('xAxis', 'title', ($event.target as HTMLInputElement).value); setAxisProp('xAxis', 'showTitle', true)" />
      </div>
    </div>

    <!-- 8. Grid -->
    <div class="space-y-2">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Grid</h3>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Show X-axis grid lines</span>
        <button type="button" role="switch" :aria-checked="localOpts.showXGridLines !== false" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.showXGridLines !== false ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('showXGridLines')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.showXGridLines !== false ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Show Y-axis grid lines</span>
        <button type="button" role="switch" :aria-checked="localOpts.showYGridLines !== false" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.showYGridLines !== false ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('showYGridLines')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.showYGridLines !== false ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <div class="flex items-center justify-between gap-2">
        <span class="text-sm text-gray-700">Grid line color</span>
        <ColorPickerPopover v-model="localOpts.gridLineColor" :disabled="!editMode" @update:model-value="emitUpdate()" />
      </div>
      <div class="space-y-1">
        <label class="text-xs text-gray-700">Grid line style</label>
        <div class="flex rounded border border-gray-200 overflow-hidden">
          <button v-for="opt in lineStyleOptions" :key="opt.value" type="button" :disabled="!editMode"
            class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localOpts.gridLineStyle ?? 'solid') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
            @click="editMode && setOpt('gridLineStyle', opt.value)">{{ opt.label }}</button>
        </div>
      </div>
    </div>

    <!-- 9. Legend -->
    <div class="space-y-2">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Legend</h3>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Show legend</span>
        <button type="button" role="switch" :aria-checked="localOpts.showLegend !== false" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.showLegend !== false ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('showLegend')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.showLegend !== false ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <template v-if="localOpts.showLegend !== false">
        <div class="space-y-1">
          <label class="text-xs text-gray-700">Position</label>
          <div class="flex rounded border border-gray-200 overflow-hidden">
            <button v-for="opt in legendPositionOptions" :key="opt.value" type="button" :disabled="!editMode"
              class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="(localOpts.legendPosition ?? 'top') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
              @click="editMode && setOpt('legendPosition', opt.value)">{{ opt.label }}</button>
          </div>
        </div>
        <div class="space-y-1">
          <label class="text-xs text-gray-700">Alignment</label>
          <div class="flex rounded border border-gray-200 overflow-hidden">
            <button v-for="opt in [{ value: 'start', label: 'Start' }, { value: 'center', label: 'Center' }, { value: 'end', label: 'End' }]" :key="opt.value"
              type="button" :disabled="!editMode"
              class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="(localOpts.legendAlignment ?? 'center') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
              @click="editMode && setOpt('legendAlignment', opt.value)">{{ opt.label }}</button>
          </div>
        </div>
        <div class="flex items-center justify-between gap-2">
          <span class="text-xs text-gray-700">Family</span>
          <select v-model="localOpts.legendFontFamily" :disabled="!editMode"
            class="rounded border border-gray-200 bg-white px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50"
            @change="emitUpdate()">
            <option value="system">System</option>
            <option value="sans">Sans-serif</option>
            <option value="serif">Serif</option>
            <option value="mono">Monospace</option>
          </select>
        </div>
        <div class="space-y-1.5">
          <label class="text-xs text-gray-700">Size</label>
          <div class="flex rounded border border-gray-200 overflow-hidden">
            <button
              v-for="opt in fontSizeOptions"
              :key="opt.value"
              type="button"
              :disabled="!editMode"
              class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
              :class="(localOpts.legendFontSize ?? 'sm') === opt.value
                ? 'bg-indigo-600 text-white'
                : 'bg-white text-gray-500 hover:bg-gray-50'"
              @click="editMode && setOpt('legendFontSize', opt.value)"
            >{{ opt.label }}</button>
          </div>
        </div>
        <div class="flex items-center justify-between gap-2">
          <span class="text-xs text-gray-700">Color</span>
          <ColorPickerPopover v-model="localOpts.legendFontColor" :disabled="!editMode" @update:model-value="emitUpdate()" />
        </div>
      </template>
    </div>

    <!-- Font (base — applies to legend, axis labels & title unless overridden per-element) -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Font</h3>
      <div class="flex items-center justify-between gap-2">
        <span class="text-xs text-gray-700">Family</span>
        <select v-model="localOpts.fontFamily" :disabled="!editMode"
          class="rounded border border-gray-200 bg-white px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50"
          @change="emitUpdate()">
          <option value="system">System</option>
          <option value="sans">Sans-serif</option>
          <option value="serif">Serif</option>
          <option value="mono">Monospace</option>
        </select>
      </div>
      <div class="space-y-1.5">
        <label class="text-xs text-gray-700">Size</label>
        <div class="flex rounded border border-gray-200 overflow-hidden">
          <button
            v-for="opt in fontSizeOptions"
            :key="opt.value"
            type="button"
            :disabled="!editMode"
            class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localOpts.fontSize ?? 'sm') === opt.value
              ? 'bg-indigo-600 text-white'
              : 'bg-white text-gray-500 hover:bg-gray-50'"
            @click="editMode && setOpt('fontSize', opt.value)"
          >{{ opt.label }}</button>
        </div>
      </div>
      <div class="flex items-center justify-between">
        <span class="text-xs text-gray-700">Color</span>
        <ColorPickerPopover v-model="localOpts.fontColor" :disabled="!editMode" @update:model-value="emitUpdate()" />
      </div>
    </div>

    <!-- 10. Background & border -->
    <div class="space-y-3">
      <h3 class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Background & Border</h3>
      <div class="flex items-center justify-between gap-2">
        <span class="text-sm text-gray-700">Background</span>
        <ColorPickerPopover v-model="localOpts.backgroundColor" :disabled="!editMode" @update:model-value="emitUpdate()" />
      </div>
      <div class="flex items-center justify-between gap-2">
        <span class="text-sm text-gray-700">Opacity</span>
        <div class="flex items-center gap-2">
          <input v-model.number="localOpts.opacity" type="range" min="0" max="100" step="1"
            :disabled="!editMode" class="w-24 accent-indigo-600" @input="emitUpdate()" />
          <span class="text-xs text-gray-500 w-8 text-right">{{ localOpts.opacity ?? 100 }}%</span>
        </div>
      </div>
      <div class="space-y-1">
        <label class="text-xs text-gray-700">Border style</label>
        <div class="flex rounded border border-gray-200 overflow-hidden">
          <button v-for="opt in borderStyleOptions" :key="opt.value" type="button" :disabled="!editMode"
            class="flex-1 py-1.5 text-[11px] font-medium transition-colors border-r border-gray-200 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
            :class="(localOpts.borderStyle ?? 'none') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
            @click="editMode && setOpt('borderStyle', opt.value)">{{ opt.label }}</button>
        </div>
      </div>
      <template v-if="localOpts.borderStyle && localOpts.borderStyle !== 'none'">
        <div class="flex items-center justify-between gap-2">
          <span class="text-sm text-gray-700">Border color</span>
          <ColorPickerPopover v-model="localOpts.borderColor" :disabled="!editMode" @update:model-value="emitUpdate()" />
        </div>
        <div class="flex items-center justify-between gap-2">
          <span class="text-sm text-gray-700">Border width</span>
          <div class="flex items-center gap-2">
            <input v-model.number="localOpts.borderWidth" type="range" min="0" max="5" step="1"
              :disabled="!editMode" class="w-24 accent-indigo-600" @input="emitUpdate()" />
            <span class="text-xs text-gray-500 w-4">{{ localOpts.borderWidth ?? 1 }}</span>
          </div>
        </div>
      </template>
      <div class="flex items-center justify-between gap-2">
        <span class="text-sm text-gray-700">Border radius</span>
        <div class="flex items-center gap-2">
          <input v-model.number="localOpts.borderRadius" type="range" min="0" max="16" step="1"
            :disabled="!editMode" class="w-24 accent-indigo-600" @input="emitUpdate()" />
          <span class="text-xs text-gray-500 w-4">{{ localOpts.borderRadius ?? 0 }}</span>
        </div>
      </div>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700">Border shadow</span>
        <button type="button" role="switch" :aria-checked="!!localOpts.addBorderShadow" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="localOpts.addBorderShadow ? 'bg-indigo-600' : 'bg-gray-200'"
          @click="editMode && toggle('addBorderShadow')">
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out mt-0.5"
            :class="localOpts.addBorderShadow ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import ColorPickerPopover from './ColorPickerPopover.vue'
import type { WidgetConfig, ChartWidgetConfig } from '~/types/dashboard'
import type { ChartOptions, DatasetConfig, ChartAxisConfig, ReferenceLine, ReferenceBand } from '~/types/chart'

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
const localOpts = ref<ChartOptions>(_rawOpts)
const localDatasets = ref<DatasetConfig[]>(JSON.parse(JSON.stringify(chartConfig.value.data?.datasets ?? [])))
const localTitle = ref(chartConfig.value.title ?? '')

// Track which series panels are expanded
const expandedSeries = ref<Set<number>>(new Set([0]))

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

const isPie = computed(() => chartConfig.value.type === 'pie' || chartConfig.value.type === 'doughnut')

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
  { value: 'lineToZero', label: 'Zero' },
  { value: 'breaks', label: 'Break' },
  { value: 'linearInterpolation', label: 'Interpolate' },
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

const fontSizeOptions = [
  { value: 'xs' as const, label: 'XS' },
  { value: 'sm' as const, label: 'S' },
  { value: 'md' as const, label: 'M' },
  { value: 'lg' as const, label: 'L' },
]

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

const DATASET_STYLE_KEYS = [
  'seriesType', 'lineWeight', 'lineStyle', 'showPoints', 'pointRadius',
  'stepped', 'gradient', 'cumulative', 'showDataLabels', 'yAxisID',
  'trendline', 'borderColor', 'backgroundColor', 'borderWidth', 'fill', 'tension',
] as const

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
