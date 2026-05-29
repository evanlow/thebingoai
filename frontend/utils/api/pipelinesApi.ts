/**
 * Pipelines REST client. Mirrors `bingo/backend/pipelines/api.py` — see the
 * router for response shapes and validation rules.
 */

export interface PipelineRow {
  id: string
  name: string
  source_connection_id: number
  target_table: string
  cron: string | null
  timezone: string
  mode: 'full' | 'incremental'
  incremental_key: string | null
  unique_key: string[] | null
  extraction_config: Record<string, any>
  last_run_at: string | null
  last_run_status: string | null
  next_run_at: string | null
  enabled: boolean
}

export interface PipelineRunRow {
  id: string
  pipeline_id: string
  started_at: string
  finished_at: string | null
  status: string
  rows_written: number | null
  bytes_written: number | null
  error_message: string | null
  triggered_by: string
}

export interface RedetectResponse {
  pipeline_id: string
  table: string | null
  suggested_incremental_key: string | null
  current_incremental_key: string | null
  current_mode: string
}

export function createPipelinesApi(fetchWithRefresh: Function) {
  return {
    async list(): Promise<PipelineRow[]> {
      return fetchWithRefresh('/api/pipelines', {})
    },
    async get(id: string): Promise<PipelineRow> {
      return fetchWithRefresh(`/api/pipelines/${id}`, {})
    },
    async runs(id: string, limit = 20): Promise<PipelineRunRow[]> {
      return fetchWithRefresh(`/api/pipelines/${id}/runs?limit=${limit}`, {})
    },
    async run(id: string) {
      return fetchWithRefresh(`/api/pipelines/${id}/run`, { method: 'POST' })
    },
    async override(id: string, body: { mode?: string; incremental_key?: string | null }): Promise<PipelineRow> {
      return fetchWithRefresh(`/api/pipelines/${id}/override`, {
        method: 'PATCH',
        body,
      })
    },
    async redetect(id: string): Promise<RedetectResponse> {
      return fetchWithRefresh(`/api/pipelines/${id}/redetect`, { method: 'POST' })
    },
    async backfill(id: string, backfill_since: string) {
      return fetchWithRefresh(`/api/pipelines/${id}/backfill`, {
        method: 'POST',
        body: { backfill_since },
      })
    },
  }
}
