import type { Workspace } from '~/stores/workspace'

export interface IncomingInvite {
  id: string
  org_id: string
  org_name: string | null
  role: string
  expires_at: string
}

export function createGovernanceApi(fetchWithRefresh: Function) {
  return {
    async listWorkspaces(): Promise<Workspace[]> {
      return fetchWithRefresh('/api/governance/workspaces', {})
    },
    async acceptInvite(token: string): Promise<{ user_id: string; org_id: string; role: string }> {
      return fetchWithRefresh('/api/governance/invites/accept', {
        method: 'POST',
        body: { token },
      })
    },
    // In-app notifications panel — invites addressed to the signed-in user.
    async listIncomingInvites(): Promise<IncomingInvite[]> {
      try {
        return await fetchWithRefresh('/api/governance/invites/incoming', {})
      } catch {
        // Community standalone (plugin absent) → endpoint 404 → empty panel.
        return []
      }
    },
    async acceptInviteById(inviteId: string): Promise<{ user_id: string; org_id: string; role: string }> {
      return fetchWithRefresh(`/api/governance/invites/${inviteId}/accept`, { method: 'POST' })
    },
  }
}
