<template>
  <div class="h-full flex flex-col overflow-hidden" :style="containerStyle">
    <div v-if="config.showTitle && config.title" class="px-1 pb-1 flex-shrink-0">
      <span class="text-xs font-semibold text-gray-700 dark:text-neutral-200 uppercase tracking-wide">{{ config.title }}</span>
    </div>

    <div v-if="isEmptyState" class="flex-1 flex items-center justify-center p-6 text-center text-xs text-gray-400 dark:text-neutral-500">
      Add at least one row dimension and one metric to build the pivot.
    </div>

    <div v-else class="flex-1 overflow-auto" :class="fontClass">
      <table class="table-fixed border-collapse text-left text-gray-700 dark:text-neutral-300"
        :style="tableStyle">
        <colgroup>
          <col :style="{ width: pivotColWidth('rowHeader') + 'px' }" />
          <template v-for="(combo, ci) in columnCombos" :key="'cg'+ci">
            <col v-for="(v, vi) in values" :key="'cg'+ci+'-'+vi"
              :style="{ width: pivotColWidth(valueKey(v)) + 'px' }" />
          </template>
          <col v-if="showTotalCol" :style="{ width: totalColWidth + 'px' }" />
        </colgroup>
        <thead>
          <!-- Column-dimension group header (only when column dimensions exist) -->
          <tr v-if="colDims.length">
            <th :rowspan="2" class="relative sticky left-0 z-10 px-2 py-1.5 font-semibold text-gray-500 dark:text-neutral-400 align-bottom whitespace-nowrap overflow-hidden text-ellipsis"
              :style="headerCellStyle">{{ rowHeaderLabel }}
              <div v-if="editMode" class="absolute top-0 right-0 z-20 h-full w-1.5 cursor-col-resize hover:bg-indigo-300/60"
                @mousedown.stop.prevent="startPivotResize($event, 'rowHeader')" @click.stop /></th>
            <th v-for="(combo, ci) in columnCombos" :key="'g'+ci" :colspan="values.length"
              class="px-2 py-1.5 text-center font-semibold text-gray-500 dark:text-neutral-400 border-l whitespace-nowrap overflow-hidden text-ellipsis" :style="headerCellStyle">
              {{ combo.map(String).join(' / ') }}
            </th>
            <th v-if="showTotalCol" :rowspan="2" class="px-2 py-1.5 text-right font-semibold text-gray-700 dark:text-neutral-200 border-l align-bottom whitespace-nowrap overflow-hidden text-ellipsis"
              :style="headerCellStyle">{{ config.grandTotalLabel || 'Total' }}</th>
          </tr>
          <tr>
            <th v-if="!colDims.length" class="relative sticky left-0 z-10 px-2 py-1.5 font-semibold text-gray-500 dark:text-neutral-400 whitespace-nowrap overflow-hidden text-ellipsis"
              :style="headerCellStyle">{{ rowHeaderLabel }}
              <div v-if="editMode" class="absolute top-0 right-0 z-20 h-full w-1.5 cursor-col-resize hover:bg-indigo-300/60"
                @mousedown.stop.prevent="startPivotResize($event, 'rowHeader')" @click.stop /></th>
            <template v-for="(combo, ci) in columnCombos" :key="'m'+ci">
              <th v-for="(v, vi) in values" :key="'m'+ci+'-'+vi"
                class="relative px-2 py-1.5 text-right font-semibold text-gray-500 dark:text-neutral-400 whitespace-nowrap overflow-hidden text-ellipsis"
                :class="{ 'border-l': vi === 0 && colDims.length }" :style="headerCellStyle">
                {{ v.label || v.column }}
                <div v-if="editMode" class="absolute top-0 right-0 z-20 h-full w-1.5 cursor-col-resize hover:bg-indigo-300/60"
                  @mousedown.stop.prevent="startPivotResize($event, valueKey(v))" @click.stop />
              </th>
            </template>
            <th v-if="showTotalCol && !colDims.length" class="px-2 py-1.5 text-right font-semibold text-gray-700 dark:text-neutral-200 border-l whitespace-nowrap overflow-hidden text-ellipsis"
              :style="headerCellStyle">{{ config.grandTotalLabel || 'Total' }}</th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="(node, ri) in flatRows" :key="node.key"
            :class="node.children ? 'font-medium' : ''" :style="rowStyle(ri)">
            <!-- Row header with indent + expand toggle -->
            <td class="sticky left-0 z-10 px-2 py-1 whitespace-normal break-words" :style="rowHeaderStyle(ri)">
              <span :style="{ paddingLeft: (node.depth * 14) + 'px' }" class="inline-flex items-center gap-1">
                <button v-if="node.children" type="button"
                  class="inline-flex h-3.5 w-3.5 items-center justify-center rounded text-[10px] text-gray-500 hover:bg-gray-200 dark:text-neutral-400 dark:hover:bg-neutral-700"
                  @click="toggle(node)">{{ expandedSet(node) ? '−' : '+' }}</button>
                <span v-else class="inline-block w-3.5"></span>
                {{ fmtLabel(node.value) }}
              </span>
            </td>
            <!-- Cells -->
            <template v-for="(combo, ci) in columnCombos" :key="ci">
              <td v-for="(v, vi) in values" :key="ci+'-'+vi"
                class="px-2 py-1 text-right tabular-nums" :class="{ 'border-l': vi === 0 && colDims.length }"
                :style="cellBorderStyle">{{ fmtCell(cellValue(node.rows, combo, v), v) }}</td>
            </template>
            <td v-if="showTotalCol" class="px-2 py-1 text-right tabular-nums font-medium border-l" :style="cellBorderStyle">
              {{ fmtCell(totalCellValue(node.rows, values[0]), values[0]) }}
              <template v-if="values.length > 1"> <!-- multi-metric total: show first metric only for compactness --></template>
            </td>
          </tr>
        </tbody>

        <tfoot v-if="config.showColumnTotals">
          <tr class="font-semibold border-t-2" :style="grandTotalRowStyle">
            <td class="sticky left-0 z-10 px-2 py-1.5" :style="grandTotalRowStyle">{{ config.grandTotalLabel || 'Grand total' }}</td>
            <template v-for="(combo, ci) in columnCombos" :key="'t'+ci">
              <td v-for="(v, vi) in values" :key="'t'+ci+'-'+vi"
                class="px-2 py-1.5 text-right tabular-nums" :class="{ 'border-l': vi === 0 && colDims.length }"
                :style="cellBorderStyle">{{ fmtCell(cellValue(config.rows, combo, v), v) }}</td>
            </template>
            <td v-if="showTotalCol" class="px-2 py-1.5 text-right tabular-nums border-l" :style="cellBorderStyle">
              {{ fmtCell(totalCellValue(config.rows, values[0]), values[0]) }}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { PivotTableWidgetConfig, PivotValue } from '~/types/dashboard'
