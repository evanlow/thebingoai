import { useAuthStore } from '~/stores/auth'
import { createFetchHelper } from '~/utils/api/fetchHelper'
import { createChatApi } from '~/utils/api/chatApi'
import { createConnectionsApi } from '~/utils/api/connectionsApi'
import { createDashboardsApi } from '~/utils/api/dashboardsApi'
import { createGovernanceApi } from '~/utils/api/governanceApi'
import { createPipelinesApi } from '~/utils/api/pipelinesApi'
import { createResourcesApi } from '~/utils/api/resourcesApi'
import { useApiExtensions } from '~/composables/useApiExtensions'

export const useApi = () => {
  const authStore = useAuthStore()
  const router = useRouter()
  const { fetchWithRefresh } = createFetchHelper(authStore, router)

  const resources = createResourcesApi(fetchWithRefresh, authStore, router)

  const base = {
    fetchWithRefresh,
    ...resources,
    connections: createConnectionsApi(fetchWithRefresh, authStore, router),
    chat: createChatApi(fetchWithRefresh, authStore, router),
    dashboards: createDashboardsApi(fetchWithRefresh),
    governance: createGovernanceApi(fetchWithRefresh),
    pipelines: createPipelinesApi(fetchWithRefresh),
  }

  const ext = useApiExtensions()
  for (const [key, factory] of ext.entries()) {
    (base as Record<string, unknown>)[key] = factory(fetchWithRefresh, authStore, router)
  }

  return base
}
