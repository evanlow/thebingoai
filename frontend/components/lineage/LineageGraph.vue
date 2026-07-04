<script setup lang="ts">
import { computed, ref } from 'vue'
import { VueFlow, Handle, Position, type Node, type Edge } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import type { LineageGraph, LineageNode, LineageEdge } from '~/composables/useLineage'

const props = defineProps<{
  graph: LineageGraph | null
}>()

const emit = defineEmits<{
  (e: 'select', node: LineageNode): void
}>()

const selectedId = ref<string | null>(null)

const NODE_W = 220
const NODE_H = 64
const COL_GAP = 120
const ROW_GAP = 36

const KIND_PALETTE: Record<string, { dot: string; accent: string; label: string }> = {
  source:    { dot: '#3b82f6', accent: '#dbeafe', label: 'SOURCE' },
  pipeline:  { dot: '#8b5cf6', accent: '#ede9fe', label: 'PIPELINE' },
  parquet:   { dot: '#64748b', accent: '#f1f5f9', label: 'PARQUET' },
  transform: { dot: '#f59e0b', accent: '#fef3c7', label: 'TRANSFORM' },
  widget:    { dot: '#0ea5e9', accent: '#e0f2fe', label: 'WIDGET' },
}

function layered(nodes: LineageNode[], edges: LineageEdge[]) {
  const adjOut: Record<string, string[]> = {}
  const inDeg: Record<string, number> = {}
  for (const n of nodes) { adjOut[n.id] = []; inDeg[n.id] = 0 }
  for (const e of edges) {
    if (!adjOut[e.src]) adjOut[e.src] = []
    if (inDeg[e.dst] === undefined) inDeg[e.dst] = 0
    adjOut[e.src].push(e.dst)
    inDeg[e.dst]++
  }
  const layer: Record<string, number> = {}
  const queue: string[] = []
  for (const id of Object.keys(inDeg)) if (inDeg[id] === 0) { layer[id] = 0; queue.push(id) }
  const visited = new Set<string>(queue)
  while (queue.length) {
    const cur = queue.shift()!
    for (const nb of adjOut[cur] || []) {
      layer[nb] = Math.max(layer[nb] ?? 0, (layer[cur] ?? 0) + 1)
      if (!visited.has(nb)) { visited.add(nb); queue.push(nb) }
    }
  }
  const cols: Record<number, string[]> = {}
  for (const n of nodes) {
    const c = layer[n.id] ?? 0
    if (!cols[c]) cols[c] = []
    cols[c].push(n.id)
  }
  return cols
}

const flowNodes = computed<Node[]>(() => {
  const g = props.graph
  if (!g) return []
  const cols = layered(g.nodes, g.edges)
  const result: Node[] = []
  for (const colKey of Object.keys(cols)) {
    const x = parseInt(colKey, 10) * (NODE_W + COL_GAP)
    cols[+colKey].forEach((id, idx) => {
      const node = g.nodes.find(n => n.id === id)
      if (!node) return
      result.push({
        id: node.id,
        type: 'lineage',
        position: { x, y: idx * (NODE_H + ROW_GAP) },
        data: { label: node.name, kind: node.kind, meta: node.meta, lineage: node },
      })
    })
  }
  return result
})

const flowEdges = computed<Edge[]>(() => {
  const g = props.graph
  if (!g) return []
  return g.edges.map((e, i) => ({
    id: `e${i}`,
    source: e.src,
    target: e.dst,
    animated: false,
    style: { stroke: '#cbd5e1', strokeWidth: 1.5 },
    type: 'smoothstep',
  }))
})

function onNodeClick(_evt: any, node: Node) {
  selectedId.value = node.id
  emit('select', node.data?.lineage as LineageNode)
}

const legendItems = Object.entries(KIND_PALETTE).map(([kind, pal]) => ({
  kind,
  dot: pal.dot,
  label: pal.label,
}))
</script>

<template>
  <div class="lineage-graph w-full h-full relative">
    <VueFlow
      :nodes="flowNodes"
      :edges="flowEdges"
      :default-viewport="{ x: 0, y: 0, zoom: 0.85 }"
      fit-view-on-init
      @node-click="onNodeClick"
      @pane-click="selectedId = null"
    >
      <!-- custom node card -->
      <template #node-lineage="{ data }">
        <div
          class="rounded-xl border bg-white dark:bg-neutral-800 shadow-sm px-3 py-2 flex items-center gap-2.5 cursor-pointer transition-shadow hover:shadow-md"
          :style="{
            borderColor: data.selected || selectedId === data.lineage?.id
              ? (KIND_PALETTE[data.kind]?.dot ?? '#9ca3af')
              : 'var(--line)',
            width: '220px',
            boxShadow: (data.selected || selectedId === data.lineage?.id)
              ? `0 0 0 1px ${KIND_PALETTE[data.kind]?.dot ?? '#9ca3af'}`
              : undefined,
          }"
        >
          <span
            class="grid place-items-center h-8 w-8 rounded-lg text-sm font-semibold text-white shrink-0 uppercase"
            :style="{ background: KIND_PALETTE[data.kind]?.dot ?? '#9ca3af' }"
          >
            {{ data.lineage?.name?.[0] ?? '?' }}
          </span>
          <div class="min-w-0 flex-1">
            <p class="text-sm font-medium text-[var(--ink-0)] truncate leading-snug">
              {{ data.label }}
            </p>
            <p
              class="text-sm font-semibold tracking-widest uppercase text-gray-400 dark:text-neutral-500 leading-tight"
            >
              {{ KIND_PALETTE[data.kind]?.label ?? data.kind?.toUpperCase() }}
            </p>
          </div>
          <Handle type="target" :position="Position.Left" class="!w-1.5 !h-1.5 !border-0 !bg-gray-300" />
          <Handle type="source" :position="Position.Right" class="!w-1.5 !h-1.5 !border-0 !bg-gray-300" />
        </div>
      </template>
    </VueFlow>

    <!-- Legend -->
    <div
      class="absolute top-3 right-3 rounded-xl border border-[var(--line)] bg-white/90 dark:bg-neutral-800/90 backdrop-blur-sm px-3 py-2.5 text-sm space-y-1.5 z-10"
    >
      <div
        v-for="item in legendItems"
        :key="item.kind"
        class="flex items-center gap-2"
      >
        <span class="h-2 w-2 rounded-full shrink-0" :style="{ background: item.dot }" />
        <span class="text-gray-600 dark:text-neutral-300">{{ item.label }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.lineage-graph {
  min-height: 480px;
}
</style>
