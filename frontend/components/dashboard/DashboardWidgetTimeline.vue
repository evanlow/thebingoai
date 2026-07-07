<template>
  <div class="tl">
    <div v-if="!lanes.length" class="tl-empty">No data</div>
    <template v-else>
      <div class="tl-body">
        <div
          v-for="(lane, li) in lanes"
          :key="li"
          class="tl-lane"
          :class="{ 'tl-lane-alt': altRows && li % 2 === 1 }"
        >
          <div class="tl-rowlabel" :title="lane.label">{{ lane.label }}</div>
          <div class="tl-track">
            <div
              v-for="(bar, bi) in lane.bars"
              :key="bi"
              class="tl-bar"
              :style="{ left: bar.left + '%', width: bar.width + '%', background: bar.color }"
              :title="bar.tip"
            >
              <span class="tl-barlabel">{{ bar.label }}</span>
            </div>
          </div>
        </div>
      </div>
      <div class="tl-axis">
        <span class="tl-rowlabel" />
        <div class="tl-axis-scale">
          <span>{{ domainLabels.min }}</span>
          <span>{{ domainLabels.max }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChartWidgetConfig } from '~/types/dashboard'

interface TimelineRow {
  rowLabel: string
  barLabel?: string | null
  start: string | number
  end: string | number
  tooltip?: string | null
}

const props = defineProps<{ config: ChartWidgetConfig }>()

const PALETTE = ['#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f97316', '#eab308', '#22c55e', '#06b6d4']

function ts(v: unknown): number {
  if (v == null) return NaN
  const t = Date.parse(String(v))
  return Number.isNaN(t) ? NaN : t
}
function fmtDate(t: number): string {
  return new Date(t).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

const rows = computed(() => {
  const raw = ((props.config.data as any)?.rows ?? []) as TimelineRow[]
  return raw
    .map(r => ({ ...r, s: ts(r.start), e: ts(r.end) }))
    .filter(r => Number.isFinite(r.s) && Number.isFinite(r.e) && r.e >= r.s)
})

const domain = computed(() => {
  const all = rows.value
  if (!all.length) return { min: 0, max: 1 }
  const min = Math.min(...all.map(r => r.s))
  const max = Math.max(...all.map(r => r.e))
  return { min, max: max === min ? min + 1 : max }
})

const domainLabels = computed(() => ({ min: fmtDate(domain.value.min), max: fmtDate(domain.value.max) }))

const lanes = computed(() => {
  const opts = props.config.options ?? {}
  const grouped = opts.timelineGroupByRowLabel ?? false
  const colorBy = opts.timelineColorBy ?? 'row'
  const { min, max } = domain.value
  const span = max - min || 1

  // Stable palette index per distinct color key.
  const keyIndex = new Map<string, number>()
  const colorFor = (key: string) => {
    if (!keyIndex.has(key)) keyIndex.set(key, keyIndex.size)
    return PALETTE[keyIndex.get(key)! % PALETTE.length]
  }

  const mkBar = (r: typeof rows.value[number]) => {
    const left = ((r.s - min) / span) * 100
    const width = Math.max(((r.e - r.s) / span) * 100, 0.8)
    const label = r.barLabel ?? r.rowLabel
    const colorKey = colorBy === 'bar' ? String(r.barLabel ?? r.rowLabel) : String(r.rowLabel)
    const tip = [
      `${r.rowLabel}`,
      r.barLabel ? `${r.barLabel}` : '',
      `${fmtDate(r.s)} → ${fmtDate(r.e)}`,
      r.tooltip ? `${r.tooltip}` : '',
    ].filter(Boolean).join('\n')
    return { left, width, label, color: colorFor(colorKey), tip }
  }

  if (grouped) {
    // One lane per distinct row label; all matching bars share the lane.
    const order: string[] = []
    const byLabel = new Map<string, typeof rows.value>()
    for (const r of rows.value) {
      const k = String(r.rowLabel)
      if (!byLabel.has(k)) { byLabel.set(k, []); order.push(k) }
      byLabel.get(k)!.push(r)
    }
    return order.map(label => ({ label, bars: byLabel.get(label)!.map(mkBar) }))
  }

  // One lane per record.
  return rows.value.map(r => ({ label: String(r.rowLabel), bars: [mkBar(r)] }))
})

const altRows = computed(() => props.config.options?.timelineAltRows ?? false)
</script>

<style scoped>
.tl {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  font-size: 12px;
}
.tl-body {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
}
.tl-lane {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 26px;
  padding: 2px 0;
}
.tl-lane-alt { background: var(--paper-1, rgba(0, 0, 0, 0.025)); }
.tl-rowlabel {
  flex: 0 0 100px;
  width: 100px;
  padding-left: 4px;
  color: var(--ink-2, #4b5563);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tl-track {
  position: relative;
  flex: 1 1 auto;
  height: 20px;
}
.tl-bar {
  position: absolute;
  top: 2px;
  bottom: 2px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  padding: 0 6px;
  min-width: 3px;
  overflow: hidden;
}
.tl-barlabel {
  font-size: 11px;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}
.tl-axis {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  border-top: 1px solid var(--line, #e5e7eb);
  padding-top: 3px;
  margin-top: 2px;
}
.tl-axis-scale {
  flex: 1 1 auto;
  display: flex;
  justify-content: space-between;
  color: var(--ink-3, #9ca3af);
  font-size: 10px;
}
.tl-empty {
  margin: auto;
  color: var(--ink-3, #9ca3af);
}
</style>
