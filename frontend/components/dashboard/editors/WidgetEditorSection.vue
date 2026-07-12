<template>
  <div class="h-full overflow-y-auto p-5 space-y-5">
    <div class="space-y-1.5">
      <label class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Section name</label>
      <input
        v-model="localTitle"
        type="text"
        :readonly="!editMode"
        placeholder="Section name"
        class="w-full rounded-lg border border-gray-200 dark:border-neutral-700 bg-gray-50 dark:bg-neutral-900 px-3 py-2.5 text-sm text-gray-800 dark:text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 transition-colors"
        :class="editMode ? 'bg-white dark:bg-neutral-900' : 'cursor-default'"
      />
    </div>

    <div class="space-y-1.5">
      <label class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">Section color</label>
      <div class="flex items-center gap-2">
        <button
          v-for="color in SECTION_COLORS"
          :key="color"
          class="h-6 w-6 rounded-full border transition-shadow"
          :class="localColor === color ? 'ring-2 ring-indigo-500 ring-offset-1 dark:ring-offset-neutral-900' : 'border-gray-200 dark:border-neutral-700'"
          :style="{ background: `var(--section-${color}-line)` }"
          :title="color"
          :disabled="!editMode"
          @click="editMode && (localColor = color)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WidgetConfig, SectionWidgetConfig, SectionColor } from '~/types/dashboard'
import { SECTION_COLORS, sectionColorToken } from '~/types/dashboard'

const props = defineProps<{
  modelValue: WidgetConfig
  editMode: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: WidgetConfig]
}>()

const sectionConfig = computed(() => props.modelValue.config as SectionWidgetConfig)

const localTitle = computed({
  get: () => sectionConfig.value.title ?? '',
  set: (v) => emit('update:modelValue', { type: 'section', config: { ...sectionConfig.value, title: v } }),
})

const localColor = computed({
  get: () => sectionColorToken(sectionConfig.value.sectionColor),
  set: (v: SectionColor) => emit('update:modelValue', { type: 'section', config: { ...sectionConfig.value, sectionColor: v } }),
})
</script>
