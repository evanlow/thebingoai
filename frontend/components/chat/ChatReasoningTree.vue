<template>
  <div class="font-mono text-sm">
    <!-- Root: Orchestrator -->
    <div class="flex items-center gap-1.5 py-0.5 mb-0.5">
      <span class="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />
      <span class="font-medium text-gray-800 dark:text-neutral-200 font-sans text-sm">Orchestrator</span>
      <span v-if="rootTimestamp" class="ml-auto text-sm font-mono text-gray-400 dark:text-neutral-500">{{ rootTimestamp }}</span>
    </div>

    <ChatReasoningTreeNode
      v-for="(child, idx) in treeNodes.children"
      :key="idx"
      :node="child"
      :is-last="idx === treeNodes.children.length - 1"
      :ancestors="[]"
    />
  </div>
</template>

<script setup lang="ts">
import type { AgentStep, Message } from '~/stores/chat'
import type { TreeNode } from '~/components/chat/ChatReasoningTreeNode.vue'
import { parseUtcDate } from '~/utils/format'

const props = defineProps<{
  message: Message
}>()

const chatStore = useChatStore()
const { ensureLoaded: ensureConnectionsLoaded, getConnectionLabel } = useConnections()
ensureConnectionsLoaded()

const steps = computed((): AgentStep[] => props.message.agent_steps || [])

// --- Formatting helpers ---

