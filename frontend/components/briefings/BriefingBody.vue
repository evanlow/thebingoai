<template>
  <div>
    <div data-pdf-block>
      <p class="text-sm uppercase tracking-wider text-neutral-500 mb-3">{{ contextLabel }}</p>

      <h1 class="font-serif text-4xl font-bold leading-tight text-neutral-900 dark:text-neutral-100 mb-5 tracking-tight">
        {{ payload.headline }}
      </h1>

      <div
        class="flex items-center gap-3 text-sm text-neutral-600 dark:text-neutral-400 mb-5 pb-4 border-b border-neutral-100 dark:border-neutral-800"
      >
        <div class="w-6 h-6 rounded-full bg-gradient-to-br from-indigo-500 to-pink-500" />
        <span><strong>Compiled by Bingo</strong> &middot; {{ formatDate(createdAt) }}</span>
      </div>

      <p class="text-lg leading-relaxed text-neutral-800 dark:text-neutral-200 mb-6">
        {{ payload.deck }}
      </p>
    </div>

    <div
      v-if="payload.kpis.length"
      data-pdf-block
      class="grid gap-3 p-4 bg-neutral-50 dark:bg-neutral-800 rounded-lg mb-7"
      :style="{ gridTemplateColumns: `repeat(${payload.kpis.length}, minmax(0,1fr))` }"
    >
      <div
        v-for="(k, i) in payload.kpis"
        :key="i"
        class="pl-3"
        :class="{ 'border-l border-neutral-200 dark:border-neutral-700': i > 0 }"
      >
        <div class="text-sm uppercase tracking-wide text-neutral-500">{{ k.label }}</div>
        <div class="text-2xl font-semibold mt-1 text-neutral-900 dark:text-neutral-100">{{ k.value }}</div>
        <div v-if="k.delta_vs_prev" class="text-sm mt-1" :class="deltaClass(k.delta_direction)">
          {{ k.delta_vs_prev }}
        </div>
      </div>
    </div>

    <section v-for="(s, idx) in payload.sections" :key="idx" data-pdf-block class="mb-7">
      <h2 class="font-serif text-2xl font-bold text-neutral-900 dark:text-neutral-100 mb-3">
        <span class="text-neutral-400 font-normal mr-2">{{ idx + 1 }}.</span>{{ stripLeadingNumber(s.heading) }}
      </h2>
      <div class="text-[15px] leading-relaxed text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap">
        {{ s.prose }}
      </div>
      <BriefingWidgetEmbed
        v-if="s.widget_id"
        :widget-id="s.widget_id"
        :dashboard-id="dashboardId"
        :widget="widgets?.[String(s.widget_id)]"
        :snapshot="payload.widget_snapshots?.[String(s.widget_id)]"
        class="mt-4"
        @loaded="emit('loaded')"
      />
    </section>

    <aside
      data-pdf-block
      class="rounded-lg bg-yellow-50 dark:bg-yellow-950 border border-yellow-200 dark:border-yellow-800 p-5 mt-4"
    >
      <p class="text-sm uppercase tracking-wider font-semibold text-yellow-900 dark:text-yellow-200 mb-2">
        Key takeaways
      </p>
      <ul class="list-disc pl-5 space-y-1 text-yellow-950 dark:text-yellow-200">
        <li v-for="(t, i) in payload.key_takeaways" :key="i" class="text-sm">{{ t }}</li>
      </ul>
    </aside>

    <aside
      v-if="payload.recommended_actions?.length"
      data-pdf-block
      class="rounded-lg bg-indigo-50 dark:bg-indigo-950 border border-indigo-200 dark:border-indigo-800 p-5 mt-4"
    >
      <p class="text-sm uppercase tracking-wider font-semibold text-indigo-900 dark:text-indigo-200 mb-2">
        Recommended actions
      </p>
      <ol class="list-decimal pl-5 space-y-1 text-indigo-950 dark:text-indigo-200">
        <li v-for="(a, i) in payload.recommended_actions" :key="i" class="text-sm">{{ a }}</li>
      </ol>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { stripLeadingNumber } from '~/utils/stripLeadingNumber'

defineProps<{
  payload: any
  contextLabel: string
  createdAt: string
  // Authed view only — the public view passes `widgets` instead.
  dashboardId?: number
  // Public view only: widget_id -> stripped widget shape, inlined by the
  // backend so no authed widget fetch is needed.
  widgets?: Record<string, any>
}>()

const emit = defineEmits<{ loaded: [] }>()

function deltaClass(dir?: 'up' | 'down' | 'flat' | null) {
  if (dir === 'up') return 'text-emerald-600'
  if (dir === 'down') return 'text-rose-600'
  return 'text-neutral-500'
}

function formatDate(s: string) {
  return new Date(s).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>
