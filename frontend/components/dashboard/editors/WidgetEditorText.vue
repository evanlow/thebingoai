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

    <div class="flex items-center justify-between">
      <label class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Section header</label>
      <button
        role="switch"
        :aria-checked="localIsSection"
        class="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors"
        :class="localIsSection ? 'bg-indigo-600' : 'bg-gray-300 dark:bg-neutral-600'"
        :disabled="!editMode"
        @click="editMode && (localIsSection = !localIsSection)"
      >
        <span
          class="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform"
          :style="{ transform: localIsSection ? 'translateX(16px)' : 'translateX(0)' }"
        />
      </button>
    </div>

    <div v-if="localIsSection" class="space-y-1.5">
      <label class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Section color</label>
      <div class="flex items-center gap-2">
        <button
          v-for="color in SECTION_COLORS"
          :key="color"
          class="h-6 w-6 rounded-full border transition-shadow"
          :class="localSectionColor === color ? 'ring-2 ring-indigo-500 ring-offset-1 dark:ring-offset-neutral-900' : 'border-gray-200 dark:border-neutral-700'"
          :style="{ background: `var(--section-${color}-line)` }"
          :title="color"
          :disabled="!editMode"
          @click="editMode && (localSectionColor = color)"
        />
      </div>
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
import type { WidgetConfig, TextWidgetConfig, SectionColor } from '~/types/dashboard'
import { SECTION_COLORS } from '~/types/dashboard'

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

const localIsSection = computed({
  // Mirrors the display heuristic: undefined → heading content counts as a section
  get: () => textConfig.value.isSection ?? (textConfig.value.content ?? '').trimStart().startsWith('#'),
  set: (v: boolean) => emit('update:modelValue', { type: 'text', config: { ...textConfig.value, isSection: v } }),
})

const localSectionColor = computed({
  get: () => textConfig.value.sectionColor ?? 'default',
  set: (v: SectionColor) => emit('update:modelValue', { type: 'text', config: { ...textConfig.value, sectionColor: v } }),
})

const alignOptions = [
  { value: 'left', label: 'Left' },
  { value: 'center', label: 'Center' },
  { value: 'right', label: 'Right' },
]
</script>
