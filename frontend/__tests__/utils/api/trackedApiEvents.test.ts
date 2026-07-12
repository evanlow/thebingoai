import { describe, it, expect, vi, beforeEach } from 'vitest'

// GA4 event wiring in the API utils: each tracked call fires exactly one
// event AFTER the request resolves, with the documented params — and no
// event when the request rejects.
const { trackEventMock } = vi.hoisted(() => ({ trackEventMock: vi.fn() }))
vi.mock('~/utils/analytics', () => ({ trackEvent: trackEventMock }))

// uploadDataset goes through withAuthRetry + xhrUpload (XHR, browser-only) —
// mock the module so the upload resolves/rejects without a network layer.
const { withAuthRetryMock } = vi.hoisted(() => ({ withAuthRetryMock: vi.fn() }))
vi.mock('~/utils/api/xhrUpload', () => ({
  xhrUpload: vi.fn(),
  withAuthRetry: withAuthRetryMock,
}))

import { createDashboardsApi } from '~/utils/api/dashboardsApi'
import { createConnectionsApi } from '~/utils/api/connectionsApi'
import { createPipelinesApi } from '~/utils/api/pipelinesApi'

describe('tracked API events', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    trackEventMock.mockClear()
    fetchMock.mockReset()
    fetchMock.mockResolvedValue({ briefing_id: 9, status: 'ok' })
  })

  describe('dashboardsApi.brief', () => {
    it('fires briefing_create with the dashboard id on success', async () => {
      const api = createDashboardsApi(fetchMock)
      await api.brief(40)
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('briefing_create', {
        dashboard_id: 40,
      })
    })

    it('fires no event when the request rejects', async () => {
      fetchMock.mockRejectedValueOnce(new Error('402'))
      const api = createDashboardsApi(fetchMock)
      await expect(api.brief(40)).rejects.toThrow()
      expect(trackEventMock).not.toHaveBeenCalled()
    })
  })

  describe('connectionsApi', () => {
    const makeApi = () => createConnectionsApi(fetchMock, {}, {})

    it('create fires connection_create with connector_type from db_type', async () => {
      await makeApi().create({ db_type: 'postgres', host: 'h' })
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('connection_create', {
        connector_type: 'postgres',
      })
    })

    it('create falls back to "unknown" when db_type is absent', async () => {
      await makeApi().create({ name: 'x' })
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('connection_create', {
        connector_type: 'unknown',
      })
    })

    it('test fires connection_test with no params', async () => {
      await makeApi().test('c1')
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('connection_test')
    })

    it('uploadDataset fires csv_upload on success', async () => {
      withAuthRetryMock.mockResolvedValueOnce({ connection_id: 1 })
      await makeApi().uploadDataset(new File(['a,b'], 'data.csv'))
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('csv_upload')
    })

    it('uploadDataset fires no event when the upload fails', async () => {
      withAuthRetryMock.mockRejectedValueOnce(new Error('413'))
      await expect(makeApi().uploadDataset(new File(['x'], 'data.csv'))).rejects.toThrow()
      expect(trackEventMock).not.toHaveBeenCalled()
    })
  })

  describe('pipelinesApi', () => {
    const makeApi = () => createPipelinesApi(fetchMock)

    it('create fires pipeline_create with the mode', async () => {
      await makeApi().create({ mode: 'incremental' } as any)
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('pipeline_create', {
        mode: 'incremental',
      })
    })

    it('run fires pipeline_run_manual', async () => {
      await makeApi().run('p1')
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('pipeline_run_manual')
    })

    it('loadHistory fires pipeline_backfill', async () => {
      await makeApi().loadHistory('p1', '2026-01-01')
      expect(trackEventMock).toHaveBeenCalledExactlyOnceWith('pipeline_backfill')
    })
  })
})
