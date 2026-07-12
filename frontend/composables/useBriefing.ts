/**
 * Composable for fetching and polling a briefing by ID.
 * Polls GET /api/briefings/{id} every 3s while status is 'generating'.
 * Stops when status becomes 'ready' or 'failed'.
 */

import { POLL_INTERVAL_MS } from './_chatConstants'
import { trackEvent } from '~/utils/analytics'

export interface BriefingKpi {
  label: string
  value: string
  delta_vs_prev?: string | null
  delta_direction?: 'up' | 'down' | 'flat' | null
}

export interface BriefingSection {
  heading: string
  prose: string
  widget_id?: string | number | null
}

export interface BriefingPayload {
  headline: string
  deck: string
  kpis: BriefingKpi[]
  sections: BriefingSection[]
  key_takeaways: string[]
  // Rendered widget configs keyed by widget_id, snapshot at generation time.
  // Absent on briefings generated before this shipped → embed refreshes live.
  widget_snapshots?: Record<string, any>
}

export interface BriefingResponse {
  id: number
  user_id: string
  dashboard_id: number
  dashboard_name: string | null
  source: string
  status: string
  payload: BriefingPayload | null
  error: string | null
  date_range_from: string | null
  date_range_to: string | null
  created_at: string
}

export function useBriefing(briefingId: number | Ref<number>) {
  const api = useApi()
  const id = computed(() => unref(briefingId))

  const briefing = ref<BriefingResponse | null>(null)
  const loading = ref(false)
  const error = ref('')

  let pollTimer: ReturnType<typeof setInterval> | null = null
  // Dedup briefing_view: polling + refresh() re-run fetch for the same id.
  let viewedId: number | null = null

  function stopPolling() {
    if (pollTimer !== null) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  async function fetch() {
    const currentId = id.value
    if (!currentId) return

    try {
      const result = await api.fetchWithRefresh(`/api/briefings/${currentId}`, {}) as BriefingResponse
      briefing.value = result
      loading.value = false
      error.value = ''

      if (result.status === 'ready' || result.status === 'failed') {
        stopPolling()
        // Credits are charged by briefing_runner when status flips to 'ready'.
        // Refresh the shared balance so the sidebar reflects the spend without
        // a page reload (mirrors chat refreshing on the 'done' SSE event).
        if (result.status === 'ready') {
          useCreditBalance().refresh()
          if (viewedId !== result.id) {
            viewedId = result.id
            trackEvent('briefing_view', { briefing_id: result.id, dashboard_id: result.dashboard_id })
          }
        }
      } else if (result.status === 'generating' && pollTimer === null) {
        pollTimer = setInterval(fetch, POLL_INTERVAL_MS)
      }
    } catch (e: any) {
      loading.value = false
      error.value = e?.message || 'Failed to load briefing'
      stopPolling()
    }
  }

  // Start fetching when briefingId becomes available
  watch(
    () => id.value,
    (newId) => {
      stopPolling()
      if (newId) {
        loading.value = true
        error.value = ''
        briefing.value = null
        fetch()
      }
    },
    { immediate: true },
  )

  onUnmounted(() => stopPolling())

  const refresh = fetch

  return { briefing, loading, error, refresh }
}