import { formatNumericValue } from '~/utils/numberFormat'
import { useDashboardStore } from '~/stores/dashboard'

const props = defineProps<{
  widgetId: string
  config: PivotTableWidgetConfig
  editMode?: boolean
}>()

const store = useDashboardStore()

// ── Column resize (edit mode) ────────────────────────────────────────────────
// Widths keyed by 'rowHeader' for the left label column, and by the value
// column key for data columns (one width applies across every column-combo).
const MIN_COL_W = 48
const DEFAULT_MIN_COL_W = 96
const liveWidths = ref<Record<string, number>>({})

function valueKey(v: PivotValue): string {
  return v.column ?? v.label ?? ''
}

// Default width fits the header label on one line: ~7.5px/char + padding slack.
function estimateColWidth(label: string): number {
  return Math.max(DEFAULT_MIN_COL_W, Math.round(label.length * 7.5) + 48)
}

function pivotHeaderLabel(key: string): string {
  if (key === 'rowHeader') return rowHeaderLabel.value
  const v = values.value.find(v => valueKey(v) === key)
  return v ? (v.label || v.column || '') : key
}

function pivotColWidth(key: string): number {
  return liveWidths.value[key] ?? props.config.columnWidths?.[key] ?? estimateColWidth(pivotHeaderLabel(key))
}

const totalColWidth = computed(() => estimateColWidth(props.config.grandTotalLabel || 'Total'))

const totalWidth = computed(() => {
  let w = pivotColWidth('rowHeader')
  for (const _combo of columnCombos.value) {
    for (const v of values.value) w += pivotColWidth(valueKey(v))
  }
  if (showTotalCol.value) w += totalColWidth.value
  return w
})

