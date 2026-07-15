<template>
  <div class="section-bands" aria-hidden="true">
    <div
      v-for="section in sections"
      v-show="bounds[section.id]"
      :key="section.id"
      class="section-band"
      :style="bandStyle(section)"
    />
  </div>
</template>

<script setup lang="ts">
import type { DashboardSection, SectionBounds } from '~/composables/useDashboardSections'

const props = defineProps<{
  sections: DashboardSection[]
  bounds: Record<string, SectionBounds>
}>()

function bandStyle(section: DashboardSection) {
  const b = props.bounds[section.id]
  if (!b) return {}
  return {
    top: `${b.top}px`,
    height: `${b.height}px`,
    background: `var(--section-${section.color})`,
    borderColor: `var(--section-${section.color}-line)`,
  }
}
</script>

<style scoped>
.section-bands {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.section-band {
  position: absolute;
  left: 0;
  right: 0;
  border: 1px solid;
  border-radius: 14px;
  transition: top 0.2s ease, height 0.2s ease;
}
</style>
