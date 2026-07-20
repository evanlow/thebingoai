<template>
  <div class="h-full flex flex-col bg-white dark:bg-neutral-900">
    <!-- Back to originating dashboard — mirrors the chat briefing back bar; visible once dashboard_id is known -->
    <div
      v-if="briefing?.dashboard_id"
      data-pdf-ignore="true"
      class="flex items-center gap-2 px-4 py-2 border-b border-[var(--line)] flex-shrink-0"
    >
      <button
        data-testid="briefing-back"
        class="text-sm text-[var(--ink-2)] hover:text-[var(--ink-0)] flex items-center gap-1"
        @click="goBack"
      >
        <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        Back to dashboard
      </button>
    </div>

    <div class="flex-1 overflow-y-auto">
    <!-- Loading skeleton -->
    <div v-if="loading" class="max-w-3xl mx-auto px-6 py-10 space-y-4">
      <div class="h-3 w-40 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
      <div class="h-10 w-3/4 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
      <div class="h-4 w-full bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
      <div class="h-4 w-5/6 bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
    </div>

    <!-- API error / not found (briefing is null) -->
    <div v-else-if="!briefing && error" class="max-w-3xl mx-auto px-6 py-10">
      <div class="rounded-lg border border-rose-200 dark:border-rose-900/60 bg-rose-50 dark:bg-rose-950/40 p-6">
        <h2 class="text-lg font-semibold text-rose-900 dark:text-rose-200 mb-2">Could not load briefing</h2>
        <p class="text-sm text-rose-700 dark:text-rose-300">{{ error }}</p>
      </div>
    </div>

    <!-- Failed (briefing exists but status is failed) -->
    <div v-else-if="briefing.status === 'failed'" class="max-w-3xl mx-auto px-6 py-10">
      <div class="rounded-lg border border-rose-200 dark:border-rose-900/60 bg-rose-50 dark:bg-rose-950/40 p-6">
        <h2 class="text-lg font-semibold text-rose-900 dark:text-rose-200 mb-2">Briefing failed</h2>
        <p class="text-sm text-rose-700 dark:text-rose-300 mb-4">{{ briefing.error || 'Unknown error.' }}</p>
        <button class="px-3 py-1.5 rounded bg-rose-600 text-white text-sm" @click="retry">Retry</button>
      </div>
    </div>

    <!-- Generating (briefing exists but payload not written yet) — useBriefing polls every 3s -->
    <div v-else-if="!briefing.payload" class="max-w-3xl mx-auto px-6 py-10 space-y-4">
      <p class="text-sm uppercase tracking-wider text-neutral-500">Generating your briefing…</p>
      <div class="h-10 w-3/4 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
      <div class="h-4 w-full bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
      <div class="h-4 w-5/6 bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
      <div class="h-4 w-2/3 bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
    </div>

    <!-- Ready -->
    <article v-else ref="articleRef" class="max-w-3xl mx-auto px-6 py-10">
      <div data-pdf-ignore="true" class="flex justify-end gap-2 mb-6">
        <button
          class="text-sm px-3 py-1 rounded-full border border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="exporting"
          @click="onExportPdf"
        >
          {{ exporting ? 'Generating…' : 'Export PDF' }}
        </button>
        <button
          data-testid="briefing-share-toggle"
          class="text-sm px-3 py-1 rounded-full border transition-colors disabled:opacity-50"
          :class="shareUrl || shareActive
            ? 'border-emerald-300 dark:border-emerald-700 text-emerald-700 dark:text-emerald-400'
            : 'border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800'"
          :disabled="sharing"
          @click="shareUrl ? copyShareUrl() : enableSharing()"
        >
          <!-- 'Shared · New link' (not 'Copy link'): after a reload the raw token
               is unrecoverable (hashed at rest), so clicking mints a new link —
               the label says so instead of silently rotating. -->
          {{ shareUrl ? 'Shared · Copy link' : shareActive ? 'Shared · New link' : 'Share to web' }}
        </button>
      </div>
      <p v-if="shareError" data-pdf-ignore="true" class="text-sm text-rose-600 mb-4 text-right">
        {{ shareError }}
      </p>
      <p v-if="shareUrl || shareActive" data-pdf-ignore="true" class="text-sm text-neutral-500 mb-4 text-right">
        <!-- The URL is rendered as selectable text on purpose: clipboard write can
             fail (permission denied) or silently no-op (non-secure context), and
             this is then the owner's only way to retrieve the link. -->
        <span
          v-if="shareUrl"
          data-testid="briefing-share-url"
          class="block select-all break-all text-neutral-600 dark:text-neutral-400"
        >{{ shareUrl }}</span>
        Anyone with the link can read this briefing.
        <button class="underline hover:text-neutral-700" :disabled="sharing" @click="disableSharing">Turn off</button>
      </p>

      <BriefingBody
        :payload="briefing.payload!"
        :context-label="contextLabel"
        :created-at="briefing.created_at"
        :dashboard-id="briefing.dashboard_id"
        @loaded="markWidgetLoaded"
      />
    </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { trackEvent } from '~/utils/analytics'

