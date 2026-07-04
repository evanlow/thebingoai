<template>
  <div class="h-full overflow-y-auto p-5 space-y-5 [&>*+*]:border-t [&>*+*]:border-gray-200 [&>*+*]:pt-5">

    <!-- Title -->
    <div class="space-y-2">
      <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Title</h3>
      <div class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Show title</span>
        <button type="button" role="switch" :aria-checked="localShowTitle" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors disabled:opacity-40"
          :class="localShowTitle ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
          @click="editMode && (localShowTitle = !localShowTitle, emitUpdate())">
          <span class="inline-block h-4 w-4 rounded-full bg-white shadow transition mt-0.5"
            :class="localShowTitle ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
      <div v-if="localShowTitle" class="space-y-1">
        <label class="text-sm text-gray-700 dark:text-neutral-200">Title text</label>
        <input v-model="localTitle" type="text" placeholder="Pivot title…" :readonly="!editMode"
          class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300"
          :class="!editMode ? 'cursor-default bg-gray-50 dark:bg-neutral-900' : ''" @input="emitUpdate()" />
      </div>
    </div>

    <!-- Table Body -->
    <div class="space-y-1">
      <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide mb-2">Table Body</h3>
      <div v-for="opt in bodyOptions" :key="opt.key" class="flex items-center justify-between py-1">
        <span class="text-sm text-gray-700 dark:text-neutral-200">{{ opt.label }}</span>
        <button type="button" role="switch" :aria-checked="localFlags[opt.key]" :disabled="!editMode"
          class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors disabled:opacity-40"
          :class="localFlags[opt.key] ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-neutral-600'"
          @click="editMode && (localFlags[opt.key] = !localFlags[opt.key], emitUpdate())">
          <span class="inline-block h-4 w-4 rounded-full bg-white shadow transition mt-0.5"
            :class="localFlags[opt.key] ? 'translate-x-4 ml-0.5' : 'translate-x-0 ml-0.5'" />
        </button>
      </div>
    </div>

    <!-- Table Colors -->
    <div class="space-y-3">
      <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Table Colors</h3>
      <div v-for="opt in tableColorOptions" :key="opt.key" class="flex items-center justify-between">
        <span class="text-sm text-gray-700 dark:text-neutral-200">{{ opt.label }}</span>
        <ColorPickerPopover :model-value="localTableColors[opt.key] || undefined" :disabled="!editMode"
          @update:model-value="(c) => { localTableColors[opt.key] = c ?? ''; emitUpdate() }" />
      </div>
    </div>

    <!-- Totals labels -->
    <div class="space-y-2">
      <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Totals Labels</h3>
      <div class="space-y-1">
        <label class="text-sm text-gray-700 dark:text-neutral-200">Subtotal label</label>
        <input v-model="localSubtotalLabel" type="text" placeholder="Subtotal" :readonly="!editMode"
          class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5 text-sm disabled:bg-gray-50 dark:disabled:bg-neutral-800" @input="emitUpdate()" />
      </div>
      <div class="space-y-1">
        <label class="text-sm text-gray-700 dark:text-neutral-200">Grand total label</label>
        <input v-model="localGrandTotalLabel" type="text" placeholder="Grand total" :readonly="!editMode"
          class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5 text-sm disabled:bg-gray-50 dark:disabled:bg-neutral-800" @input="emitUpdate()" />
      </div>
    </div>

    <!-- Data -->
    <div class="space-y-1.5">
      <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Data</h3>
      <label class="text-sm text-gray-700 dark:text-neutral-200">Missing data display</label>
      <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
        <button v-for="opt in missingOptions" :key="opt.value" type="button" :disabled="!editMode"
          class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40"
          :class="localMissingData === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
          @click="editMode && (localMissingData = opt.value, emitUpdate())">{{ opt.label }}</button>
      </div>
    </div>

    <!-- Border -->
    <div class="space-y-3">
      <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Border</h3>
      <div class="flex items-center justify-between">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Color</span>
        <ColorPickerPopover :model-value="localBorderColor || undefined" :disabled="!editMode"
          @update:model-value="(c) => { localBorderColor = c ?? ''; emitUpdate() }" />
      </div>
      <div class="space-y-1.5">
        <label class="text-sm text-gray-700 dark:text-neutral-200">Style</label>
        <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
          <button v-for="opt in borderStyleOptions" :key="opt.value" type="button" :disabled="!editMode"
            class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40"
            :class="(localBorderStyle ?? 'solid') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
            @click="editMode && (localBorderStyle = opt.value, emitUpdate())">{{ opt.label }}</button>
        </div>
      </div>
      <div class="flex items-center justify-between gap-2">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Width</span>
        <div class="flex items-center gap-2 flex-1 max-w-[140px]">
          <input v-model.number="localBorderWidth" type="range" min="0" max="5" :disabled="!editMode" class="flex-1 disabled:opacity-40" @input="emitUpdate()" />
          <span class="text-sm text-gray-500 dark:text-neutral-400 tabular-nums w-6 text-right">{{ localBorderWidth }}px</span>
        </div>
      </div>
      <div class="flex items-center justify-between gap-2">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Radius</span>
        <div class="flex items-center gap-2 flex-1 max-w-[140px]">
          <input v-model.number="localBorderRadius" type="range" min="0" max="16" :disabled="!editMode" class="flex-1 disabled:opacity-40" @input="emitUpdate()" />
          <span class="text-sm text-gray-500 dark:text-neutral-400 tabular-nums w-6 text-right">{{ localBorderRadius }}px</span>
        </div>
      </div>
    </div>

    <!-- Font -->
    <div class="space-y-3">
      <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Font</h3>
      <div class="flex items-center justify-between gap-2">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Family</span>
        <select v-model="localFontFamily" :disabled="!editMode"
          class="rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm disabled:bg-gray-50 dark:disabled:bg-neutral-800" @change="emitUpdate()">
          <option value="system">System</option>
          <option value="sans">Sans-serif</option>
          <option value="serif">Serif</option>
          <option value="mono">Monospace</option>
        </select>
      </div>
      <div class="space-y-1.5">
        <label class="text-sm text-gray-700 dark:text-neutral-200">Size</label>
        <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
          <button v-for="opt in fontSizeOptions" :key="opt.value" type="button" :disabled="!editMode"
            class="flex-1 py-1.5 text-sm font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40"
            :class="(localFontSize ?? 'sm') === opt.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
            @click="editMode && (localFontSize = opt.value, emitUpdate())">{{ opt.label }}</button>
        </div>
      </div>
      <div class="flex items-center justify-between">
        <span class="text-sm text-gray-700 dark:text-neutral-200">Color</span>
        <ColorPickerPopover :model-value="localFontColor || undefined" :disabled="!editMode"
          @update:model-value="(c) => { localFontColor = c ?? ''; emitUpdate() }" />
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { computed } from 'vue'
import type { WidgetConfig, PivotTableWidgetConfig } from '~/types/dashboard'
import ColorPickerPopover from './ColorPickerPopover.vue'