const formatToolName = (name?: string): string => {
  if (!name) return 'Tool'
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

const formatTimestamp = (step: AgentStep): string => {
  const ts = step.started_at ?? (step.created_at ? parseUtcDate(step.created_at).getTime() : undefined)
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const getResultLabel = (result: any): string => {
  if (!result) return 'Completed'
  if (Array.isArray(result)) return `Found ${result.length} item${result.length !== 1 ? 's' : ''}`
  if (typeof result === 'object') {
    if ('row_count' in result) return `Completed: ${result.row_count} row${result.row_count !== 1 ? 's' : ''}`
    if ('rows' in result && Array.isArray(result.rows)) return `Completed: ${result.rows.length} row${result.rows.length !== 1 ? 's' : ''}`
  }
  return 'Completed'
}

const formatArgs = (args: Record<string, any> | undefined): string | undefined => {
  if (!args || Object.keys(args).length === 0) return undefined
  const entries = Object.entries(args).filter(([k]) => !k.startsWith('_'))
  if (entries.length === 0) return undefined
  return entries
    .map(([k, v]) => {
      if (k === 'connection_id' && typeof v === 'number') {
        return `**connection**: ${getConnectionLabel(v)}`
      }
      const val = typeof v === 'string' ? v : JSON.stringify(v, null, 2)
      return `**${k}**: ${val}`
    })
    .join('\n\n')
}

// --- Tree transformation ---

/** Extract a compact label from tool args for grouped display (e.g. "listings" instead of repeating "Get Table Schema"). */
const compactArgLabel = (args: Record<string, any> | undefined): string | undefined => {
  if (!args || Object.keys(args).length === 0) return undefined
  // Skip connection_id — show the differentiating args only
  const meaningful = Object.entries(args).filter(([k]) => k !== 'connection_id' && !k.startsWith('_'))
  if (meaningful.length === 0) return undefined
  // Single arg: show just the value
  if (meaningful.length === 1) {
    const val = meaningful[0][1]
    return typeof val === 'string' ? val : JSON.stringify(val)
  }
  // Multiple args: show key: value pairs
  return meaningful.map(([k, v]) => {
    const val = typeof v === 'string' ? v : JSON.stringify(v)
    return `${k}: ${val}`
  }).join(', ')
}

const SUB_AGENT_TOOLS = new Set(['data_agent', 'rag_agent'])
const AGENT_LABELS: Record<string, string> = {
  data_agent: 'Data Agent',
  rag_agent: 'RAG Agent',
}

const rootTimestamp = computed((): string | undefined => {
  const first = steps.value[0]
  return first ? formatTimestamp(first) || undefined : undefined
})

const treeNodes = computed((): TreeNode => {
  const root: TreeNode = { type: 'agent', label: 'Orchestrator', children: [] }

  // Buffer for grouping consecutive same-name non-sub-agent tool_calls
  let toolBuffer: { toolName: string; nodes: TreeNode[]; steps: AgentStep[]; totalMs: number } | null = null

  const flushBuffer = () => {
    if (!toolBuffer) return
    if (toolBuffer.nodes.length === 1) {
      root.children.push(toolBuffer.nodes[0])
    } else {
      const allCompleted = toolBuffer.nodes.every(n => n.status === 'completed')
      // Create compact children showing just the differentiating arg (e.g. table name)
      const compactChildren: TreeNode[] = toolBuffer.steps.map((s, i) => {
        const argLabel = compactArgLabel(s.content?.args)
        const dur = typeof s.duration_ms === 'number' ? formatDuration(s.duration_ms) : undefined
        return {
          type: 'result' as const,
          label: argLabel || toolBuffer!.nodes[i].label,
          status: s.status === 'completed' ? 'completed' as const : 'in-progress' as const,
          duration: dur,
          children: [],
        }
      })
      root.children.push({
        type: 'action',
        label: toolBuffer.nodes[0].label,
        count: toolBuffer.nodes.length,
        duration: toolBuffer.totalMs > 0 ? formatDuration(toolBuffer.totalMs) : undefined,
        status: allCompleted ? 'completed' : 'in-progress',
        timestamp: toolBuffer.nodes[0].timestamp,
        children: compactChildren,
      })
    }
    toolBuffer = null
  }

  for (const step of steps.value) {
    if (step.step_type === 'reasoning') {
      flushBuffer()
      root.children.push({
        type: 'reasoning',
        label: step.content?.text || 'Thinking...',
        status: step.status === 'streaming' ? 'streaming' : 'completed',
        timestamp: formatTimestamp(step) || undefined,
        children: [],
      })
      continue
    }

    if (step.step_type === 'judge_status') {
      flushBuffer()
      const state = step.content?.state ?? 'refining'
      const label =
        state === 'refining' ? 'Refining response…' :
        state === 'refined' ? 'Response refined' :
        'Response approved'
      root.children.push({
        type: 'reasoning',
        label,
        status: state === 'refining' ? 'streaming' : 'completed',
        timestamp: formatTimestamp(step) || undefined,
        children: [],
      })
      continue
    }

    if (step.step_type !== 'tool_call') continue

    const ts = formatTimestamp(step) || undefined
    const dur = typeof step.duration_ms === 'number' ? formatDuration(step.duration_ms) : undefined
    const nodeStatus: 'in-progress' | 'completed' = step.status === 'completed' ? 'completed' : 'in-progress'
    const argsDetail = formatArgs(step.content?.args)

    if (SUB_AGENT_TOOLS.has(step.tool_name || '')) {
      flushBuffer()
      const agentLabel = AGENT_LABELS[step.tool_name!] || formatToolName(step.tool_name)
      const agentNode: TreeNode = { type: 'agent', label: agentLabel, children: [] }

      for (const subStep of (step.content?.sub_steps || [])) {
        let subTs: string | undefined
        if (subStep.started_at) {
          subTs = parseUtcDate(subStep.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
        } else if (subStep.created_at) {
          subTs = parseUtcDate(subStep.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
        }
        agentNode.children.push({
          type: 'action',
          label: formatToolName(subStep.tool_name),
          timestamp: subTs,
          status: subStep.status === 'completed' ? 'completed' : 'in-progress',
          children: [],
        })
      }

      if (step.status === 'completed' && step.content?.result !== undefined) {
        agentNode.children.push({
          type: 'result',
          label: getResultLabel(step.content.result),
          status: 'completed',
          timestamp: ts,
          children: [],
        })
      }

      root.children.push({
        type: 'action',
        label: `Routing to ${agentLabel}`,
        detail: argsDetail,
        status: nodeStatus,
        duration: dur,
        timestamp: ts,
        children: [agentNode],
      })
    } else {
      const node: TreeNode = {
        type: 'action',
        label: formatToolName(step.tool_name),
        detail: argsDetail,
        status: nodeStatus,
        duration: dur,
        timestamp: ts,
        children: [],
      }

      if (toolBuffer && toolBuffer.toolName === step.tool_name) {
        toolBuffer.nodes.push(node)
        toolBuffer.steps.push(step)
        toolBuffer.totalMs += step.duration_ms || 0
      } else {
        flushBuffer()
        toolBuffer = {
          toolName: step.tool_name || '',
          nodes: [node],
          steps: [step],
          totalMs: step.duration_ms || 0,
        }
      }
    }
  }

  flushBuffer()

  if (steps.value.length > 0 && !chatStore.isStreaming) {
    const lastStep = steps.value[steps.value.length - 1]
    root.children.push({
      type: 'result',
      label: 'Response generated',
      status: 'completed',
      timestamp: formatTimestamp(lastStep) || undefined,
      children: [],
    })
  }

  return root
})
</script>