const route = useRoute()
const briefingId = computed(() => parseInt(route.params.id as string))
const { briefing, loading, error, refresh } = useBriefing(briefingId)
const articleRef = ref<HTMLElement | null>(null)
const { exporting, markWidgetLoaded, resetWidgets, exportPdf } = useBriefingPdf()

function goBack() {
  if (briefing.value?.dashboard_id) navigateTo('/dashboard?id=' + briefing.value.dashboard_id)
}

const expectedWidgets = computed(
  () => briefing.value?.payload?.sections.filter((s) => s.widget_id).length ?? 0,
)

// The page component is reused across briefing ids (not remounted), so the
// embedded widgets remount and re-emit @loaded — reset the counter to match.
watch(briefingId, () => resetWidgets())

async function onExportPdf() {
  if (!briefing.value?.payload || !articleRef.value) return
  await exportPdf(articleRef.value, briefing.value.payload.headline, expectedWidgets.value)
}

const contextLabel = computed(() => {
  const b = briefing.value
  if (!b) return ''
  const range = b.date_range_from ? ` · ${formatRange(b)}` : ''
  return `Dashboard #${b.dashboard_id}${range}`
})

function formatRange(b: any) {
  if (!b.date_range_from || !b.date_range_to) return ''
  const from = new Date(b.date_range_from).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  })
  const to = new Date(b.date_range_to).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
  return `${from} – ${to}`
}

const shareUrl = ref<string | null>(null)
const shareError = ref<string | null>(null)
const sharing = ref(false)
// A share row exists server-side. Distinct from shareUrl: the raw token is
// hashed at rest, so after a reload we can know sharing is ON but never
// reconstruct the URL.
const shareActive = ref(false)

// Hydrate share status per briefing id. Also the reset that keeps stale share
// state from leaking across ids when the page component is reused (see the
// resetWidgets() watcher above).
watch(
  briefingId,
  async (id) => {
    shareUrl.value = null
    shareError.value = null
    shareActive.value = false
    if (!id) return
    try {
      const { fetchWithRefresh } = useApi()
      const resp = await fetchWithRefresh(`/api/briefings/${id}/share`, { method: 'GET' })
      if (briefingId.value !== id) return // navigated away mid-flight — stale response
      shareActive.value = !!resp?.active
    } catch {
      // Status probe only — on failure the button just reads 'Share to web'.
    }
  },
  { immediate: true },
)

async function copyShareUrl() {
  if (!shareUrl.value) return
  try {
    await navigator.clipboard?.writeText(shareUrl.value)
  } catch {
    // Clipboard permission denied — the URL is still shown on screen.
  }
}

async function enableSharing() {
  if (!briefing.value) return
  if (sharing.value) return
  const id = briefing.value.id
  sharing.value = true
  shareError.value = null
  try {
    const { fetchWithRefresh } = useApi()
    const resp = await fetchWithRefresh(`/api/briefings/${id}/share`, {
      method: 'POST',
    })
    // Navigated to another briefing while the POST was in flight: applying the
    // response now would show (and copy) briefing A's link on briefing B.
    if (briefingId.value !== id) return
    // No server-built URL in the response: the browser already knows its own
    // origin. Mirrors stores/auth.ts's window.location.origin pattern for
    // our-own-app URLs handed to a user — no env var can be wrong or forgotten.
    // The token rides in the FRAGMENT, not the path: fragments never leave the
    // browser, so the raw credential stays out of server/proxy access logs and
    // Referer headers. The share page reads it from location.hash.
    shareUrl.value = `${window.location.origin}/share/briefings#${resp.token}`
    shareActive.value = true
    try {
      await navigator.clipboard?.writeText(shareUrl.value)
    } catch {
      // Clipboard denial is not a share failure: the link was created and is
      // shown on screen. Surfacing it as shareError invited a re-click, which
      // rotates the token and kills the link that just succeeded.
    }
  } catch (e: any) {
    // The 400 here is the fail-closed guard: a briefing without widget_snapshots
    // can't be shared, because the public view would otherwise live-query.
    shareError.value = e?.data?.detail || 'Could not create a share link.'
  } finally {
    sharing.value = false
  }
}

async function disableSharing() {
  if (!briefing.value) return
  if (sharing.value) return
  const id = briefing.value.id
  sharing.value = true
  shareError.value = null
  try {
    const { fetchWithRefresh } = useApi()
    await fetchWithRefresh(`/api/briefings/${id}/share`, { method: 'DELETE' })
    if (briefingId.value !== id) return // navigated away mid-flight — stale response
    shareUrl.value = null
    shareError.value = null
    shareActive.value = false
  } catch (e: any) {
    shareError.value = e?.data?.detail || 'Could not turn off sharing.'
  } finally {
    sharing.value = false
  }
}

async function retry() {
  if (!briefing.value) return
  const { fetchWithRefresh } = useApi()
  const resp = await fetchWithRefresh(`/api/dashboards/${briefing.value.dashboard_id}/brief`, {
    method: 'POST',
  })
  trackEvent('briefing_create', { dashboard_id: briefing.value.dashboard_id })
  if (resp?.briefing_id && resp.briefing_id !== briefing.value.id) {
    await navigateTo(`/briefings/${resp.briefing_id}`)
  } else {
    await refresh()
  }
}

</script>
