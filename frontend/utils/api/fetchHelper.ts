import { trackEvent } from '~/utils/analytics'

export function createFetchHelper(authStore: any, router: any) {
  const getHeaders = (body?: any) => {
    const headers: Record<string, string> = {}

    // Let the browser set its own multipart/form-data boundary for FormData uploads
    if (!(body instanceof FormData)) {
      headers['Content-Type'] = 'application/json'
    }

    if (authStore.token) {
      headers['Authorization'] = `Bearer ${authStore.token}`
    }

    return headers
  }

  const reportApiError = (url: string, error: any) => {
    trackEvent('api_error', {
      status: error?.statusCode ?? error?.status ?? 0,
      endpoint: url.split('?')[0],  // strip query — may carry user data
    })
  }

  const fetchWithRefresh = async <T>(url: string, options: Parameters<typeof $fetch>[1] = {}): Promise<T> => {
    try {
      return await $fetch<T>(url, {
        timeout: 60_000,  // default cap; callers can override via options
        ...options,
        headers: {
          ...getHeaders(options.body),
          ...(options.headers as Record<string, string> || {}),
        },
      })
    } catch (error: any) {
      if (error?.statusCode === 401 || error?.status === 401) {
        const refreshed = await authStore.refreshAccessToken()
        if (refreshed) {
          // Retry with new token
          return await $fetch<T>(url, {
            timeout: 60_000,  // default cap; callers can override via options
            ...options,
            headers: {
              ...getHeaders(options.body),
              ...(options.headers as Record<string, string> || {}),
            },
          })
        } else {
          // Refresh failed - logout and redirect. Report before logout so the
          // error event still carries GA4 user identity (logout clears it via
          // the user watcher).
          reportApiError(url, error)
          await authStore.logout()
          await router.push('/login')
          throw error
        }
      }
      reportApiError(url, error)
      throw error
    }
  }

  return { fetchWithRefresh, getHeaders }
}
