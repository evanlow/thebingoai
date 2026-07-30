<template>
  <!-- One column of a horizontal stepper. The connector is drawn as two half
       lines flanking the icon, so the icon lands over the centre of its label
       and the first/last icons sit inset by half a column. -->
  <div class="flex-1 min-w-0">
    <div class="flex items-center">
      <div class="h-px flex-1" :class="isFirst ? 'bg-transparent' : leftLineClass" />
      <div
        class="w-3.5 h-3.5 rounded-full flex items-center justify-center shrink-0"
        :class="iconClasses"
      >
        <!-- Completed: checkmark -->
        <svg v-if="status === 'completed'" class="w-2 h-2" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <!-- Active: pulsing dot -->
        <div v-else-if="status === 'active'" class="w-1.5 h-1.5 rounded-full animate-pulse" :class="activeDotClass" />
        <!-- Failed: X -->
        <svg v-else-if="status === 'failed'" class="w-2 h-2" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
        <!-- Pending: empty -->
      </div>
      <div class="h-px flex-1" :class="isLast ? 'bg-transparent' : rightLineClass" />
    </div>

    <!-- Label + timestamp, centred under the icon -->
    <div class="mt-1 px-1 text-center leading-tight">
      <div class="text-xs font-medium" :class="labelColor">
        {{ status === 'active' ? activeLabel : (status === 'failed' ? failedLabel : label) }}
      </div>
      <div v-if="formattedTime" class="text-[11px] text-gray-300">
        {{ formattedTime }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { parseUtcDate } from '~/utils/format'
type StepState = 'completed' | 'active' | 'pending' | 'failed'

const props = defineProps<{
  status: StepState
  label: string
  activeLabel: string
  timestamp: string | null
  isLast: boolean
  prevStatus?: StepState
}>()

const isFirst = computed(() => props.prevStatus === undefined)

const failedLabel = computed(() => props.label.replace(/built|profiled/i, 'failed').replace(/^Uploaded$/, 'Upload failed'))

const iconClasses = computed(() => {
  switch (props.status) {
    case 'completed': return 'bg-emerald-500'
    case 'active': return 'border-2 border-amber-400'
    case 'failed': return 'bg-red-500'
    default: return 'border-2 border-gray-200 dark:border-neutral-700'
  }
})

const activeDotClass = computed(() => {
  // Use blue for uploading (first step), amber for the rest
  return props.label === 'Uploaded' ? 'bg-blue-500' : 'bg-amber-400'
})

const labelColor = computed(() => {
  switch (props.status) {
    case 'completed': return 'text-emerald-500'
    case 'active': return props.label === 'Uploaded' ? 'text-blue-500' : 'text-amber-500'
    case 'failed': return 'text-red-500'
    default: return 'text-gray-300'
  }
})

// A half line is green once the step it leaves behind is done, so a completed
// step followed by a pending one reads as a segment half filled.
const DONE = 'bg-emerald-500'
const TODO = 'bg-gray-200 dark:bg-neutral-700'
const leftLineClass = computed(() => (props.prevStatus === 'completed' ? DONE : TODO))
const rightLineClass = computed(() => (props.status === 'completed' ? DONE : TODO))

const formattedTime = computed(() => {
  if (!props.timestamp) return null
  try {
    const date = parseUtcDate(props.timestamp)
    return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return null
  }
})
</script>
