import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import NodeDetailPanel from '~/components/lineage/NodeDetailPanel.vue'

const mountPanel = (node: any, graph: any = null) =>
  mount(NodeDetailPanel, {
    props: { node, graph },
    global: { stubs: { NuxtLink: true } },
  })

function makeGraph() {
  const nodes = [
    { id: 'a', kind: 'source', name: 'Prod Postgres', meta: {} },
    { id: 'b', kind: 'pipeline', name: 'orders_sync', meta: {} },
    { id: 'c', kind: 'parquet', name: 't_orders', meta: {} },
  ]
  const edges = [
    { src: 'a', dst: 'b', kind: 'source_to_pipeline' },
    { src: 'b', dst: 'c', kind: 'pipeline_to_table' },
  ]
  return { nodes, edges }
}

describe('NodeDetailPanel', () => {
  it('renders nothing when node is null', () => {
    expect(mountPanel(null).find('div').exists()).toBe(false)
  })

  it('lists upstream and downstream neighbors from the graph edges', () => {
    const graph = makeGraph()
    const node = { id: 'b', kind: 'pipeline', name: 'orders_sync', meta: {} }
    const wrapper = mountPanel(node, graph)
    const text = wrapper.text()
    expect(text).toContain('Upstream')
    expect(text).toContain('Prod Postgres')   // a → b
    expect(text).toContain('Downstream')
    expect(text).toContain('t_orders')        // b → c
  })

  it('shows no neighbor sections without a graph', () => {
    const node = { id: 'b', kind: 'pipeline', name: 'orders_sync', meta: {} }
    const text = mountPanel(node, null).text()
    expect(text).not.toContain('Upstream')
    expect(text).not.toContain('Downstream')
  })

  it.each(['pipeline', 'transform'])('shows the Re-run button for %s nodes', (kind) => {
    const wrapper = mountPanel({ id: 'x', kind, name: 'n', meta: {} })
    expect(wrapper.text()).toContain('Re-run')
  })

  it.each(['source', 'parquet', 'widget'])('hides the Re-run button for %s nodes', (kind) => {
    const wrapper = mountPanel({ id: 'x', kind, name: 'n', meta: {} })
    expect(wrapper.text()).not.toContain('Re-run')
  })

  it('emits rerun with the node when the button is clicked', async () => {
    const node = { id: 'x', kind: 'transform', name: 'n', meta: {} }
    const wrapper = mountPanel(node)
    const btn = wrapper.findAll('button').find(b => b.text() === 'Re-run')!
    await btn.trigger('click')
    expect(wrapper.emitted('rerun')?.[0]?.[0]).toEqual(node)
  })

  describe('status badge', () => {
    const badge = (status: string) =>
      mountPanel({ id: 'x', kind: 'pipeline', name: 'n', meta: { last_run_status: status } })
        .findAll('span').find(s => s.text() === status)!

    it.each([
      ['success', 'bg-emerald-100'],
      ['succeeded', 'bg-emerald-100'],
      ['failed', 'bg-rose-100'],
      ['running', 'bg-blue-100'],
    ])('applies a single status background for %s', (status, expected) => {
      const classes = badge(status).classes()
      expect(classes).toContain(expected)
      // exactly one bg-* utility — no conflicting fallback alongside it
      expect(classes.filter(c => c.startsWith('bg-'))).toHaveLength(1)
      expect(classes).not.toContain('bg-gray-100')
    })

    it('uses only the gray fallback for an unknown status', () => {
      const classes = badge('queued').classes()
      expect(classes).toContain('bg-gray-100')
      expect(classes.filter(c => c.startsWith('bg-'))).toHaveLength(1)
    })
  })
})