const props = defineProps<{ modelValue: WidgetConfig; editMode: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: WidgetConfig] }>()

const cfg = computed(() => props.modelValue.config as PivotTableWidgetConfig)

const localShowTitle = ref(!!cfg.value.showTitle)
const localTitle = ref(cfg.value.title ?? '')

const bodyOptions = [
  { key: 'stripedRows' as const, label: 'Striped rows' },
  { key: 'horizontalScrolling' as const, label: 'Horizontal scrolling' },
]
const localFlags = ref({
  stripedRows: !!cfg.value.stripedRows,
  horizontalScrolling: !!cfg.value.horizontalScrolling,
})

type ColorKey = 'headerBackground' | 'cellBorderColor' | 'oddRowColor' | 'evenRowColor'
const tableColorOptions: { key: ColorKey; label: string }[] = [
  { key: 'headerBackground', label: 'Header background' },
  { key: 'cellBorderColor', label: 'Cell border color' },
  { key: 'oddRowColor', label: 'Odd row color' },
  { key: 'evenRowColor', label: 'Even row color' },
]
const localTableColors = ref<Record<ColorKey, string>>({
  headerBackground: cfg.value.headerBackground ?? '',
  cellBorderColor: cfg.value.cellBorderColor ?? '',
  oddRowColor: cfg.value.oddRowColor ?? '',
  evenRowColor: cfg.value.evenRowColor ?? '',
})

