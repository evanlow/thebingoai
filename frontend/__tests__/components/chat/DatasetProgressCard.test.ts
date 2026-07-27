import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, computed, reactive } from 'vue'

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
// Run mounted hooks: the card fetches its documentation from history there.
vi.stubGlobal('onMounted', vi.fn((cb: () => void) => cb()))
vi.stubGlobal('onUnmounted', vi.fn())

const retryProfiling = vi.fn()
vi.stubGlobal('useDatasetStatus', () => ({ retryProfiling }))

const chatStore = reactive({
  datasetDocs: {} as Record<number, any>,
  setDatasetDocs(docs: any) { chatStore.datasetDocs[docs.connection_id] = docs },
})
vi.stubGlobal('useChatStore', () => chatStore)

const getSemantics = vi.fn()
vi.stubGlobal('useApi', () => ({ connections: { getSemantics } }))

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
  beforeEach(() => {
    vi.clearAllMocks()
    for (const k of Object.keys(chatStore.datasetDocs)) delete chatStore.datasetDocs[Number(k)]
    getSemantics.mockResolvedValue({ glossary: {} })
  })

  it('renders the four upload steps and the file header', () => {
    const wrapper = mountCard({ dataset: dataset('schema') })

    expect(wrapper.text()).toContain('headcount.csv')
    expect(wrapper.text()).toContain('573 B')
    // Documentation is a first-class step now, in both the thread and the panel.
    expect(wrapper.findAll('.step')).toHaveLength(4)
    expect(wrapper.findAll('.step')[3].attributes('data-label')).toBe('Columns documented')
  })

  it('takes no docsStatus prop — documentation comes from the dataset step', () => {
    const wrapper = mountCard({ dataset: dataset('ready'), docsStatus: 'active' })

    // The stray prop lands on attrs rather than driving anything.
    expect(wrapper.props()).not.toHaveProperty('docsStatus')
    expect(wrapper.findAll('.step')[3].attributes('data-status')).toBe('completed')
  })

  it('renders documenting as the active step with the previous four completed', () => {
    const wrapper = mountCard({ dataset: dataset('documenting') })

    const steps = wrapper.findAll('.step')
    expect(steps.map(s => s.attributes('data-status')))
      .toEqual(['completed', 'completed', 'completed', 'active'])
    expect(steps[3].attributes('data-last')).toBe('true')
  })

  it('leaves documentation pending while the dataset is still profiling', () => {
    const wrapper = mountCard({ dataset: dataset('profiling') })

    const steps = wrapper.findAll('.step')
    expect(steps[2].attributes('data-status')).toBe('active')
    expect(steps[3].attributes('data-status')).toBe('pending')
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

describe('DatasetProgressCard — documentation inside the card', () => {
  const DOCS = {
    connection_id: 7,
    table_name: 'csv_7',
    filename: 'headcount.csv',
    table_description: 'Employee records',
    columns: [
      { name: 'emp_id', display_name: 'Employee ID', description: 'Unique identifier' },
      { name: 'dept', display_name: 'Department', description: null },
    ],
    total_columns: 2,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    for (const k of Object.keys(chatStore.datasetDocs)) delete chatStore.datasetDocs[Number(k)]
    getSemantics.mockResolvedValue({ glossary: {} })
  })

  it('is collapsed by default and reports the column count', async () => {
    chatStore.datasetDocs[7] = DOCS
    const wrapper = mountCard({ dataset: dataset('ready') })
    await flushPromises()

    expect(wrapper.find('[data-testid="docs-toggle"]').text()).toContain('I read 2 columns — review')
    expect(wrapper.find('[data-testid="docs-body"]').exists()).toBe(false)
    // The column meanings are not on screen until asked for.
    expect(wrapper.text()).not.toContain('Unique identifier')
  })

  it('expands to the column rows on click', async () => {
    chatStore.datasetDocs[7] = DOCS
    const wrapper = mountCard({ dataset: dataset('ready') })
    await flushPromises()

    await wrapper.find('[data-testid="docs-toggle"]').trigger('click')

    const body = wrapper.find('[data-testid="docs-body"]')
    expect(body.exists()).toBe(true)
    expect(body.text()).toContain('emp_id')
    expect(body.text()).toContain('Employee ID — Unique identifier')
    // display_name alone is enough — no trailing separator.
    expect(body.text()).toContain('Department')
    expect(body.text()).toContain('Employee records')
    expect(body.text()).toContain("Tell me anything I've read wrong.")
  })

  it('uses the singular for a one-column dataset', async () => {
    chatStore.datasetDocs[7] = { ...DOCS, columns: [DOCS.columns[0]], total_columns: 1 }
    const wrapper = mountCard({ dataset: dataset('ready') })
    await flushPromises()

    expect(wrapper.find('[data-testid="docs-toggle"]').text()).toContain('I read 1 column — review')
  })

  it('renders no docs section when the payload documented nothing', async () => {
    chatStore.datasetDocs[7] = { ...DOCS, columns: [], total_columns: 0 }
    const wrapper = mountCard({ dataset: dataset('ready') })
    await flushPromises()

    expect(wrapper.find('[data-testid="docs-toggle"]').exists()).toBe(false)
  })

  it('fetches the glossary once on mount when the store has no entry', async () => {
    getSemantics.mockResolvedValue({
      glossary: {
        csv_7: { description: 'Employee records' },
        'csv_7.emp_id': { display_name: 'Employee ID', description: 'Unique identifier' },
        // Another table's entry must not leak into this card.
        'csv_99.other': { display_name: 'Nope' },
      },
    })
    const wrapper = mountCard({ dataset: dataset('ready') })
    await flushPromises()

    expect(getSemantics).toHaveBeenCalledExactlyOnceWith(7)
    expect(wrapper.find('[data-testid="docs-toggle"]').text()).toContain('I read 1 column — review')

    await wrapper.find('[data-testid="docs-toggle"]').trigger('click')
    expect(wrapper.find('[data-testid="docs-body"]').text()).toContain('emp_id')
    expect(wrapper.text()).not.toContain('Nope')
  })

  it('fetches nothing when the store already has the payload', async () => {
    chatStore.datasetDocs[7] = DOCS
    mountCard({ dataset: dataset('ready') })
    await flushPromises()

    expect(getSemantics).not.toHaveBeenCalled()
  })

  it('renders without documentation when the fetch fails', async () => {
    getSemantics.mockRejectedValue(new Error('404'))
    const wrapper = mountCard({ dataset: dataset('ready') })
    await flushPromises()

    expect(wrapper.find('[data-testid="docs-toggle"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('headcount.csv')
  })

  it('skips the fetch for a dataset with no connection', async () => {
    mountCard({ dataset: dataset('uploading', { connectionId: null }) })
    await flushPromises()

    expect(getSemantics).not.toHaveBeenCalled()
  })
})