function startPivotResize(e: MouseEvent, key: string) {
  const startX = e.clientX
  const startW = (e.target as HTMLElement).closest('th')?.offsetWidth ?? pivotColWidth(key)
  const onMove = (ev: MouseEvent) => {
    liveWidths.value = { ...liveWidths.value, [key]: Math.max(MIN_COL_W, startW + ev.clientX - startX) }
  }
  const onUp = () => {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
    const w = liveWidths.value[key]
    liveWidths.value = {}
    if (w == null) return
    const columnWidths = { ...(props.config.columnWidths ?? {}), [key]: Math.round(w) }
    store.updateWidgetConfig(props.widgetId, { type: 'pivot_table', config: { ...props.config, columnWidths } })
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

// Reactive theme — drives dark-aware defaults for the config-driven inline
// surface/border colors (which can't use Tailwind `dark:` variants).
const colorMode = useColorMode()
const isDark = computed(() => colorMode.value === 'dark')

const rowDims = computed(() => props.config.rowDimensions ?? [])
const colDims = computed(() => props.config.columnDimensions ?? [])
const values = computed(() => props.config.values ?? [])
const rows = computed(() => props.config.rows ?? [])

const isEmptyState = computed(() => !rowDims.value.length || !values.value.length)
const showTotalCol = computed(() => !!props.config.showRowTotals && colDims.value.length > 0)
const rowHeaderLabel = computed(() => rowDims.value.map(d => d.label || d.column).join(' / '))

// ── Aggregation ───────────────────────────────────────────────────────────────
function aggregate(vals: any[], agg: string): number | null {
  const nonNull = vals.filter(v => v != null && v !== '')
  if (agg === 'count') return nonNull.length
  if (agg === 'countDistinct') return new Set(nonNull).size
  const nums = nonNull.map(Number).filter(n => isFinite(n))
  if (!nums.length) return null
  const sum = nums.reduce((a, b) => a + b, 0)
  switch (agg) {
    case 'sum': return sum
    case 'average': return sum / nums.length
    case 'min': return Math.min(...nums)
    case 'max': return Math.max(...nums)
    case 'median': {
      const s = [...nums].sort((a, b) => a - b); const m = Math.floor(s.length / 2)
      return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
    }
    case 'variance': case 'stdDev': {
      const mean = sum / nums.length
      const varc = nums.reduce((a, b) => a + (b - mean) ** 2, 0) / nums.length
      return agg === 'stdDev' ? Math.sqrt(varc) : varc
    }
    default: return sum
  }
}

// ── Column combos (distinct value tuples of the column dimensions) ─────────────
const columnCombos = computed<any[][]>(() => {
  if (!colDims.value.length) return [[]]
  const seen = new Set<string>(); const combos: any[][] = []
  for (const row of rows.value) {
    const combo = colDims.value.map(d => row[d.column])
    const key = combo.map(String).join(' ')
    if (!seen.has(key)) { seen.add(key); combos.push(combo) }
  }
  combos.sort((a, b) => a.map(String).join(' ').localeCompare(b.map(String).join(' ')))
  const lim = props.config.columnLimit
  return lim && lim > 0 ? combos.slice(0, lim) : combos
})

function comboMatch(row: Record<string, any>, combo: any[]): boolean {
  if (!combo.length) return true
  return colDims.value.every((d, k) => String(row[d.column]) === String(combo[k]))
}

function cellValue(nodeRows: Record<string, any>[], combo: any[], v: PivotValue): number | null {
  const matched = combo.length ? nodeRows.filter(r => comboMatch(r, combo)) : nodeRows
  return aggregate(matched.map(r => r[v.column]), v.aggregation)
}
function totalCellValue(nodeRows: Record<string, any>[], v: PivotValue): number | null {
  return aggregate(nodeRows.map(r => r[v.column]), v.aggregation)
}

// ── Row hierarchy tree ────────────────────────────────────────────────────────
interface PivotNode { key: string; depth: number; value: any; rows: Record<string, any>[]; children: PivotNode[] | null }

function sortEntries(entries: { v: any; rows: Record<string, any>[] }[]) {
  const sortBy = props.config.sortBy
  const dir = props.config.sortDir === 'asc' ? 1 : -1
  if (sortBy) {
    const metric = values.value.find(v => v.column === sortBy)
    const agg = metric?.aggregation ?? 'sum'
    return entries.sort((a, b) => {
      const av = aggregate(a.rows.map(r => r[sortBy]), agg) ?? -Infinity
      const bv = aggregate(b.rows.map(r => r[sortBy]), agg) ?? -Infinity
      return (av < bv ? -1 : av > bv ? 1 : 0) * dir
    })
  }
  // default: by dimension value ascending
  return entries.sort((a, b) => String(a.v).localeCompare(String(b.v)))
}

function buildTree(srcRows: Record<string, any>[], depth: number, prefix: string): PivotNode[] {
  const dim = rowDims.value[depth]
  const order: any[] = []; const map = new Map<any, Record<string, any>[]>()
  for (const row of srcRows) {
    const val = row[dim.column]
    if (!map.has(val)) { map.set(val, []); order.push(val) }
    map.get(val)!.push(row)
  }
  let entries = order.map(v => ({ v, rows: map.get(v)! }))
  entries = sortEntries(entries)
  if (depth === 0 && props.config.rowLimit && props.config.rowLimit > 0) {
    entries = entries.slice(0, props.config.rowLimit)
  }
  return entries.map(e => {
    const key = prefix + '/' + String(e.v)
    const node: PivotNode = { key, depth, value: e.v, rows: e.rows, children: null }
    if (depth + 1 < rowDims.value.length) node.children = buildTree(e.rows, depth + 1, key)
    return node
  })
}

const tree = computed<PivotNode[]>(() => rowDims.value.length ? buildTree(rows.value, 0, '') : [])

// ── Expand / collapse ─────────────────────────────────────────────────────────
const overrides = ref<Record<string, boolean>>({})
function expandedSet(node: PivotNode): boolean {
  if (props.config.expandCollapse === false) return true
  if (node.key in overrides.value) return overrides.value[node.key]
  return node.depth < (props.config.defaultExpandLevel ?? 0)
}
function toggle(node: PivotNode) {
  overrides.value = { ...overrides.value, [node.key]: !expandedSet(node) }
}

const flatRows = computed<PivotNode[]>(() => {
  const out: PivotNode[] = []
  const walk = (nodes: PivotNode[]) => {
    for (const node of nodes) {
      out.push(node)
      if (node.children && expandedSet(node)) walk(node.children)
    }
  }
  walk(tree.value)
  return out
})

// ── Formatting ────────────────────────────────────────────────────────────────
function fmtLabel(v: any): string {
  return v == null || v === '' ? missingText() : String(v)
}
function missingText(): string {
  switch (props.config.missingDataDisplay) {
    case 'blank': return ''
    case 'zero': return '0'
    case 'noData': return 'No data'
    case 'null': return 'null'
    default: return '—'
  }
}
function fmtCell(value: number | null, v: PivotValue): string {
  if (value == null) return missingText()
  return formatNumericValue(value, {
    format: v.format as any,
    decimalPlaces: v.decimalPlaces,
  })
}

// ── Style ─────────────────────────────────────────────────────────────────────
const containerStyle = computed(() => {
  const s: Record<string, string> = {}
  if (props.config.borderWidth && props.config.borderWidth > 0) {
    s.border = `${props.config.borderWidth}px ${props.config.borderStyle ?? 'solid'} ${props.config.borderColor ?? 'var(--line)'}`
  }
  if (props.config.borderRadius && props.config.borderRadius > 0) s.borderRadius = `${props.config.borderRadius}px`
  if (props.config.fontColor) s.color = props.config.fontColor
  return s
})
const fontClass = computed(() => {
  const c: string[] = []
  switch (props.config.fontFamily) {
    case 'sans': c.push('font-sans'); break
    case 'serif': c.push('font-serif'); break
    case 'mono': c.push('font-mono'); break
  }
  switch (props.config.fontSize ?? 'sm') {
    case 'xs': c.push('text-[11px]'); break
    case 'sm': c.push('text-xs'); break
    case 'md': c.push('text-[13px]'); break
    case 'lg': c.push('text-sm'); break
  }
  return c.join(' ')
})
const headerBg = computed(() => props.config.headerBackground || (isDark.value ? '#262626' : '#f9fafb'))
const cellBorder = computed(() => props.config.cellBorderColor || (isDark.value ? '#404040' : '#f1f1f4'))
const headerCellStyle = computed(() => ({ background: headerBg.value, borderColor: cellBorder.value, borderBottom: `1px solid ${cellBorder.value}` }))
const cellBorderStyle = computed(() => ({ borderColor: cellBorder.value }))
const grandTotalRowStyle = computed(() => ({ background: headerBg.value, borderColor: cellBorder.value }))
const tableStyle = computed(() => ({ width: totalWidth.value + 'px', minWidth: '100%' }))
// Striped fallback: when stripedRows is on but no explicit odd/even color, use a light alt bg.
function stripeBg(i: number): string | undefined {
  const odd = props.config.oddRowColor
  const even = props.config.evenRowColor
  const explicit = i % 2 === 0 ? even : odd
  if (explicit) return explicit
  if (props.config.stripedRows) return i % 2 === 0 ? undefined : (isDark.value ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.025)')
  return undefined
}
function rowStyle(i: number) {
  const bg = stripeBg(i)
  return { borderBottom: `1px solid ${cellBorder.value}`, ...(bg ? { background: bg } : {}) }
}
function rowHeaderStyle(i: number) {
  return { background: stripeBg(i) || (isDark.value ? '#262626' : '#fff'), borderColor: cellBorder.value }
}
</script>
