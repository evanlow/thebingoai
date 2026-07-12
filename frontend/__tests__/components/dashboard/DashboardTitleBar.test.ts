import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

// DashboardTitleBar imports icons explicitly from lucide-vue-next.
vi.mock('lucide-vue-next', () => ({
  Pencil: { render: () => null },
  Eye: { render: () => null },
  Save: { render: () => null },
  RefreshCw: { render: () => null },
  Trash2: { render: () => null },
}))

// DashboardTitleBar calls useWorkspaceStore() directly at setup.
vi.mock('~/stores/workspace', () => ({
  useWorkspaceStore: () => ({ isViewer: false }),
}))

import DashboardTitleBar from '~/components/dashboard/DashboardTitleBar.vue'

// Regression guard for: DashboardBriefsButton captures useDashboardBriefings(dashboardId)
// once at setup (non-reactive). Without `:key="dashboardId"` on the button in
// DashboardTitleBar.vue, switching dashboards leaves it bound to the old dashboard's
// briefings because the component instance is reused instead of remounted.
//
// This test doesn't touch useDashboardBriefings at all — it stubs DashboardBriefsButton
// itself and counts setup() calls, which only increments on a real mount/unmount cycle,
// i.e. exactly when the `:key` forces Vue to recreate the instance.
let briefsMountCount = 0

const DashboardBriefsButtonStub = {
  name: 'DashboardBriefsButton',
  props: ['dashboardId'],
  setup() {
    briefsMountCount++
    return () => null
  },
}

// DashboardSchedulePopover and BriefMeButton are also auto-imported siblings in the
// same template row; stub them to trivial no-ops so mounting doesn't pull their deps.
const NullStub = { template: '<div />' }

function mountTitleBar(props: Record<string, any> = {}) {
  return mount(DashboardTitleBar, {
    props: {
      title: 'My Dashboard',
      editMode: false,
      dirty: false,
      saving: false,
      refreshing: false,
      dashboardId: 1,
      ...props,
    },
    global: {
      stubs: {
        DashboardSchedulePopover: NullStub,
        BriefMeButton: NullStub,
        DashboardBriefsButton: DashboardBriefsButtonStub,
      },
    },
  })
}

describe('DashboardTitleBar — briefs button remounts on dashboard switch', () => {
  beforeEach(() => {
    briefsMountCount = 0
  })

  it('remounts DashboardBriefsButton when dashboardId changes', async () => {
    const wrapper = mountTitleBar({ dashboardId: 1 })
    expect(briefsMountCount).toBe(1)

    await wrapper.setProps({ dashboardId: 2 })
    expect(briefsMountCount).toBe(2)
  })

  it('control: an unrelated prop change (title) does not remount the briefs button', async () => {
    const wrapper = mountTitleBar({ dashboardId: 1 })
    expect(briefsMountCount).toBe(1)

    await wrapper.setProps({ title: 'Renamed Dashboard' })
    expect(briefsMountCount).toBe(1)
  })
})
