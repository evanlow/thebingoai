import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, computed, reactive } from 'vue'

// Nuxt auto-imports these at build; provide them as globals for the test runtime.
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('reactive', reactive)
vi.stubGlobal('useChatStore', () => ({ isStreaming: false }))
vi.stubGlobal('useConnections', () => ({
  ensureLoaded: vi.fn(),
  getConnectionLabel: (id: number) => `conn ${id}`,
}))

import ChatReasoningTree from '~/components/chat/ChatReasoningTree.vue'

// Recursive stub for the auto-imported tree-node renderer: surfaces every node's
// label (and child labels) in the rendered text so we can assert tree shape.
const TreeNodeStub = {
  name: 'ChatReasoningTreeNode',
  props: ['node', 'isLast', 'ancestors'],
  template: `<div class="tnode">
    <span class="label">{{ node.label }}</span>
    <span v-if="node.count" class="count">x{{ node.count }}</span>
    <ChatReasoningTreeNode
      v-for="(c, i) in node.children"
      :key="i"
      :node="c"
      :is-last="false"
      :ancestors="[]"
    />
  </div>`,
}

function mountTree(agent_steps: any[]) {
  return mount(ChatReasoningTree, {
    props: { message: { id: 'm1', role: 'assistant', agent_steps } },
    global: { components: { ChatReasoningTreeNode: TreeNodeStub } },
  })
}

describe('ChatReasoningTree', () => {
  beforeEach(() => {
    vi.stubGlobal('useChatStore', () => ({ isStreaming: false }))
  })

  it('renders the Orchestrator root and a completion node when not streaming', () => {
    const wrapper = mountTree([
      { step_type: 'tool_call', tool_name: 'get_table_schema', content: {}, status: 'completed' },
    ])
    expect(wrapper.text()).toContain('Orchestrator')
    expect(wrapper.text()).toContain('Response generated')
  })

  it('surfaces a reasoning step text as its node label', () => {
    const wrapper = mountTree([
      { step_type: 'reasoning', content: { text: 'need to join orders and users' }, status: 'completed' },
    ])
    expect(wrapper.text()).toContain('need to join orders and users')
  })

  it('formats a tool_call name into a title-cased label', () => {
    const wrapper = mountTree([
      { step_type: 'tool_call', tool_name: 'get_table_schema', content: {}, status: 'completed' },
    ])
    expect(wrapper.text()).toContain('Get Table Schema')
  })

  it('renders sub-agent routing with nested sub-steps', () => {
    const wrapper = mountTree([
      {
        step_type: 'tool_call',
        tool_name: 'data_agent',
        status: 'completed',
        content: {
          args: {},
          sub_steps: [{ tool_name: 'run_sql', status: 'completed' }],
          result: { row_count: 3 },
        },
      },
    ])
    expect(wrapper.text()).toContain('Routing to Data Agent')
    expect(wrapper.text()).toContain('Data Agent')
    expect(wrapper.text()).toContain('Run Sql')
  })

  it('groups consecutive same-name tool_calls into compact children', () => {
    const wrapper = mountTree([
      { step_type: 'tool_call', tool_name: 'get_table_schema', status: 'completed', content: { args: { table: 'orders' } } },
      { step_type: 'tool_call', tool_name: 'get_table_schema', status: 'completed', content: { args: { table: 'users' } } },
    ])
    const text = wrapper.text()
    // grouped parent keeps the formatted tool name + a count badge
    expect(text).toContain('Get Table Schema')
    expect(text).toContain('x2')
    // compact children differentiate by the changing arg value
    expect(text).toContain('orders')
    expect(text).toContain('users')
  })

  it('renders only the Orchestrator root for an empty step list', () => {
    const wrapper = mountTree([])
    expect(wrapper.text()).toContain('Orchestrator')
    expect(wrapper.text()).not.toContain('Response generated')
    expect(wrapper.findAllComponents(TreeNodeStub).length).toBe(0)
  })

  it('does not append a completion node while streaming', () => {
    vi.stubGlobal('useChatStore', () => ({ isStreaming: true }))
    const wrapper = mountTree([
      { step_type: 'tool_call', tool_name: 'get_table_schema', content: {}, status: 'in-progress' },
    ])
    expect(wrapper.text()).not.toContain('Response generated')
  })
})
