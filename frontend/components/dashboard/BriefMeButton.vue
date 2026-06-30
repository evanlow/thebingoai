<template>
  <div class="relative" ref="wrapperRef">
    <button
      class="hdr-btn"
      :class="{ 'hdr-btn--active': scheduled }"
      :title="scheduled ? (selectedLabel ? `Briefing ${selectedLabel.toLowerCase()}` : 'Briefing scheduled') : 'Generate a briefing'"
      @click="open = !open"
    >
      <Sparkles class="h-3.5 w-3.5" />
      <span class="hidden sm:inline">Brief me</span>
    </button>

    <Transition name="brief-sched">
      <div
        v-if="open"
        class="absolute right-0 top-full z-50 mt-1.5 w-44 rounded-lg border border-gray-200 bg-white py-1 shadow-lg dark:border-neutral-700 dark:bg-neutral-800"
      >
        <button
          class="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs font-medium text-gray-700 hover:bg-gray-100 dark:text-neutral-200 dark:hover:bg-neutral-700"
          @click="briefNow"
        >
          <Sparkles class="h-3.5 w-3.5 text-indigo-500" />
          <span>Now</span>
        </button>
        <div class="my-1 border-t border-gray-100 dark:border-neutral-700" />
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
          :disabled="busy || !scheduled"
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
import { Sparkles, Check } from 'lucide-vue-next'
import { useApi } from '~/composables/useApi'

const props = defineProps<{ dashboardId: number }>()
const api = useApi()

// Daily/Weekly are backend presets; Monthly has no preset so it goes as cron
// (9am on the 1st). `scheduled` drives the active highlight + Turn off; `selected`
// is the matched option for the check mark (empty when a custom schedule exists).
const OPTIONS = [
  { label: 'Daily', value: 'daily', type: 'preset', val: 'daily' },
  { label: 'Weekly', value: 'weekly', type: 'preset', val: 'weekly' },
  { label: 'Monthly', value: 'monthly', type: 'cron', val: '0 9 1 * *' },
] as const

const open = ref(false)
const busy = ref(false)
const error = ref('')
const selected = ref<string>('')
const scheduled = ref(false)
const wrapperRef = ref<HTMLElement | null>(null)

const selectedLabel = computed(() => OPTIONS.find(o => o.value === selected.value)?.label ?? '')

// Hydrate from the server so the highlight + Turn off survive a reload.
async function loadSchedule() {
  try {
    const job = await api.dashboards.getBriefSchedule(props.dashboardId)
    if (!job?.is_active) return
    scheduled.value = true
    selected.value = OPTIONS.find(o => o.type === job.schedule_type && o.val === job.schedule_value)?.value ?? ''
  } catch {
    // No schedule / fetch failed — leave the button in its default state.
  }
}

// Navigate to the generating page immediately. The briefing is created there
// (POST /brief), so the click feels instant instead of blocking on a POST that
// queues behind the dashboard's in-flight widget-refresh requests.
function briefNow() {
  open.value = false
  navigateTo(`/briefings/new?dashboard_id=${props.dashboardId}`)
}

async function choose(opt: typeof OPTIONS[number]) {
  busy.value = true
  error.value = ''
  try {
    await api.dashboards.setBriefSchedule(props.dashboardId, {
      schedule_type: opt.type,
      schedule_value: opt.val,
    })
    selected.value = opt.value
    scheduled.value = true
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
    scheduled.value = false
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
onMounted(() => {
  document.addEventListener('click', onDocumentClick, true)
  loadSchedule()
})
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
.hdr-btn--active {
  border-color: #6366f1;
  background: color-mix(in srgb, #6366f1 12%, var(--paper-0));
  color: #6366f1;
}
.hdr-btn--active:hover { background: color-mix(in srgb, #6366f1 18%, var(--paper-0)); }

.brief-sched-enter-active,
.brief-sched-leave-active { transition: opacity 0.12s, transform 0.12s; }
.brief-sched-enter-from,
.brief-sched-leave-to { opacity: 0; transform: translateY(-4px) scale(0.97); }
</style>
