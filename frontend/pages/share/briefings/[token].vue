<template>
  <div class="min-h-screen bg-white dark:bg-neutral-900">
    <div v-if="loading" class="max-w-3xl mx-auto px-6 py-10 space-y-4">
      <div class="h-3 w-40 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
      <div class="h-10 w-3/4 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
      <div class="h-4 w-full bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
    </div>

    <div v-else-if="!payload" class="max-w-3xl mx-auto px-6 py-10">
      <div class="rounded-lg border border-neutral-200 dark:border-neutral-700 p-6 text-center">
        <h2 class="text-lg font-semibold text-neutral-900 dark:text-neutral-100 mb-2">
          This link isn't available
        </h2>
        <p class="text-sm text-neutral-600 dark:text-neutral-400">
          It may have been turned off by its owner.
        </p>
      </div>
    </div>

    <article v-else class="max-w-3xl mx-auto px-6 py-10">
      <BriefingBody
        :payload="payload"
        :context-label="payload.dashboard_name || 'Briefing'"
        :created-at="payload.created_at"
        :widgets="payload.widgets"
      />
      <p class="mt-10 pt-6 border-t border-neutral-100 dark:border-neutral-800 text-center text-sm text-neutral-400">
        Compiled by Bingo
      </p>
    </article>
  </div>
</template>

<script setup lang="ts">
// Anonymous by design. `middleware/auth.ts` is a NAMED middleware, not `.global`,
// so it only runs on pages that opt in with `middleware: 'auth'` — this page does
// not, which is the whole reason a stranger can open it.
// NEVER add `middleware: 'auth'` here: it would redirect the anonymous visitors
// this page exists for.
// `layout: 'blank'` (a <slot/> passthrough) keeps the app shell out. Do NOT
// switch this to a falsy layout — that bypasses <NuxtLayout> and strands the
// leaving page's subtree in the DOM when navigating into a layouted page under
// the out-in page transition. See __tests__/pages/layout-no-false.test.ts — the
// regression guard, which greps page files, so don't write the literal form here.
// This page reads one public endpoint and renders stored JSON — never an authed API.
definePageMeta({ layout: 'blank' })

const route = useRoute()
const payload = ref<any>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    payload.value = await $fetch(`/api/public/briefings/${route.params.token}`)
  } catch {
    // 404 / revoked / never existed all look the same on purpose — do not
    // confirm token guesses.
    payload.value = null
  } finally {
    loading.value = false
  }
})
</script>
