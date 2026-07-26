import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, computed } from 'vue'

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('onMounted', vi.fn())
vi.stubGlobal('onUnmounted', vi.fn())

const retryProfiling = vi.fn()
vi.stubGlobal('useDatasetStatus', () => ({ retryProfiling }))

import DatasetProgressCard from '~/components/chat/DatasetProgressCard.vue'

const stubs = {
  DatasetTimelineStep: {
    props: ['status', 'label', 'activeLabel', 'isLast'],
    template: '<div class="step" :data-status="status" :data-label="label" :data-last="String(isLast)" />',
  },
}

function dataset(step: string, overrides: Record<string, any> = {}) {
  return {
    name: 'headcount.csv', size: 573, fileId: 'f1', connectionId: 7, step,
    uploadedAt: null, schemaBuiltAt: null, profilingStartedAt: null, completedAt: null,
    rowCount: null, columnCount: null, error: null, ...overrides,
  }
}

const mountCard = (props: Record<string, any>) =>
  mount(DatasetProgressCard, { props, global: { stubs } })

describe('DatasetProgressCard', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders the three upload steps and the file header', () => {
    const wrapper = mountCard({ dataset: dataset('schema') })

    expect(wrapper.text()).toContain('headcount.csv')
    expect(wrapper.text()).toContain('573 B')
    expect(wrapper.findAll('.step')).toHaveLength(3)
  })

  it('omits the documentation step when no docsStatus is given — the info panel case', () => {
    const wrapper = mountCard({ dataset: dataset('schema') })

    expect(wrapper.text()).not.toContain('Columns documented')
    expect(wrapper.text()).not.toContain('Reading the columns')
    // Profiling is the last step, so no connector hangs off the bottom
    expect(wrapper.findAll('.step')[2].attributes('data-last')).toBe('true')
  })

  it('shows a spinning Bingo mark while the documentation is being written', () => {
    const wrapper = mountCard({ dataset: dataset('ready'), docsStatus: 'active' })

    expect(wrapper.text()).toContain('Reading the columns...')
    const spinners = wrapper.findAll('img.docs-spin')
    // One for each theme; both carry the spin animation class
    expect(spinners.length).toBe(2)
    // src is percent-encoded by the DOM
    expect(spinners[0].attributes('src')).toContain('BINGO%20Logo')
  })

  it('settles the documentation step once the docs have arrived', () => {
    const wrapper = mountCard({ dataset: dataset('ready'), docsStatus: 'completed' })

    expect(wrapper.text()).toContain('Columns documented')
    expect(wrapper.find('img.docs-spin').exists()).toBe(false)
  })

  it('keeps profiling connected to the documentation step when one follows', () => {
    const wrapper = mountCard({ dataset: dataset('ready'), docsStatus: 'pending' })

    expect(wrapper.findAll('.step')[2].attributes('data-last')).toBe('false')
  })

  it('marks every step completed once the dataset is ready', () => {
    const wrapper = mountCard({ dataset: dataset('ready') })

    for (const step of wrapper.findAll('.step')) {
      expect(step.attributes('data-status')).toBe('completed')
    }
  })

  it('offers a retry when profiling failed', async () => {
    const wrapper = mountCard({ dataset: dataset('failed', { error: 'boom' }) })

    const btn = wrapper.find('button')
    expect(btn.text()).toBe('Retry')
    await btn.trigger('click')
    expect(retryProfiling).toHaveBeenCalledWith(7)
  })

  it('does not offer a retry for an upload that failed before a connection existed', () => {
    const wrapper = mountCard({
      dataset: dataset('failed', { error: 'Upload failed', connectionId: null }),
    })

    expect(wrapper.find('button').exists()).toBe(false)
  })
})
