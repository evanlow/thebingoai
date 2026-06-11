import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWorkspaceStore } from '~/stores/workspace'

describe('workspace store', () => {
  beforeEach(() => { setActivePinia(createPinia()); localStorage.clear() })

  it('persists active workspace id to localStorage', () => {
    const s = useWorkspaceStore()
    s.setActive('org-123')
    expect(s.activeOrgId).toBe('org-123')
    expect(localStorage.getItem('bingo.activeWorkspace')).toBe('org-123')
  })

  it('hydrates from localStorage', () => {
    localStorage.setItem('bingo.activeWorkspace', 'org-xyz')
    const s = useWorkspaceStore()
    s.hydrate()
    expect(s.activeOrgId).toBe('org-xyz')
  })

  it('isViewer reflects active role', () => {
    const s = useWorkspaceStore()
    s.setWorkspaces([{ org_id: 'o1', org_name: 'O1', role: 'viewer', is_home: false }])
    s.setActive('o1')
    expect(s.isViewer).toBe(true)
  })
})
