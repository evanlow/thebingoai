<template>
  <details :open="defaultOpen !== false" class="group/section">
    <summary class="flex cursor-pointer select-none items-center justify-between gap-2 list-none [&::-webkit-details-marker]:hidden">
      <h3 class="text-sm font-medium text-gray-500 dark:text-neutral-400 uppercase tracking-wide">{{ title }}</h3>
      <span class="flex items-center gap-2">
        <slot name="action" />
        <ChevronDown class="h-3.5 w-3.5 text-gray-400 dark:text-neutral-500 transition-transform group-open/section:rotate-180" />
      </span>
    </summary>
    <div class="mt-2" :class="bodyClass ?? 'space-y-2'">
      <slot />
    </div>
  </details>
</template>

<script setup lang="ts">
import { ChevronDown } from 'lucide-vue-next'

defineProps<{
  title: string
  defaultOpen?: boolean
  bodyClass?: string
}>()
</script>
