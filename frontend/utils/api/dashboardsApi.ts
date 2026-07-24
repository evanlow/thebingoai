import { trackEvent } from '~/utils/analytics'

export function createDashboardsApi(fetchWithRefresh: Function) {
  return {
    async list() {
      return fetchWithRefresh('/api/dashboards', {})
    },
    async get(id: number, opts: { skeleton?: boolean } = {}) {
      // skeleton=1 → structure + columns only (no baked rows/data), so the
      // dashboard paints instantly on open; the live refresh fills widget data.
      const qs = opts.skeleton ? '?skeleton=1' : ''
      return fetchWithRefresh(`/api/dashboards/${id}${qs}`, {})
    },
    async create(data: any) {
      return fetchWithRefresh('/api/dashboards', {
        method: 'POST',
        body: data,
      })
    },
    async update(id: number, data: any) {
      return fetchWithRefresh(`/api/dashboards/${id}`, {
        method: 'PUT',
        body: data,
      })
    },
    async delete(id: number) {
      return fetchWithRefresh(`/api/dashboards/${id}`, {
        method: 'DELETE',
      })
    },
    async refreshWidget(data: { connection_id: number; sql: string; mapping: any; limit?: number; filters?: Array<{ column: string; op: string; value: any }>; dashboard_id?: number; widget_id?: string; widget_sources?: string[] }, signal?: AbortSignal) {
      return fetchWithRefresh('/api/dashboards/widgets/refresh', {
        method: 'POST',
        body: data,
        timeout: 120_000,  // match backend query budget; 60s default aborts slow source-DB queries
        signal,  // cancelled on navigation away / dashboard switch
      })
    },
    async refreshAll(dashboardId: number, filters?: Array<{ column: string; op: string; value: any }>, signal?: AbortSignal) {
      return fetchWithRefresh(`/api/dashboards/${dashboardId}/refresh`, {
        method: 'POST',
        body: { filters: filters ?? null },
        timeout: 120_000,  // match backend query budget; 60s default aborts slow source-DB queries
        signal,  // cancelled on navigation away / dashboard switch
      })
    },
    async suggestFix(data: { connection_id: number; sql: string; error_message: string; mapping: any; widget_title?: string; widget_description?: string }) {
      return fetchWithRefresh('/api/dashboards/widgets/suggest-fix', {
        method: 'POST',
        body: data,
      }) as Promise<{ suggested_sql: string; explanation: string }>
    },
    async setSchedule(id: number, data: { schedule_type: string; schedule_value: string; timezone?: string }) {
      return fetchWithRefresh(`/api/dashboards/${id}/schedule`, {
        method: 'PUT',
        body: data,
      })
    },
    async toggleSchedule(id: number, active: boolean) {
      return fetchWithRefresh(`/api/dashboards/${id}/schedule`, {
        method: 'PATCH',
        body: { schedule_active: active },
      })
    },
    async removeSchedule(id: number) {
      return fetchWithRefresh(`/api/dashboards/${id}/schedule`, {
        method: 'DELETE',
      })
    },
    async listRefreshRuns(id: number, limit = 20, offset = 0) {
      return fetchWithRefresh(`/api/dashboards/${id}/schedule/runs?limit=${limit}&offset=${offset}`, {})
    },
    async triggerRefresh(id: number) {
      return fetchWithRefresh(`/api/dashboards/${id}/schedule/run`, {
        method: 'POST',
      })
    },
    async getSqliteUrl(connectionId: number) {
      return fetchWithRefresh(`/api/connections/datasets/${connectionId}/sqlite-url`, {}) as Promise<{ url: string; expires_in: number }>
    },
    async brief(id: number) {
      const resp = await (fetchWithRefresh(`/api/dashboards/${id}/brief`, {
        method: 'POST',
      }) as Promise<{ briefing_id: number; status: string }>)
      trackEvent('briefing_create', { dashboard_id: id })
      return resp
    },
    async getBriefSchedule(id: number) {
      return fetchWithRefresh(`/api/dashboards/${id}/analysis-schedule`, {}) as Promise<
        { schedule_type: string; schedule_value: string; is_active: boolean } | null
      >
    },
    async setBriefSchedule(id: number, data: { schedule_type: string; schedule_value: string; timezone?: string }) {
      return fetchWithRefresh(`/api/dashboards/${id}/analysis-schedule`, {
        method: 'POST',
        body: data,
      })
    },
    async removeBriefSchedule(id: number) {
      return fetchWithRefresh(`/api/dashboards/${id}/analysis-schedule`, {
        method: 'DELETE',
      })
    },
  }
}
