<template>
  <div
    class="relative rounded-lg border border-gray-200 dark:border-neutral-700 bg-gray-50 dark:bg-neutral-900 transition-shadow"
    :class="expanded ? 'p-3 space-y-2' : ''"
  >
    <!-- Collapsed header -->
    <button
      v-if="!expanded"
      type="button"
      class="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-gray-100 dark:hover:bg-neutral-700 rounded-lg transition-colors"
      @click="expanded = true"
    >
      <div class="flex items-center gap-2 min-w-0">
        <ChevronRight class="h-3.5 w-3.5 text-gray-400 dark:text-neutral-500 flex-shrink-0" />
        <span class="text-sm font-medium text-gray-700 dark:text-neutral-200 truncate">
          {{ local.label || local.column || 'Untitled' }}
        </span>
        <!-- Format badge -->
        <span v-if="local.format && local.format !== 'number'" class="text-sm text-gray-400 dark:text-neutral-500 uppercase tracking-wide flex-shrink-0">
          {{ local.format }}
        </span>
        <!-- Aggregation badge -->
        <span v-if="local.aggregation" class="text-sm px-1.5 py-0.5 rounded bg-indigo-50 dark:bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 flex-shrink-0">
          {{ aggLabel(local.aggregation) }}
        </span>
      </div>
      <button
        v-if="editMode"
        type="button"
        class="flex h-5 w-5 items-center justify-center rounded text-gray-300 dark:text-neutral-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 hover:text-rose-500 dark:hover:text-rose-400 transition-colors flex-shrink-0"
        title="Remove"
        @click.stop="emit('remove')"
      >
        <X class="h-3.5 w-3.5" />
      </button>
    </button>

    <!-- Expanded body -->
    <template v-if="expanded">
      <!-- Collapse button -->
      <button
        type="button"
        class="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded text-gray-400 dark:text-neutral-500 hover:bg-gray-200 dark:hover:bg-neutral-600 hover:text-gray-600 dark:hover:text-neutral-300 transition-colors z-10"
        title="Collapse"
        @click="expanded = false"
      >
        <ChevronDown class="h-3.5 w-3.5" />
      </button>

      <!-- Column picker -->
      <div class="space-y-1">
        <label class="text-sm text-gray-400 dark:text-neutral-500">Column</label>
        <div class="flex gap-2">
          <select
            :value="local.column"
            :disabled="!editMode"
            class="flex-1 rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
            @change="setField('column', ($event.target as HTMLSelectElement).value)"
          >
            <option value="" disabled>Column…</option>
            <option v-for="col in availableColumns" :key="col" :value="col">{{ col }}</option>
          </select>
          <!-- Remove button (expanded) -->
          <button
            v-if="editMode"
            type="button"
            class="flex h-7 w-7 items-center justify-center rounded text-gray-300 dark:text-neutral-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 hover:text-rose-500 dark:hover:text-rose-400 transition-colors flex-shrink-0"
            title="Remove"
            @click="emit('remove')"
          >
            <X class="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <!-- Label -->
      <div class="space-y-1">
        <label class="text-sm text-gray-400 dark:text-neutral-500">Label</label>
        <input
          :value="local.label ?? ''"
          type="text"
          placeholder="Label (optional)"
          :readonly="!editMode"
          class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50 dark:disabled:bg-neutral-800"
          @input="setField('label', ($event.target as HTMLInputElement).value || undefined)"
        />
      </div>

      <!-- Aggregation -->
      <div class="space-y-1">
        <label class="text-sm text-gray-400 dark:text-neutral-500">Aggregation</label>
        <select
          :value="local.aggregation || 'sum'"
          :disabled="!editMode"
          class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
          @change="setField('aggregation', ($event.target as HTMLSelectElement).value)"
        >
          <option v-for="a in aggregationOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
        </select>
      </div>

      <!-- Format + Decimals via FieldFormatControls -->
      <FieldFormatControls
        :model-value="formatModel"
        :edit-mode="editMode"
        show-format
        show-decimals
        @update:model-value="onFormatUpdate"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { reactive, computed, ref } from 'vue'
import { X, ChevronRight, ChevronDown } from 'lucide-vue-next'
import type { PivotValue } from '~/types/dashboard'
import FieldFormatControls from './FieldFormatControls.vue'

const AGG_LABELS: Record<string, string> = {
  sum: 'Sum',
  average: 'Avg',
  count: 'Count',
  countDistinct: 'Count Distinct',
  min: 'Min',
  max: 'Max',
  median: 'Median',
  stdDev: 'Std Dev',
  variance: 'Variance',
}
function aggLabel(v?: string) { return AGG_LABELS[v ?? ''] ?? v ?? '' }

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

const props = defineProps<{
  modelValue: PivotValue
  editMode: boolean
  availableColumns?: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: PivotValue]
  remove: []
}>()

const expanded = ref(!props.modelValue.column)
const local = reactive<PivotValue>({ ...props.modelValue })

function setField(key: keyof PivotValue, value: any) {
  ;(local as any)[key] = value
  emit('update:modelValue', { ...local })
}

const formatModel = computed(() => ({
  format: local.format,
  decimalPlaces: local.decimalPlaces,
}))

function onFormatUpdate(patch: { format?: string; decimalPlaces?: number }) {
  if ('format' in patch) local.format = patch.format as PivotValue['format']
  if ('decimalPlaces' in patch) local.decimalPlaces = patch.decimalPlaces
  emit('update:modelValue', { ...local })
}
</script>
