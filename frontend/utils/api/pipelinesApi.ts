export interface PipelineScheduleTable {
  source_table: string
  target_table: string
  mode: string
  incremental_key: string | null
  unique_key: string[] | null
  enabled: boolean
}

export interface PipelineSchedule {
  id: string
  name: string | null
  cron: string | null
  timezone: string
  enabled: boolean
  next_run_at: string | null
  tables: PipelineScheduleTable[]
}

export interface Pipeline {
  id: string
  name: string
  source_connection_id: number
  owner_scope_kind: string
  owner_scope_id: string
  target_table: string | null
  cron: string | null
  timezone: string
  mode: string
  incremental_key: string | null
  extraction_config: Record<string, any>
  pipeline_fingerprint: string
  last_run_at: string | null
  last_run_status: string | null
  next_run_at: string | null
  enabled: boolean
  created_by_user_id: string
  created_at?: string | null
  updated_at?: string | null
  schedules?: PipelineSchedule[]
}

export interface ScheduleUpdate {
  cron?: string | null
  timezone?: string | null
  enabled?: boolean
  tables?: string[]
}

export interface PipelineCreate {
  name: string
  source_connection_id: number
  owner_scope_kind?: string
  owner_scope_id: string
  target_table: string
  cron?: string | null
  timezone?: string | null
  mode?: string
  incremental_key?: string | null
  extraction_config?: Record<string, any>
}

export interface PipelineUpdate {
  // Mirrors backend PipelineUpdate. Schedule + enabled + name + cursor overrides.
  // Passing incremental_key='' (empty string) explicitly clears the cursor.
  // Switching mode to 'incremental' requires a non-empty cursor in the same call.
  // Changing source tables still requires delete + recreate.
  name?: string
  cron?: string | null
  timezone?: string | null
  enabled?: boolean
  mode?: 'full' | 'incremental'
  incremental_key?: string | null
}

export function createPipelinesApi(fetchWithRefresh: Function) {
  return {
    async list(): Promise<Pipeline[]> {
      return fetchWithRefresh('/api/pipelines', {})
    },
    async listForConnection(connectionId: number): Promise<Pipeline[]> {
      // Server endpoint doesn't filter; we filter client-side. Lists are small.
      const all: Pipeline[] = await fetchWithRefresh('/api/pipelines', {})
      const filtered = all.filter((p) => p.source_connection_id === connectionId)
      // Prefer new-model pipelines (have schedules) over legacy rows. Falls back
      // to newest-first within each group. SettingsConnectionSync picks list[0].
      return [...filtered].sort((a, b) => {
        const aNew = (a.schedules?.length ?? 0) > 0 ? 1 : 0
        const bNew = (b.schedules?.length ?? 0) > 0 ? 1 : 0
        if (aNew !== bNew) return bNew - aNew
        return new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime()
      })
    },
    async get(id: string): Promise<Pipeline> {
      return fetchWithRefresh(`/api/pipelines/${id}`, {})
    },
    async create(data: PipelineCreate): Promise<Pipeline> {
      return fetchWithRefresh('/api/pipelines', {
        method: 'POST',
        body: data,
      })
    },
    async update(id: string, data: PipelineUpdate): Promise<Pipeline> {
      return fetchWithRefresh(`/api/pipelines/${id}`, {
        method: 'PATCH',
        body: data,
      })
    },
    async updateSchedule(pipelineId: string, scheduleId: string, data: ScheduleUpdate): Promise<Pipeline> {
      return fetchWithRefresh(`/api/pipelines/${pipelineId}/schedules/${scheduleId}`, {
        method: 'PATCH',
        body: data,
      })
    },
    async delete(id: string): Promise<void> {
      return fetchWithRefresh(`/api/pipelines/${id}`, {
        method: 'DELETE',
      })
    },
    async run(id: string): Promise<{ run_id: string; status: string }> {
      return fetchWithRefresh(`/api/pipelines/${id}/run`, {
        method: 'POST',
      })
    },
    async redetectWatermark(id: string): Promise<Pipeline> {
      return fetchWithRefresh(`/api/pipelines/${id}/redetect-watermark`, {
        method: 'POST',
      })
    },
    async loadHistory(id: string, since: string): Promise<{ run_id: string; status: string; since: string }> {
      return fetchWithRefresh(`/api/pipelines/${id}/load-history`, {
        method: 'POST',
        body: { since },
      })
    },
  }
}
