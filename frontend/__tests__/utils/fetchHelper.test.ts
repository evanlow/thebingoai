import { describe, it, expect, vi } from 'vitest'
import { initAnalytics } from '~/utils/analytics'
import { createFetchHelper } from '~/utils/api/fetchHelper'

describe('fetchHelper api_error tracking', () => {
  it('fires api_error with status and query-stripped endpoint on non-401 failure', async () => {
    initAnalytics('G-TEST123')
    ;(globalThis as any).$fetch = vi.fn().mockRejectedValue({ status: 500 })
    const { fetchWithRefresh } = createFetchHelper({ token: null }, {})

    await expect(fetchWithRefresh('/api/dashboards?page=2')).rejects.toBeTruthy()

    const last = Array.from((window as any).dataLayer.at(-1) as ArrayLike<unknown>)
    expect(last).toEqual(['event', 'api_error', { status: 500, endpoint: '/api/dashboards' }])
  })
})
