<template>
  <div
    :class="[bgClass, textClass, sizeClass, 'rounded-lg flex items-center justify-center shrink-0']"
    v-html="iconHtml"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  dbType: string
  iconHtml?: string
  size?: 'sm' | 'md'
}

const props = withDefaults(defineProps<Props>(), { size: 'md' })

const BG_CLASSES: Record<string, string> = {
  postgres:     'bg-blue-100 dark:bg-blue-900/30',
  mysql:        'bg-cyan-100 dark:bg-cyan-900/30',
  bigquery:     'bg-blue-100 dark:bg-blue-900/30',
  snowflake:    'bg-sky-100 dark:bg-sky-900/30',
  redshift:     'bg-red-100 dark:bg-red-900/30',
  clickhouse:   'bg-yellow-100 dark:bg-yellow-900/30',
  sqlite:       'bg-sky-100 dark:bg-sky-900/30',
  dataset:      'bg-gray-100 dark:bg-neutral-800',
  facebook_ads: 'bg-blue-100 dark:bg-blue-900/30',
  notion:       'bg-gray-100 dark:bg-neutral-800',
  google_sheets: 'bg-green-100 dark:bg-green-900/30',
}

// currentColor for monochrome connector glyphs (e.g. notion) so they invert per theme.
const TEXT_CLASSES: Record<string, string> = {
  notion: 'text-neutral-900 dark:text-white',
}

const bgClass  = computed(() => BG_CLASSES[props.dbType] ?? 'bg-gray-100 dark:bg-neutral-800')
const textClass = computed(() => TEXT_CLASSES[props.dbType] ?? '')
const sizeClass = computed(() => props.size === 'sm' ? 'h-8 w-8 p-1.5' : 'h-9 w-9 p-2')
</script>
