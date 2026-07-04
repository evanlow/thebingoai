<template>
  <div class="h-full overflow-y-auto p-5 space-y-5">
    <div class="space-y-1.5">
      <label class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Content (Markdown)</label>
      <textarea
        v-model="localContent"
        :readonly="!editMode"
        rows="12"
        class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-gray-50 dark:bg-neutral-900 px-3 py-2.5 font-mono text-sm text-gray-800 dark:text-neutral-200 leading-relaxed resize-none focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 transition-colors"
        :class="editMode ? 'bg-white dark:bg-neutral-900' : 'cursor-default'"
        spellcheck="false"
      />
    </div>

    <div class="space-y-1.5">
      <label class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Alignment</label>
      <div class="flex rounded-lg border border-gray-200 dark:border-neutral-700 overflow-hidden">
        <button
          v-for="opt in alignOptions"
          :key="opt.value"
          class="flex-1 py-1.5 text-sm font-medium transition-colors"
          :class="localAlignment === opt.value
            ? 'bg-indigo-600 text-white'
            : 'bg-white dark:bg-neutral-900 text-gray-500 dark:text-neutral-400 hover:bg-gray-50 dark:hover:bg-neutral-800'"
          :disabled="!editMode"
          @click="editMode && (localAlignment = opt.value)"
        >
          {{ opt.label }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WidgetConfig, TextWidgetConfig } from '~/types/dashboard'

const props = defineProps<{
  modelValue: WidgetConfig
  editMode: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WidgetConfig]
}>()

const textConfig = computed(() => props.modelValue.config as TextWidgetConfig)

const localContent = computed({
  get: () => textConfig.value.content,
  set: (v) => emit('update:modelValue', { type: 'text', config: { ...textConfig.value, content: v } }),
})

const localAlignment = computed({
  get: () => textConfig.value.alignment ?? 'left',
  set: (v) => emit('update:modelValue', { type: 'text', config: { ...textConfig.value, alignment: v as TextWidgetConfig['alignment'] } }),
})

const alignOptions = [
  { value: 'left', label: 'Left' },
  { value: 'center', label: 'Center' },
  { value: 'right', label: 'Right' },
]
</script>
