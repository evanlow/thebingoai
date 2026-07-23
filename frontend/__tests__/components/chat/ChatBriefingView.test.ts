import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, computed, watch } from 'vue'

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', watch)

let briefingValue: any = null
vi.stubGlobal('useBriefing', () => ({
  briefing: ref(briefingValue),
  loading: ref(false),
  error: ref(''),
}))
vi.stubGlobal('useBriefingPdf', () => ({
  exporting: ref(false),
  markWidgetLoaded: vi.fn(),
  resetWidgets: vi.fn(),
  exportPdf: vi.fn(),
}))

import ChatBriefingView from '~/components/chat/ChatBriefingView.vue'

const mountView = () =>
  mount(ChatBriefingView, {
    props: { briefingId: 48 },
    global: { stubs: { BriefingWidgetEmbed: true } },
  })

function readyBriefing(extraPayload: Record<string, any> = {}) {
  return {
    id: 48,
    status: 'ready',
    dashboard_id: 40,
    created_at: '2026-06-19T00:00:00Z',
    date_range_from: null,
    date_range_to: null,
    payload: {
      headline: 'Sales up 12%',
      deck: 'Strong quarter',
      kpis: [],
      sections: [{ heading: '1. Lift', prose: 'Strong.' }],
      key_takeaways: ['one', 'two', 'three'],
      ...extraPayload,
    },
  }
}

describe('ChatBriefingView', () => {
  beforeEach(() => {
    briefingValue = null
  })

  it('renders headline and key takeaways when ready', () => {
    briefingValue = readyBriefing()
    const w = mountView()
    expect(w.text()).toContain('Sales up 12%')
    expect(w.text()).toContain('Key takeaways')
    expect(w.text()).toContain('one')
  })

  it('renders recommended actions when present in the payload', () => {
    briefingValue = readyBriefing({ recommended_actions: ['Ship the fix', 'Review pricing'] })
    const w = mountView()
    expect(w.text()).toContain('Recommended actions')
    expect(w.text()).toContain('Ship the fix')
    expect(w.text()).toContain('Review pricing')
  })

  it('hides the recommended actions block on old briefings without the field', () => {
    briefingValue = readyBriefing()
    const w = mountView()
    expect(w.text()).not.toContain('Recommended actions')
  })
})
