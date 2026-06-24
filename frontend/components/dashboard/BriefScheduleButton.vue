<template>
  <div class="relative" ref="wrapperRef">
    <button
      class="hdr-btn"
      :title="selected ? `Briefing ${selectedLabel.toLowerCase()}` : 'Schedule recurring briefings'"
      @click="open = !open"
    >
      <CalendarClock class="h-3.5 w-3.5" />
      <span class="hidden sm:inline">{{ selected ? selectedLabel : 'Schedule' }}</span>
    </button>

    <Transition name="brief-sched">
      <div
        v-if="open"
        class="absolute right-0 top-full z-50 mt-1.5 w-44 rounded-lg border border-gray-200 bg-white py-1 shadow-lg dark:border-neutral-700 dark:bg-neutral-800"
      >
        <button
          v-for="opt in OPTIONS"
          :key="opt.value"
          class="flex w-full items-center justify-between px-3 py-1.5 text-left text-xs text-gray-700 hover:bg-gray-100 disabled:opacity-50 dark:text-neutral-200 dark:hover:bg-neutral-700"
          :disabled="busy"
          @click="choose(opt)"
        >
          <span>{{ opt.label }}</span>
          <Check v-if="selected === opt.value" class="h-3.5 w-3.5 text-indigo-500" />
        </button>
        <div class="my-1 border-t border-gray-100 dark:border-neutral-700" />
        <button
          class="w-full px-3 py-1.5 text-left text-xs text-red-500 hover:bg-red-50 disabled:opacity-40 dark:hover:bg-neutral-700"
          :disabled="busy || !selected"
          @click="turnOff"
        >
          Turn off
        </button>
        <p v-if="error" class="px-3 pt-1 text-xs text-red-500">{{ error }}</p>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { CalendarClock, Check } from 'lucide-vue-next'
import { useApi } from '~/composables/useApi'

const props = defineProps<{ dashboardId: number }>()
const api = useApi()

// Daily/Weekly are backend presets; Monthly has no preset so it goes as cron
// (9am on the 1st). Recurring briefings have no GET endpoint, so `selected`
// reflects what was set this session only, not server state across reloads.
// ponytail: add a GET + populate on mount if persisted display is needed.
const OPTIONS = [
  { label: 'Daily', value: 'daily', type: 'preset', val: 'daily' },
  { label: 'Weekly', value: 'weekly', type: 'preset', val: 'weekly' },
  { label: 'Monthly', value: 'monthly', type: 'cron', val: '0 9 1 * *' },
] as const

const open = ref(false)
const busy = ref(false)
const error = ref('')
const selected = ref<string>('')
const wrapperRef = ref<HTMLElement | null>(null)

const selectedLabel = computed(() => OPTIONS.find(o => o.value === selected.value)?.label ?? '')

async function choose(opt: typeof OPTIONS[number]) {
  busy.value = true
  error.value = ''
  try {
    await api.dashboards.setBriefSchedule(props.dashboardId, {
      schedule_type: opt.type,
      schedule_value: opt.val,
    })
    selected.value = opt.value
    open.value = false
  } catch (err: any) {
    error.value = err?.data?.detail ?? 'Failed to set schedule'
  } finally {
    busy.value = false
  }
}

async function turnOff() {
  busy.value = true
  error.value = ''
  try {
    await api.dashboards.removeBriefSchedule(props.dashboardId)
    selected.value = ''
    open.value = false
  } catch (err: any) {
    error.value = err?.data?.detail ?? 'Failed to turn off'
  } finally {
    busy.value = false
  }
}

function onDocumentClick(e: MouseEvent) {
  if (wrapperRef.value && !wrapperRef.value.contains(e.target as Node)) open.value = false
}
onMounted(() => document.addEventListener('click', onDocumentClick, true))
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick, true))
</script>

<style scoped>
/* Mirror DashboardTitleBar's .hdr-btn — scoped styles there don't reach a
   non-root element in this component. */
.hdr-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 8px;
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 500;
  border: 1px solid var(--line);
  background: var(--paper-0);
  color: var(--ink-1);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.1s, border-color 0.1s;
}
.hdr-btn:hover { background: var(--paper-2); }

.brief-sched-enter-active,
.brief-sched-leave-active { transition: opacity 0.12s, transform 0.12s; }
.brief-sched-enter-from,
.brief-sched-leave-to { opacity: 0; transform: translateY(-4px) scale(0.97); }
</style>
