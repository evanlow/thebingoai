<template>
  <div class="section-widget-bar" :style="{ background: `var(--section-${color}-bar)` }">
    <input
      v-if="editMode"
      class="section-widget-input"
      :value="config.title"
      placeholder="Section name"
      @input="onTitle(($event.target as HTMLInputElement).value)"
      @click.stop
    />
    <span v-else class="section-widget-label">{{ config.title || 'Untitled section' }}</span>
  </div>
</template>

<script setup lang="ts">
import type { SectionWidgetConfig } from '~/types/dashboard'
import { sectionColorToken } from '~/types/dashboard'
import { useDashboardStore } from '~/stores/dashboard'

const props = defineProps<{
  widgetId: string
  config: SectionWidgetConfig
  editMode?: boolean
}>()

const store = useDashboardStore()
const color = computed(() => sectionColorToken(props.config.sectionColor))

function onTitle(title: string) {
  store.updateWidgetConfig(props.widgetId, { type: 'section', config: { ...props.config, title } })
}
</script>

<style scoped>
.section-widget-bar {
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-radius: 10px;
  /* Headroom above the bar creates the spacing between adjacent bands and
     the title padding from the band's top edge — geometry constants in
     useDashboardSections.ts are derived from this margin. */
  margin-top: 22px;
  height: calc(100% - 22px);
}

.section-widget-label,
.section-widget-input {
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 650;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--ink-0);
}

.section-widget-input {
  flex: 1;
  min-width: 0;
  background: transparent;
  border: none;
  outline: none;
  padding: 4px 0;
}
.section-widget-input::placeholder {
  color: var(--ink-2);
  text-transform: none;
  letter-spacing: normal;
  font-weight: 500;
}
</style>
