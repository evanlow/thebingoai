<template>
  <div class="flex items-end gap-2 flex-wrap">
    <!-- Format select -->
    <div v-if="showFormat" class="space-y-1" style="min-width:86px;">
      <label class="text-[10px] text-gray-400 dark:text-neutral-500">Format</label>
      <select
        :value="modelValue.format ?? ''"
        :disabled="!editMode"
        class="w-full rounded border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-xs text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:cursor-default disabled:bg-gray-50 dark:disabled:bg-neutral-800"
        @change="patch('format', ($event.target as HTMLSelectElement).value || undefined)"
      >
        <option value="">Default</option>
        <option value="text">Text</option>
        <option value="number">Number</option>
        <option value="currency">Currency</option>
        <option value="percent">Percent</option>
        <option value="date">Date</option>
        <option v-if="showDuration" value="duration">Duration</option>
      </select>
    </div>

    <!-- Align segmented -->
    <div v-if="showAlign" class="space-y-1">
      <label class="text-[10px] text-gray-400 dark:text-neutral-500">Align</label>
      <div class="flex gap-0.5">
        <button
          v-for="a in (['left', 'center', 'right'] as const)"
          :key="a"
          type="button"
          :disabled="!editMode"
          class="flex h-6 w-6 items-center justify-center rounded border transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          :class="(modelValue.align ?? 'left') === a
            ? 'border-indigo-400 bg-indigo-50 dark:bg-indigo-500/15 text-indigo-600 dark:text-indigo-400'
            : 'border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-gray-400 dark:text-neutral-500 hover:border-gray-300'"
          :title="a"
          @click="editMode && patch('align', a)"
        >
          <AlignLeft v-if="a === 'left'" class="h-3 w-3" />
          <AlignCenter v-else-if="a === 'center'" class="h-3 w-3" />
          <AlignRight v-else class="h-3 w-3" />
        </button>
      </div>
    </div>

    <!-- Decimal places: None / .0 / .00 segmented -->
    <div v-if="showDecimals && isNumeric" class="space-y-1">
      <label class="text-[10px] text-gray-400 dark:text-neutral-500">Decimals</label>
      <div class="flex rounded border border-gray-200 dark:border-neutral-700 overflow-hidden">
        <button
          v-for="opt in decimalOpts"
          :key="String(opt.value)"
          type="button"
          :disabled="!editMode"
          class="px-2 py-1 text-[10px] font-medium transition-colors border-r border-gray-200 dark:border-neutral-700 last:border-r-0 disabled:opacity-40 disabled:cursor-not-allowed"
          :class="effectiveDecimals === opt.value
            ? 'bg-indigo-600 text-white'
            : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
          @click="editMode && patch('decimalPlaces', opt.value)"
        >{{ opt.label }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { AlignLeft, AlignCenter, AlignRight } from 'lucide-vue-next'
import { isNumericFormat } from '~/utils/numberFormat'

export interface FieldFormatModel {
  format?: string
  decimalPlaces?: number
  align?: 'left' | 'center' | 'right'
}

const props = defineProps<{
  modelValue: FieldFormatModel
  editMode: boolean
  showFormat?: boolean
  showAlign?: boolean
  showDecimals?: boolean
  showDuration?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: FieldFormatModel]
}>()

function patch(key: keyof FieldFormatModel, value: any) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

const isNumeric = computed(() => isNumericFormat(props.modelValue.format))

/** Effective decimal places: use stored value or per-format default */
const effectiveDecimals = computed(() => {
  if (props.modelValue.decimalPlaces !== undefined) return props.modelValue.decimalPlaces
  return props.modelValue.format === 'currency' ? 2 : 0
})

const decimalOpts = [
  { value: 0, label: 'None' },
  { value: 2, label: '.00' },
]
</script>
