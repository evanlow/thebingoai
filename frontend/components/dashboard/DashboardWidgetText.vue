<template>
  <div ref="wrapperRef" :class="[alignClass, editMode ? 'px-3 py-1 compact-text' : 'p-4']">
    <template v-if="isSection">
      <div class="section-header" :class="{ 'justify-center': config.alignment === 'center', 'justify-end': config.alignment === 'right' }">
        <span class="section-header-accent" :style="{ background: `var(--section-${sectionColorToken(config.sectionColor)}-line)` }" />
        <span class="section-header-title">{{ headerTitle }}</span>
      </div>
      <UiMarkdownRenderer v-if="headerBody" :content="headerBody" />
    </template>
    <UiMarkdownRenderer v-else :content="config.content" />
  </div>
</template>

<script setup lang="ts">
import type { TextWidgetConfig } from '~/types/dashboard'
import { sectionColorToken } from '~/types/dashboard'
import { sectionTitle } from '~/composables/useDashboardSections'

const props = defineProps<{
  widgetId: string
  config: TextWidgetConfig
  editMode?: boolean
}>()

const isSection = computed(() =>
  props.config.isSection ?? (props.config.content ?? '').trimStart().startsWith('#'),
)
const headerTitle = computed(() => sectionTitle(props.config.content))
const headerBody = computed(() =>
  (props.config.content ?? '').trimStart().split('\n').slice(1).join('\n').trim(),
)

const wrapperRef = ref<HTMLElement | null>(null)
const resizeWidget = inject<(id: string, h: number) => void>('resizeWidget')

// GridStack init constants — must match useDashboardGrid.ts
const CELL_HEIGHT = 70
const MARGIN = 4
const INSET = 4

function autoResize() {
  if (!wrapperRef.value || !resizeWidget) return
  const scrollH = wrapperRef.value.scrollHeight
  // overhead: inset*2 + one margin gap + pt-7 in edit mode
  const overhead = (INSET * 2 + MARGIN) + (props.editMode ? 28 : 0)
  const neededH = Math.max(2, Math.ceil((scrollH + overhead) / (CELL_HEIGHT + MARGIN)))
  resizeWidget(props.widgetId, neededH)
}

onMounted(() => nextTick(autoResize))
watch(() => [props.config.content, isSection.value], () => nextTick(autoResize))

const alignClass = computed(() => {
  switch (props.config.alignment) {
    case 'center': return 'text-center'
    case 'right': return 'text-right'
    default: return 'text-left'
  }
})
</script>

<style scoped>
.compact-text :deep(h1),
.compact-text :deep(h2),
.compact-text :deep(h3),
.compact-text :deep(h4) {
  margin-top: 0;
  margin-bottom: 0;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 28px;
}
.section-header-accent {
  width: 4px;
  height: 18px;
  border-radius: 2px;
  flex-shrink: 0;
}
.section-header-title {
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 650;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--ink-0);
}
</style>
