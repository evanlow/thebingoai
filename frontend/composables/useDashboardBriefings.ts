// Per-dashboard briefings list, cached and shared per dashboard id. Backs the
// dashboard's "Previous briefs" button + panel. Separate from useBriefingsList
// (the global, unscoped list used by the chat briefings tab).

import type { BriefingResponse } from './useBriefing'

export function useDashboardBriefings(dashboardId: number) {
  const { fetchWithRefresh } = useApi()
  const key = `dashboard-briefings-${dashboardId}`

  const briefings = useState<BriefingResponse[]>(key, () => [])
  const loaded = useState<boolean>(`${key}-loaded`, () => false)
  const loading = useState<boolean>(`${key}-loading`, () => false)
  const error = useState<string>(`${key}-error`, () => '')
  const inflight = useState<Promise<void> | null>(`${key}-inflight`, () => null)

  async function refresh(): Promise<void> {
    if (inflight.value) return inflight.value
    loading.value = true
    const p = (async () => {
      try {
        const data = (await fetchWithRefresh(
          `/api/briefings?dashboard_id=${dashboardId}&limit=50`,
          { method: 'GET' },
        )) as BriefingResponse[]
        briefings.value = data || []
        loaded.value = true
        error.value = ''
      } catch (e: any) {
        error.value = e?.message || 'Failed to load briefings'
      } finally {
        loading.value = false
        inflight.value = null
      }
    })()
    inflight.value = p
    return p
  }

  function ensure(): void {
    if (loaded.value || inflight.value) return
    refresh()
  }

  return { briefings, loaded, loading, error, refresh, ensure }
}
