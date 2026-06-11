import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DashboardTable from '~/components/dashboard/DashboardTable.vue'

function row(overrides: Record<string, any> = {}) {
  return {
    id: 1,
    title: 'D',
    widgetCount: 0,
    widgetTypes: [],
    widgets: [],
    isShared: false,
    ...overrides,
  }
}

describe('DashboardTable OWNER column', () => {
  it('shows the row owner (not the viewer) for a shared dashboard', () => {
    const wrapper = mount(DashboardTable, {
      props: {
        currentUserEmail: 'viewer@x.com',
        items: [row({ id: 1, title: 'Shared', ownerEmail: 'host@x.com', orgName: 'Host', isShared: true })],
      },
    })
    const text = wrapper.text()
    expect(text).toContain('@host')      // owner handle derived from ownerEmail
    expect(text).not.toContain('@viewer')
  })

  it('falls back to the current user when the row has no ownerEmail', () => {
    const wrapper = mount(DashboardTable, {
      props: {
        currentUserEmail: 'me@x.com',
        items: [row({ id: 2, title: 'Mine' })],
      },
    })
    expect(wrapper.text()).toContain('@me')
  })

  it('renders the workspace org name when present', () => {
    const wrapper = mount(DashboardTable, {
      props: {
        currentUserEmail: 'viewer@x.com',
        items: [row({ id: 3, title: 'Shared', ownerEmail: 'host@x.com', orgName: 'Acme Corp', isShared: true })],
      },
    })
    expect(wrapper.text()).toContain('Acme Corp')
  })
})
