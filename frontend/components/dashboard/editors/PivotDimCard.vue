<template>
  <div
    class="relative rounded-lg border border-gray-200 bg-gray-50 transition-shadow"
    :class="expanded ? 'p-3 space-y-2' : ''"
  >
    <!-- Collapsed header -->
    <button
      v-if="!expanded"
      type="button"
      class="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-gray-100 rounded-lg transition-colors"
      @click="expanded = true"
    >
      <div class="flex items-center gap-2 min-w-0">
        <ChevronRight class="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
        <span class="text-sm font-medium text-gray-700 truncate">
          {{ local.label || local.column || 'Untitled' }}
        </span>
      </div>
      <button
        v-if="editMode"
        type="button"
        class="flex h-5 w-5 items-center justify-center rounded text-gray-300 hover:bg-rose-50 hover:text-rose-500 transition-colors flex-shrink-0"
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
        class="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded text-gray-400 hover:bg-gray-200 hover:text-gray-600 transition-colors z-10"
        title="Collapse"
        @click="expanded = false"
      >
        <ChevronDown class="h-3.5 w-3.5" />
      </button>

      <!-- Column picker -->
      <div class="space-y-1">
        <label class="text-[10px] text-gray-400">Column</label>
        <div class="flex gap-2">
          <select
            :value="local.column"
            :disabled="!editMode"
            class="flex-1 rounded border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50"
            @change="setField('column', ($event.target as HTMLSelectElement).value)"
          >
            <option value="" disabled>Column…</option>
            <option v-for="col in availableColumns" :key="col" :value="col">{{ col }}</option>
          </select>
          <!-- Remove button (expanded) -->
          <button
            v-if="editMode"
            type="button"
            class="flex h-7 w-7 items-center justify-center rounded text-gray-300 hover:bg-rose-50 hover:text-rose-500 transition-colors flex-shrink-0"
            title="Remove"
            @click="emit('remove')"
          >
            <X class="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <!-- Label -->
      <div class="space-y-1">
        <label class="text-[10px] text-gray-400">Label</label>
        <input
          :value="local.label ?? ''"
          type="text"
          placeholder="Label (optional)"
          :readonly="!editMode"
          class="w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-300 disabled:bg-gray-50"
          @input="setField('label', ($event.target as HTMLInputElement).value || undefined)"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { X, ChevronRight, ChevronDown } from 'lucide-vue-next'
import type { PivotDimension } from '~/types/dashboard'

const props = defineProps<{
  modelValue: PivotDimension
  editMode: boolean
  availableColumns?: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: PivotDimension]
  remove: []
}>()

const expanded = ref(!props.modelValue.column)
const local = reactive<PivotDimension>({ ...props.modelValue })

function setField(key: keyof PivotDimension, value: any) {
  ;(local as any)[key] = value
  emit('update:modelValue', { ...local })
}
</script>
