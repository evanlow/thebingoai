<template>
  <div class="funnel">
    <div
      v-for="(seg, i) in segments"
      :key="i"
      class="funnel-seg"
    >
      <div
        class="funnel-bar"
        :style="{ background: seg.color, clipPath: seg.clip }"
      />
      <div class="funnel-label">
        <span class="funnel-dim">{{ seg.label }}</span>
        <span v-if="seg.text" class="funnel-val">{{ seg.text }}</span>
      </div>
    </div>
    <div v-if="!segments.length" class="funnel-empty">No data</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChartWidgetConfig } from '~/types/dashboard'

const props = defineProps<{ config: ChartWidgetConfig }>()

// Same palette as useChart's DEFAULT_PALETTE so funnel matches other charts.
const PALETTE = ['#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f97316', '#eab308', '#22c55e', '#06b6d4']

function fmtNumber(v: number): string {
  return Number.isFinite(v) ? v.toLocaleString() : String(v)
}

const segments = computed(() => {
  const opts = props.config.options ?? {}
  const labels = (props.config.data?.labels ?? []) as string[]
  const values = ((props.config.data?.datasets?.[0]?.data ?? []) as number[]).map(v => Number(v) || 0)

  // Pair label+value, then sort by value (default desc — biggest stage on top).
  let pairs = labels.map((label, i) => ({ label, value: values[i] ?? 0 }))
  const sortBy = opts.sortBy
  const dir = opts.sortDirection ?? 'desc'
  if (sortBy === 'label') {
    pairs.sort((a, b) => dir === 'asc' ? String(a.label).localeCompare(String(b.label)) : String(b.label).localeCompare(String(a.label)))
  } else if (sortBy === 'value' || sortBy === undefined || sortBy === 'none') {
    // Funnels read top-to-bottom largest→smallest by default.
    pairs.sort((a, b) => dir === 'asc' ? a.value - b.value : b.value - a.value)
  }

  const maxVal = Math.max(...pairs.map(p => p.value), 0) || 1
  const shape = opts.funnelShape ?? 'smoothed'
  const labelMode = opts.funnelLabelMode ?? 'numberPercentage'
  const pctType = opts.funnelPercentType ?? 'max'
  const colorMode = opts.funnelColorMode ?? 'byValue'

  const fracs = pairs.map(p => p.value / maxVal)

  return pairs.map((p, i) => {
    const topFrac = fracs[i]
    // Smoothed bars taper toward the next (smaller) stage; stepped stay rectangular.
    const botFrac = shape === 'stepped' ? topFrac : (fracs[i + 1] ?? topFrac)
    const tl = (50 - 50 * topFrac).toFixed(2)
    const tr = (50 + 50 * topFrac).toFixed(2)
    const bl = (50 - 50 * botFrac).toFixed(2)
    const br = (50 + 50 * botFrac).toFixed(2)
    const clip = `polygon(${tl}% 0, ${tr}% 0, ${br}% 100%, ${bl}% 100%)`

    const color = colorMode === 'single'
      ? PALETTE[0]
      : PALETTE[i % PALETTE.length]

    // Percentage basis: % of max (vs largest) or % of previous stage.
    const basis = pctType === 'previous' ? (pairs[i - 1]?.value ?? p.value) : maxVal
    const pct = basis ? (p.value / basis) * 100 : 0
    const pctStr = `${pct.toFixed(1)}%`
    let text = ''
    if (labelMode === 'number') text = fmtNumber(p.value)
    else if (labelMode === 'percentage') text = pctStr
    else text = `${fmtNumber(p.value)} · ${pctStr}`

    return { label: p.label, text, color, clip }
  })
})
</script>

<style scoped>
.funnel {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  gap: 2px;
  padding: 4px 0;
}
.funnel-seg {
  position: relative;
  flex: 1 1 0;
  min-height: 0;
}
.funnel-bar {
  position: absolute;
  inset: 0;
  transition: clip-path 0.2s ease;
}
.funnel-label {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  pointer-events: none;
  font-size: 12px;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
  white-space: nowrap;
  overflow: hidden;
}
.funnel-dim { font-weight: 600; }
.funnel-val { opacity: 0.95; font-variant-numeric: tabular-nums; }
.funnel-empty {
  margin: auto;
  color: var(--ink-3, #9ca3af);
  font-size: 12px;
}
</style>
