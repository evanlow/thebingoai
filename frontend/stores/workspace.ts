import { defineStore } from 'pinia'

export interface Workspace { org_id: string; org_name: string | null; role: string; is_home: boolean }

const LS_KEY = 'bingo.activeWorkspace'

export const useWorkspaceStore = defineStore('workspace', {
  state: () => ({
    activeOrgId: null as string | null,
    workspaces: [] as Workspace[],
  }),
  getters: {
    activeRole(state): string | null {
      const w = state.workspaces.find(w => w.org_id === state.activeOrgId)
      return w ? w.role : null
    },
    isViewer(): boolean { return this.activeRole === 'viewer' },
  },
  actions: {
    hydrate() {
      if (typeof window !== 'undefined') this.activeOrgId = localStorage.getItem(LS_KEY)
    },
    setActive(orgId: string | null) {
      this.activeOrgId = orgId
      if (typeof window !== 'undefined') {
        if (orgId) localStorage.setItem(LS_KEY, orgId)
        else localStorage.removeItem(LS_KEY)
      }
    },
    setWorkspaces(ws: Workspace[]) { this.workspaces = ws },
  },
})
