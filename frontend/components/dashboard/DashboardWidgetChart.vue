<template>
  <div class="flex h-full flex-col p-3" :style="wrapperStyle">
    <div v-if="showTitleFromOptions" class="mb-2 flex-shrink-0">
      <span class="widget-label">{{ config.title }}</span>
    </div>
    <div class="relative min-h-0 flex-1">
      <DashboardWidgetFunnel v-if="config.type === 'funnel'" :config="config" />
      <DashboardWidgetTimeline v-else-if="config.type === 'timeline'" :config="config" />
      <canvas v-else ref="canvasRef" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChartWidgetConfig } from '~/types/dashboard'
import { useChart } from '~/composables/useChart'

const props = defineProps<{
  config: ChartWidgetConfig
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const configRef = computed(() => props.config)

useChart(canvasRef, configRef)

// Title is shown by the chart's own title plugin when showTitle is set;
// the legacy `config.title` label above the canvas is only shown when
// showTitle is NOT explicitly configured (backward-compat).
const showTitleFromOptions = computed(() => {
  const opts = props.config.options
  if (opts?.showTitle !== undefined) return false
  return !!(props.config.title)
})

const wrapperStyle = computed(() => {
  const opts = props.config.options
  if (!opts) return {}
  const style: Record<string, string> = {}
  if (opts.backgroundColor) style.background = opts.backgroundColor
  if (opts.opacity !== undefined) style.opacity = String(opts.opacity / 100)
  if (opts.borderColor && opts.borderStyle && opts.borderStyle !== 'none') {
    style.border = `${opts.borderWidth ?? 1}px ${opts.borderStyle} ${opts.borderColor}`
  }
  if (opts.borderRadius) style.borderRadius = `${opts.borderRadius}px`
  if (opts.addBorderShadow) style.boxShadow = '2px 2px 6px rgba(0,0,0,0.15)'
  return style
})
</script>
