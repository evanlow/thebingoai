import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'

// ── Stub @vue-flow/core ───────────────────────────────────────────────
// Real VueFlow needs ResizeObserver/RAF/measurement and never renders the
// #node-lineage scoped slot deterministically under happy-dom. This stub
// renders that slot per node and re-emits node-click / pane-click, so the
// parent's selection logic (onNodeClick, selectedId, @pane-click) is exercised.
vi.mock('@vue-flow/core', () => {
  const VueFlow = defineComponent({
    name: 'VueFlow',
    props: { nodes: { type: Array, default: () => [] }, edges: { type: Array, default: () => [] } },
    emits: ['node-click', 'pane-click'],
    setup(props, { slots, emit }) {
      return () =>
        h('div', { class: 'vf' }, [
          h('div', { class: 'vf-pane', onClick: () => emit('pane-click') }, 'pane'),
          ...(props.nodes as any[]).map((n) =>
            h(
              'div',
              { class: 'vf-node', 'data-id': n.id, onClick: () => emit('node-click', {}, n) },
              slots['node-lineage'] ? slots['node-lineage']({ data: n.data }) : [],
            ),
          ),
        ])
    },
  })
  const Handle = { name: 'Handle', render: () => null }
  const Position = { Left: 'left', Right: 'right', Top: 'top', Bottom: 'bottom' }
  return { VueFlow, Handle, Position }
})

import LineageGraph from '~/components/lineage/LineageGraph.vue'

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
  return { scope_kind: 'user', scope_id: 'u1', nodes, edges, incomplete_widgets: [] }
}

const mountGraph = (graph: any = makeGraph()) => mount(LineageGraph, { props: { graph } })

describe('LineageGraph', () => {
  it('renders a legend row for every node kind', () => {
    const text = mountGraph().text()
    for (const label of ['SOURCE', 'PIPELINE', 'PARQUET', 'TRANSFORM', 'WIDGET']) {
      expect(text).toContain(label)
    }
  })

  it('emits select with the clicked LineageNode', async () => {
    const graph = makeGraph()
    const wrapper = mountGraph(graph)
    await wrapper.find('.vf-node[data-id="b"]').trigger('click')
    expect(wrapper.emitted('select')?.[0]?.[0]).toEqual(graph.nodes[1])
  })

  it('highlights the selected node and clears it on pane click', async () => {
    const wrapper = mountGraph()
    const cardStyle = () => wrapper.find('.vf-node[data-id="b"] .rounded-xl').attributes('style') ?? ''

    // unselected: no selection ring
    expect(cardStyle()).not.toContain('box-shadow')

    // selected: ring in the pipeline accent color
    await wrapper.find('.vf-node[data-id="b"]').trigger('click')
    expect(cardStyle()).toContain('box-shadow')
    expect(cardStyle()).toContain('#8b5cf6')

    // pane click clears the selection ring
    await wrapper.find('.vf-pane').trigger('click')
    expect(cardStyle()).not.toContain('box-shadow')
  })
})
