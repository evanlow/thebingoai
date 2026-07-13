<template>
  <div class="h-full overflow-y-auto bg-white dark:bg-neutral-900">
    <!-- Skeleton -->
    <div v-if="loading" class="max-w-3xl mx-auto px-6 py-10 space-y-4">
      <div class="h-3 w-40 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
      <div class="h-10 w-3/4 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
      <div class="h-4 w-full bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
    </div>

    <!-- Error -->
    <div v-else-if="!briefing && error" class="max-w-3xl mx-auto px-6 py-10">
      <div class="rounded-lg border border-rose-200 dark:border-rose-900/60 bg-rose-50 dark:bg-rose-950/40 p-6">
        <h2 class="text-lg font-semibold text-rose-900 dark:text-rose-200 mb-2">Could not load briefing</h2>
        <p class="text-sm text-rose-700 dark:text-rose-300">{{ error }}</p>
      </div>
    </div>

    <!-- Failed -->
    <div v-else-if="briefing?.status === 'failed'" class="max-w-3xl mx-auto px-6 py-10">
      <div class="rounded-lg border border-rose-200 dark:border-rose-900/60 bg-rose-50 dark:bg-rose-950/40 p-6">
        <h2 class="text-lg font-semibold text-rose-900 dark:text-rose-200 mb-2">Briefing failed</h2>
        <p class="text-sm text-rose-700 dark:text-rose-300 mb-4">{{ briefing.error || 'Unknown error.' }}</p>
      </div>
    </div>

    <!-- Generating -->
    <div v-else-if="briefing?.status === 'generating'" class="max-w-3xl mx-auto px-6 py-10">
      <div class="flex flex-col items-center justify-center gap-3 py-16">
        <div class="relative h-10 w-10">
          <div class="h-10 w-10 rounded-full border-2 border-indigo-100 dark:border-indigo-900/40" />
          <div class="absolute inset-0 rounded-full border-2 border-transparent border-t-indigo-500 animate-spin" />
        </div>
        <p class="text-sm text-neutral-500">Briefing generating…</p>
      </div>
    </div>

    <!-- Ready -->
    <article v-else-if="briefing?.payload" ref="articleRef" class="max-w-3xl mx-auto px-6 py-10">
      <div data-pdf-ignore="true" class="flex justify-end mb-6">
        <button
          class="text-sm px-3 py-1 rounded-full border border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="exporting"
          @click="onExportPdf"
        >
          {{ exporting ? 'Generating…' : 'Export PDF' }}
        </button>
      </div>

      <div data-pdf-block>
        <p class="text-sm uppercase tracking-wider text-neutral-500 mb-3">
          Dashboard #{{ briefing.dashboard_id }}
          <template v-if="briefing.date_range_from">  · {{ formatRange(briefing) }}</template>
        </p>
        <h1 class="font-serif text-4xl font-bold leading-tight text-neutral-900 dark:text-neutral-100 mb-5 tracking-tight">
          {{ briefing.payload.headline }}
        </h1>

        <div class="flex items-center gap-3 text-sm text-neutral-600 dark:text-neutral-400 mb-5 pb-4 border-b border-neutral-100 dark:border-neutral-800">
          <div class="w-6 h-6 rounded-full bg-gradient-to-br from-indigo-500 to-pink-500" />
          <span><strong>Compiled by Bingo</strong>  ·  {{ formatDate(briefing.created_at) }}</span>
        </div>

        <p class="text-lg leading-relaxed text-neutral-800 dark:text-neutral-200 mb-6">
          {{ briefing.payload.deck }}
        </p>
      </div>

      <div v-if="briefing.payload.kpis.length" data-pdf-block class="grid gap-3 p-4 bg-neutral-50 dark:bg-neutral-800 rounded-lg mb-7"
        :style="{ gridTemplateColumns: `repeat(${briefing.payload.kpis.length}, minmax(0,1fr))` }">
        <div v-for="(k, i) in briefing.payload.kpis" :key="i" class="pl-3" :class="{ 'border-l border-neutral-200 dark:border-neutral-700': i > 0 }">
          <div class="text-sm uppercase tracking-wide text-neutral-500">{{ k.label }}</div>
          <div class="text-2xl font-semibold mt-1 text-neutral-900 dark:text-neutral-100">{{ k.value }}</div>
          <div v-if="k.delta_vs_prev" class="text-sm mt-1" :class="deltaClass(k.delta_direction)">{{ k.delta_vs_prev }}</div>
        </div>
      </div>

      <section v-for="(s, idx) in briefing.payload.sections" :key="idx" data-pdf-block class="mb-7">
        <h2 class="font-serif text-2xl font-bold text-neutral-900 dark:text-neutral-100 mb-3">
          <span class="text-neutral-400 font-normal mr-2">{{ idx + 1 }}.</span>{{ stripLeadingNumber(s.heading) }}
        </h2>
        <div class="text-[15px] leading-relaxed text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap">
          {{ s.prose }}
        </div>
        <BriefingWidgetEmbed
          v-if="s.widget_id"
          :widget-id="s.widget_id"
          :dashboard-id="briefing.dashboard_id"
          class="mt-4"
          @loaded="markWidgetLoaded"
        />
      </section>

      <aside data-pdf-block class="rounded-lg bg-yellow-50 dark:bg-yellow-950 border border-yellow-200 dark:border-yellow-800 p-5 mt-4">
        <p class="text-sm uppercase tracking-wider font-semibold text-yellow-900 dark:text-yellow-200 mb-2">Key takeaways</p>
        <ul class="list-disc pl-5 space-y-1 text-yellow-950 dark:text-yellow-200">
          <li v-for="(t, i) in briefing.payload.key_takeaways" :key="i" class="text-sm">{{ t }}</li>
        </ul>
      </aside>

      <aside v-if="briefing.payload.recommended_actions?.length" data-pdf-block class="rounded-lg bg-indigo-50 dark:bg-indigo-950 border border-indigo-200 dark:border-indigo-800 p-5 mt-4">
        <p class="text-sm uppercase tracking-wider font-semibold text-indigo-900 dark:text-indigo-200 mb-2">Recommended actions</p>
        <ol class="list-decimal pl-5 space-y-1 text-indigo-950 dark:text-indigo-200">
          <li v-for="(a, i) in briefing.payload.recommended_actions" :key="i" class="text-sm">{{ a }}</li>
        </ol>
      </aside>
    </article>
  </div>