const localSubtotalLabel = ref(cfg.value.subtotalLabel ?? '')
const localGrandTotalLabel = ref(cfg.value.grandTotalLabel ?? '')

const missingOptions = [
  { value: 'dash' as const, label: '— dash' },
  { value: 'blank' as const, label: 'Blank' },
  { value: 'zero' as const, label: '0' },
  { value: 'noData' as const, label: 'No data' },
]
const localMissingData = ref<'dash' | 'blank' | 'zero' | 'noData' | 'null'>(cfg.value.missingDataDisplay ?? 'dash')

const localBorderColor = ref(cfg.value.borderColor ?? '')
const localBorderStyle = ref<'solid' | 'dashed' | 'dotted' | 'none'>(cfg.value.borderStyle ?? 'solid')
const localBorderWidth = ref(cfg.value.borderWidth ?? 0)
const localBorderRadius = ref(cfg.value.borderRadius ?? 0)
const localFontFamily = ref<'system' | 'sans' | 'serif' | 'mono'>(cfg.value.fontFamily ?? 'system')
const localFontSize = ref<'xs' | 'sm' | 'md' | 'lg'>(cfg.value.fontSize ?? 'sm')
const localFontColor = ref(cfg.value.fontColor ?? '')

const borderStyleOptions = [
  { value: 'solid' as const, label: 'Solid' },
  { value: 'dashed' as const, label: 'Dashed' },
  { value: 'dotted' as const, label: 'Dotted' },
  { value: 'none' as const, label: 'None' },
]
const fontSizeOptions = [
  { value: 'xs' as const, label: 'XS' },
  { value: 'sm' as const, label: 'S' },
  { value: 'md' as const, label: 'M' },
  { value: 'lg' as const, label: 'L' },
]

function emitUpdate() {
  emit('update:modelValue', {
    type: 'pivot_table',
    config: {
      ...cfg.value,
      title: localTitle.value || undefined,
      showTitle: localShowTitle.value || undefined,
      stripedRows: localFlags.value.stripedRows || undefined,
      horizontalScrolling: localFlags.value.horizontalScrolling || undefined,
      headerBackground: localTableColors.value.headerBackground || undefined,
      cellBorderColor: localTableColors.value.cellBorderColor || undefined,
      oddRowColor: localTableColors.value.oddRowColor || undefined,
      evenRowColor: localTableColors.value.evenRowColor || undefined,
      subtotalLabel: localSubtotalLabel.value || undefined,
      grandTotalLabel: localGrandTotalLabel.value || undefined,
      missingDataDisplay: localMissingData.value !== 'dash' ? localMissingData.value : undefined,
      borderColor: localBorderColor.value || undefined,
      borderStyle: localBorderStyle.value !== 'solid' ? localBorderStyle.value : undefined,
      borderWidth: localBorderWidth.value > 0 ? localBorderWidth.value : undefined,
      borderRadius: localBorderRadius.value > 0 ? localBorderRadius.value : undefined,
      fontFamily: localFontFamily.value !== 'system' ? localFontFamily.value : undefined,
      fontSize: localFontSize.value !== 'sm' ? localFontSize.value : undefined,
      fontColor: localFontColor.value || undefined,
    } as PivotTableWidgetConfig,
  })
}
</script>
