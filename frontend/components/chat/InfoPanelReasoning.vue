<template>
  <div
    class="shrink-0 flex flex-col"
    :class="[
      fullHeight ? 'flex-1' : 'border-t border-gray-200 dark:border-neutral-800 bg-gray-50/50 dark:bg-neutral-800/30',
      isOpen && !fullHeight ? 'max-h-[60%]' : '',
      isOpen && fullHeight ? 'flex-1' : '',
    ]"
  >
    <!-- Header -->
    <button
      @click="chatStore.toggleInfoSection('reasoning')"
      class="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-100/50 dark:hover:bg-neutral-800/50 transition-colors shrink-0"
    >
      <div class="flex items-center gap-1.5">
        <span class="text-sm uppercase tracking-wider text-gray-400 dark:text-neutral-500 font-semibold">Log</span>
        <span v-if="stepCount > 0" class="text-sm bg-gray-200/70 dark:bg-neutral-700 text-gray-500 dark:text-neutral-300 px-1.5 py-px rounded-full">
          {{ stepCount }} step{{ stepCount !== 1 ? 's' : '' }}
        </span>
      </div>
      <svg
        class="w-3 h-3 text-gray-300 transition-transform duration-200"
        :class="{ 'rotate-180': isOpen }"
        fill="none" viewBox="0 0 24 24" stroke="currentColor"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- Content -->
    <div v-show="isOpen" class="overflow-y-auto px-4 pb-3 font-mono text-sm">
      <!-- Empty state -->
      <div v-if="!selectedMessage || !steps.length" class="text-center py-4">
        <svg class="w-5 h-5 mx-auto text-gray-200 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.347.15A4.98 4.98 0 0112 17a4.98 4.98 0 01-2.39-.606l-.347-.15z" />
        </svg>
        <p class="text-sm text-gray-300 font-sans">
          {{ chatStore.isStreaming ? 'Agent is working...' : 'Click a message to see its reasoning' }}
        </p>
      </div>

      <!-- Tree view -->
      <ChatReasoningTree v-else-if="selectedMessage" :message="selectedMessage" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AgentStep } from '~/stores/chat'

withDefaults(defineProps<{
  fullHeight?: boolean
}>(), {
  fullHeight: false,
})

const chatStore = useChatStore()

const isOpen = computed(() => chatStore.infoPanelSections.reasoning)

const selectedMessage = computed(() => {
  const id = chatStore.selectedMessageId
  if (id) return chatStore.messages.find(m => m.id === id) || null
  const msgs = chatStore.messages
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant') return msgs[i]
  }
  return null
})

const steps = computed((): AgentStep[] => selectedMessage.value?.agent_steps || [])

const stepCount = computed(() => {
  const steps = selectedMessage.value?.agent_steps
  if (!steps?.length) return 0
  return steps.filter(s => s.step_type !== 'tool_result').length
})
</script>