</template>

<script setup lang="ts">
import { stripLeadingNumber } from '~/utils/stripLeadingNumber'

const props = defineProps<{ briefingId: number }>()
const { briefing, loading, error } = useBriefing(props.briefingId)

const articleRef = ref<HTMLElement | null>(null)
const { exporting, markWidgetLoaded, resetWidgets, exportPdf } = useBriefingPdf()

const expectedWidgets = computed(
  () => briefing.value?.payload?.sections.filter((s) => s.widget_id).length ?? 0,
)

// briefingId is a prop that may change without remount — reset the widget counter.
watch(() => props.briefingId, () => resetWidgets())

async function onExportPdf() {
  if (!briefing.value?.payload || !articleRef.value) return
  await exportPdf(articleRef.value, briefing.value.payload.headline, expectedWidgets.value)
}

function deltaClass(dir?: 'up' | 'down' | 'flat' | null) {
  if (dir === 'up') return 'text-emerald-600'
  if (dir === 'down') return 'text-rose-600'
  return 'text-neutral-500'
}

function formatRange(b: any) {
  if (!b.date_range_from || !b.date_range_to) return ''
  const from = new Date(b.date_range_from).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  const to = new Date(b.date_range_to).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  return `${from} – ${to}`
}

function formatDate(s: string) {
  return new Date(s).toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>
