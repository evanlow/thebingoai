import {
  Chart,
  LineController,
  BarController,
  PieController,
  DoughnutController,
  ScatterController,
  CategoryScale,
  LinearScale,
  LogarithmicScale,
  TimeScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Legend,
  Tooltip,
  Title,
  Filler,
  type ChartType as ChartJsType,
  type ChartOptions as ChartJsOptions,
  type ChartDataset,
} from 'chart.js'
import ChartDataLabels from 'chartjs-plugin-datalabels'
import annotationPlugin from 'chartjs-plugin-annotation'
import { pieOuterLabelsPlugin } from './pieOuterLabels'
import 'chartjs-adapter-date-fns'
import type { Ref } from 'vue'
import type { ChartConfig, ChartType, DatasetConfig, ChartLineStyle, ChartFontFamily, ChartFontSize } from '~/types/chart'
import { formatNumericValue } from '~/utils/numberFormat'

// Register all required Chart.js components once
Chart.register(
  LineController,
  BarController,
  PieController,
  DoughnutController,
  ScatterController,
  CategoryScale,
  LinearScale,
  LogarithmicScale,
  TimeScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Legend,
  Tooltip,
  Title,
  Filler,
  ChartDataLabels,
  annotationPlugin,
  pieOuterLabelsPlugin
)

const DEFAULT_PALETTE = [
  '#6366f1', // indigo-500
  '#8b5cf6', // violet-500
  '#ec4899', // pink-500
  '#f43f5e', // rose-500
  '#f97316', // orange-500
  '#eab308', // yellow-500
  '#22c55e', // green-500
  '#06b6d4', // cyan-500
]

// ── Helpers ──────────────────────────────────────────────────────────────────

function resolveChartJsType(type: ChartType): ChartJsType {
  if (type === 'area') return 'line'
  // Bubble renders through the scatter controller — point size comes from the
  // scriptable sqrt-scaled radius, not Chart.js's raw-pixel `r` handling.
  if (type === 'bubble') return 'scatter'
  return type as ChartJsType
}

function getLineDash(style?: ChartLineStyle): number[] {
  if (style === 'dashed') return [6, 4]
  if (style === 'dotted') return [2, 3]
  return []
}

function getFontSizePx(size?: ChartFontSize): number {
  const map: Record<ChartFontSize, number> = { xs: 10, sm: 11, md: 13, lg: 15, xl: 18 }
  return size ? (map[size] ?? 12) : 12
}

function getFontFamilyStr(family?: ChartFontFamily): string {
  const map: Record<ChartFontFamily, string> = {
    system: 'system-ui, sans-serif',
    sans: 'Inter, system-ui, sans-serif',
    serif: 'Georgia, serif',
    mono: 'JetBrains Mono, monospace',
  }
  return family ? (map[family] ?? 'system-ui, sans-serif') : 'system-ui, sans-serif'
}

// ── Trendline computation ─────────────────────────────────────────────────────

function linearRegression(data: number[]): number[] {
  const valid = data.map((y, i) => ({ x: i, y })).filter(p => p.y != null && !isNaN(p.y))
  if (valid.length < 2) return data.map(() => null as any)
  const n = valid.length
  const sumX = valid.reduce((s, p) => s + p.x, 0)
  const sumY = valid.reduce((s, p) => s + p.y, 0)
  const sumXY = valid.reduce((s, p) => s + p.x * p.y, 0)
  const sumX2 = valid.reduce((s, p) => s + p.x * p.x, 0)
  const denom = n * sumX2 - sumX * sumX
  if (denom === 0) return data.map(() => sumY / n)
  const m = (n * sumXY - sumX * sumY) / denom
  const b = (sumY - m * sumX) / n
  return data.map((_, i) => m * i + b)
}

function movingAverage(data: number[], period: number): number[] {
  const p = Math.max(1, period)
  return data.map((_, i) => {
    const start = Math.max(0, i - p + 1)
    const window = data.slice(start, i + 1).filter((v): v is number => v != null && !isNaN(v))
    return window.length ? window.reduce((a, b) => a + b, 0) / window.length : (null as any)
  })
}

function expRegression(data: number[]): number[] {
  const valid = data.map((y, i) => ({ x: i, y })).filter(p => p.y > 0)
  if (valid.length < 2) return data.map(() => null as any)
  const logPairs = valid.map(p => ({ x: p.x, y: Math.log(p.y) }))
  const n = logPairs.length
  const sumX = logPairs.reduce((s, p) => s + p.x, 0)
  const sumY = logPairs.reduce((s, p) => s + p.y, 0)
  const sumXY = logPairs.reduce((s, p) => s + p.x * p.y, 0)
  const sumX2 = logPairs.reduce((s, p) => s + p.x * p.x, 0)
  const denom = n * sumX2 - sumX * sumX
  if (denom === 0) return data.map(() => Math.exp(sumY / n))
  const m = (n * sumXY - sumX * sumY) / denom
  const b = (sumY - m * sumX) / n
  return data.map((_, i) => Math.exp(m * i + b))
}

function computeTrendlineDatasets(processedDatasets: ChartDataset[], origDatasets: DatasetConfig[]): ChartDataset[] {
  const result: ChartDataset[] = []
  for (let i = 0; i < origDatasets.length; i++) {
    const orig = origDatasets[i]
    const tl = orig.trendline
    if (!tl || tl.type === 'none') continue
    const baseData = (processedDatasets[i]?.data ?? orig.data) as number[]
    let trendData: number[]
    if (tl.type === 'linear') trendData = linearRegression(baseData)
    else if (tl.type === 'movingAverage') trendData = movingAverage(baseData, tl.period ?? 3)
    else if (tl.type === 'exponential') trendData = expRegression(baseData)
    else continue // polynomial not implemented in v1
    const color = tl.color ?? (processedDatasets[i] as any)?.borderColor ?? DEFAULT_PALETTE[i % DEFAULT_PALETTE.length]
    result.push({
      type: 'line' as any,
      label: `Trend: ${orig.label}`,
      data: trendData as any,
      borderColor: color,
      backgroundColor: 'transparent',
      borderWidth: tl.weight ?? 2,
      borderDash: getLineDash(tl.style ?? 'dashed'),
      pointRadius: 0,
      fill: false as any,
      tension: 0,
    } as ChartDataset)
  }
  return result
}

// ── Dataset color + style application ────────────────────────────────────────

export function applyDefaultColors(
  datasets: ChartConfig['data']['datasets'],
  type: ChartType
): ChartDataset[] {
  const isPieOrDoughnut = type === 'pie' || type === 'doughnut'
  const isLineOrArea = type === 'line' || type === 'area'
  const isScatter = type === 'scatter' || type === 'bubble'

  // Bubble sizing: one GLOBAL scale across all datasets (Data Studio parity).
  // With a Dimension each dataset holds few points — a per-dataset scale would
  // collapse (min == max) and render every bubble at the floor size.
  let scaleRadius: ((ctx: any) => number) | null = null
  if (isScatter) {
    let rMin = Infinity
    let rMax = -Infinity
    for (const ds of datasets) {
      for (const p of (ds.data as any[]) ?? []) {
        const r = p && typeof p === 'object' ? Number((p as any).r) : NaN
        if (Number.isFinite(r)) {
          if (r < rMin) rMin = r
          if (r > rMax) rMax = r
        }
      }
    }
    if (rMin !== Infinity) {
      const sMin = Math.sqrt(Math.max(rMin, 0))
      const span = Math.sqrt(Math.max(rMax, 0)) - sMin || 1
      scaleRadius = (ctx: any) => {
        const r = Number(ctx?.raw?.r)
        if (!Number.isFinite(r)) return 3
        return 4 + ((Math.sqrt(Math.max(r, 0)) - sMin) / span) * 16
      }
    }
  }

  return datasets.map((ds, i) => {
    const color = DEFAULT_PALETTE[i % DEFAULT_PALETTE.length]

    if (isPieOrDoughnut) {
      return {
        ...ds,
        backgroundColor: ds.backgroundColor ?? DEFAULT_PALETTE,
        borderColor: ds.borderColor ?? getChartColors().sliceBorderColor,
        borderWidth: ds.borderWidth ?? 2,
      } as ChartDataset
    }

    // Resolve per-series subtype for combo charts
    const resolvedType = ds.seriesType === 'bars' ? 'bar'
      : ds.seriesType === 'line' ? 'line'
      : undefined

    // Smooth: use per-ds tension, then global smooth, then type default
    const tension = ds.tension !== undefined ? ds.tension
      : isLineOrArea || ds.seriesType === 'line' ? 0.4
      : undefined

    // Gradient / fill
    const useFill = ds.gradient || type === 'area'
    const bgColor = ds.backgroundColor ?? (useFill ? `${color}33` : color)

    // Points: explicit toggle wins, otherwise default to no points (scatter: visible)
    const pointRadius = ds.showPoints === true ? (ds.pointRadius ?? 3)
      : ds.showPoints === false ? 0
      : (ds.pointRadius ?? (isScatter ? 3 : 0))

    // Per-dataset datalabels — default ON, except line series and scatter default OFF.
    const datalabels = { display: ds.showDataLabels ?? !(isLineOrArea || ds.seriesType === 'line' || isScatter) }

    const processed: Record<string, any> = {
      ...ds,
      backgroundColor: bgColor,
      borderColor: ds.borderColor ?? color,
      borderWidth: ds.lineWeight ?? ds.borderWidth ?? 2,
      fill: useFill ? true : ds.fill,
      tension,
      pointRadius,
    }

    // Bubble chart: points carrying `r` get the shared global-scale radius.
    if (scaleRadius && (ds.data as any[]).some(p => p && typeof p === 'object' && Number.isFinite(Number((p as any).r)))) {
      processed.pointRadius = scaleRadius
      processed.pointHoverRadius = scaleRadius
    }

    if (resolvedType) processed.type = resolvedType
    if (ds.lineStyle) processed.borderDash = getLineDash(ds.lineStyle)
    if (ds.stepped) processed.stepped = true
    if (ds.yAxisID === 'right') processed.yAxisID = 'y1'
    else if (ds.yAxisID === 'left' || !ds.yAxisID) processed.yAxisID = 'y'
    ;(processed as any).datalabels = datalabels

    // spanGaps for missing data (set here; overridden per chart type in options too)
    // linearInterpolation = true, breaks = false, lineToZero = already 0-filled in transform
    return processed as ChartDataset
  })
}

// ── Sort helper (unchanged) ───────────────────────────────────────────────────

function sortChartData(config: ChartConfig): { labels: string[]; datasets: ChartConfig['data']['datasets'] } {
  if (!config.data) return { labels: [], datasets: [] }
  const { labels, datasets } = config.data
  const sortBy = config.options?.sortBy
  const sortDir = config.options?.sortDirection ?? 'asc'

  if (!sortBy || sortBy === 'none' || labels.length === 0) {
    return { labels, datasets }
  }

  const indices = labels.map((_, i) => i)
  if (sortBy === 'label') {
    indices.sort((a, b) => sortDir === 'asc'
      ? String(labels[a]).localeCompare(String(labels[b]))
      : String(labels[b]).localeCompare(String(labels[a])))
  } else {
    const values = datasets[0]?.data ?? []
    indices.sort((a, b) => sortDir === 'asc'
      ? (values[a] as number ?? 0) - (values[b] as number ?? 0)
      : (values[b] as number ?? 0) - (values[a] as number ?? 0))
  }

  return {
    labels: indices.map(i => labels[i]),
    datasets: datasets.map(ds => ({ ...ds, data: indices.map(i => ds.data[i]) })),
  }
}

// ── Dark mode ─────────────────────────────────────────────────────────────────

function isDarkMode(): boolean {
  if (typeof document === 'undefined') return false
  return document.documentElement.classList.contains('dark')
}

function getChartColors() {
  const dark = isDarkMode()
  return {
    tickColor: dark ? '#a3a3a3' : '#6b7280',
    gridColor: dark ? 'rgba(163,163,163,0.15)' : 'rgba(0,0,0,0.08)',
    legendColor: dark ? '#a3a3a3' : '#374151',
    datalabelColor: dark ? '#e5e5e5' : '#374151',
    // Pie/doughnut slice seam: white in light mode, panel color (neutral-900) in dark.
    sliceBorderColor: dark ? '#171717' : '#fff',
  }
}

// ── Annotation builder ────────────────────────────────────────────────────────

function buildAnnotations(config: ChartConfig): Record<string, any> {
  const opts = config.options ?? {}
  const annotations: Record<string, any> = {}

  for (const [idx, rl] of (opts.referenceLines ?? []).entries()) {
    const id = rl.id ?? `refline-${idx}`
    const isY = (rl.axis ?? 'y') === 'y'
    annotations[id] = {
      type: 'line',
      ...(isY ? { yMin: rl.value, yMax: rl.value } : { xMin: rl.value, xMax: rl.value }),
      borderColor: rl.color ?? '#6b7280',
      borderWidth: rl.weight ?? 1,
      borderDash: getLineDash(rl.style ?? 'dashed'),
      label: {
        display: !!(rl.label),
        content: rl.label ?? '',
        position: 'end',
        font: { size: 11 },
      },
    }
  }

  for (const [idx, rb] of (opts.referenceBands ?? []).entries()) {
    const id = rb.id ?? `refband-${idx}`
    const isY = (rb.axis ?? 'y') === 'y'
    annotations[id] = {
      type: 'box',
      ...(isY
        ? { yMin: rb.from, yMax: rb.to }
        : { xMin: rb.from, xMax: rb.to }),
      backgroundColor: rb.color ?? 'rgba(99,102,241,0.10)',
      borderWidth: 0,
      label: {
        display: !!(rb.label),
        content: rb.label ?? '',
        position: 'center',
        font: { size: 11 },
      },
    }
  }

  return annotations
}

// ── Helpers: stacked coercion + value formatting ──────────────────────────────

function isStackedActive(val: any): boolean {
  return val === true || val === 'standard' || val === 'percentage'
}

// ── Main options builder ──────────────────────────────────────────────────────

function buildChartJsOptions(config: ChartConfig, enableAnimation: boolean): ChartJsOptions {
  const opts = config.options ?? {}
  const isPieOrDoughnut = config.type === 'pie' || config.type === 'doughnut'
  const isScatter = config.type === 'scatter' || config.type === 'bubble'
  const isHorizontal = !isPieOrDoughnut && !isScatter && opts.indexAxis === 'y'
  const colors = getChartColors()
  const stackedActive = isStackedActive(opts.stacked)
  const isPercentage = opts.stacked === 'percentage'

  // Determine if any dataset uses the right Y axis
  const hasRightAxis = config.data.datasets.some(ds => ds.yAxisID === 'right')

  // Grid line style
  const gridDash = getLineDash(opts.gridLineStyle)
  const gridColor = opts.gridLineColor ?? colors.gridColor

  // spanGaps based on missingData
  const spanGaps = opts.missingData === 'linearInterpolation' ? true
    : opts.missingData === 'breaks' ? false
    : undefined

  // Round values ON by default (only explicit false disables it).
  const roundValues = opts.roundValues !== false
  // Reserve datalabel padding when any series shows labels (per-series default ON).
  const anyDataLabels = config.data.datasets.some(ds => ds.showDataLabels ?? true)

  // Shared value formatter: always group thousands; K/M/B compact only when
  // rounding is on (never for percentage stacking, which keeps decimals + '%').
  const formatValue = (raw: unknown): string | number => {
    if (typeof raw !== 'number') return raw as any
    return formatNumericValue(raw, {
      format: 'number',
      decimalPlaces: opts.decimalPlaces ?? 2,
      compact: roundValues && !isPercentage,
    })
  }

  // Tooltip callback always runs so values carry thousands separators.
  const tooltipCallbacks = {
    label: (ctx: any) => {
      const label = ctx.dataset?.label ?? ''
      if (isScatter) {
        const xf = formatValue(ctx.parsed?.x)
        const yf = formatValue(ctx.parsed?.y)
        const rRaw = Number(ctx.raw?.r)
        const size = Number.isFinite(rRaw) ? `, size: ${formatValue(rRaw)}` : ''
        return `${label}: (${xf}, ${yf})${size}`
      }
      // Pie/doughnut set `ctx.parsed` to a scalar number (not an {x,y} object),
      // so read it directly instead of `.y` (which would be undefined).
      const rawVal = isPieOrDoughnut ? ctx.parsed
        : (isHorizontal ? ctx.parsed?.x : ctx.parsed?.y)
      const formatted = formatValue(rawVal)
      const suffix = isPercentage ? '%' : ''
      return `${label}: ${formatted}${suffix}`
    },
  }

  // Pie/doughnut external slice labels (drawn outside the arc with leader lines
  // by the pieOuterLabels plugin). Mode: none | value | percentage | label;
  // default percentage, honoring legacy showValues → value.
  const sliceMode = opts.sliceLabel ?? (opts.showValues ? 'value' : 'percentage')
  const pieData = (config.data.datasets[0]?.data ?? []) as unknown[]
  const pieTotal = pieData.reduce((s: number, v) => s + (typeof v === 'number' ? v : 0), 0)
  const pieLabels = config.data.labels ?? []
  const pieLabelFormatter = (value: number, index: number): string => {
    if (sliceMode === 'label') return String(pieLabels[index] ?? '')
    if (sliceMode === 'percentage') {
      if (!pieTotal) return ''
      return `${((value / pieTotal) * 100).toFixed(opts.decimalPlaces ?? 1)}%`
    }
    return String(formatValue(value))
  }

  const options: ChartJsOptions = {
    responsive: opts.responsive ?? true,
    maintainAspectRatio: opts.maintainAspectRatio ?? false,
    animation: enableAnimation ? undefined : false,
    layout: {
      // Pie/doughnut: reserve horizontal room so external slice labels + leader
      // lines aren't clipped. Others: pad for top/right datalabels.
      padding: isPieOrDoughnut
        ? (sliceMode !== 'none' ? { left: 72, right: 72, top: 16, bottom: 16 } : 0)
        : isHorizontal
          ? { right: anyDataLabels ? 28 : 0 }
          : { top: anyDataLabels ? 20 : 0 },
    },
    plugins: {
      legend: {
        // GDS parity: ungrouped scatter/bubble shows no legend pill; a
        // Dimension (multiple datasets) brings the legend back.
        display: opts.showLegend ?? !(isScatter && config.data.datasets.length <= 1),
        position: opts.legendPosition ?? 'top',
        align: (opts.legendAlignment ?? 'center') as any,
        labels: {
          color: opts.legendFontColor ?? opts.fontColor ?? colors.legendColor,
          font: {
            family: getFontFamilyStr(opts.legendFontFamily ?? opts.fontFamily),
            size: getFontSizePx(opts.legendFontSize ?? opts.fontSize),
          },
        },
      },
      tooltip: {
        enabled: opts.showTooltips ?? true,
        ...(tooltipCallbacks ? { callbacks: tooltipCallbacks } : {}),
      },
      title: {
        display: !!(opts.showTitle),
        text: config.title ?? '',
        position: (opts.titlePosition ?? 'top') as any,
        align: (opts.titleAlignment ?? 'center') as any,
        color: opts.titleFontColor ?? opts.fontColor,
        font: {
          family: getFontFamilyStr(opts.titleFontFamily ?? opts.fontFamily),
          size: getFontSizePx(opts.titleFontSize ?? opts.fontSize),
        },
      },
      // Pie/doughnut labels are drawn OUTSIDE the arc by the pieOuterLabels
      // plugin (below), so the inline datalabels plugin is off for them.
      datalabels: isPieOrDoughnut
        ? { display: false }
        : {
            display: opts.showValues ?? false,
            color: colors.datalabelColor,
            font: { size: 11, weight: 'bold' as const },
            anchor: 'end' as const,
            align: isHorizontal ? 'right' : 'top',
            formatter: (value: unknown) => {
              // Scatter datum is an {x, y} object — format like the tooltip.
              if (value && typeof value === 'object' && 'x' in value && 'y' in value) {
                const v = value as { x: unknown; y: unknown }
                return `(${formatValue(v.x)}, ${formatValue(v.y)})`
              }
              if (typeof value !== 'number') return value
              const formatted = formatValue(value)
              return isPercentage ? `${formatted}%` : formatted
            },
          },
      annotation: {
        annotations: buildAnnotations(config),
      },
      pieOuterLabels: isPieOrDoughnut
        ? {
            display: sliceMode !== 'none',
            color: colors.datalabelColor,
            font: {
              size: getFontSizePx(opts.fontSize),
              weight: 'bold' as const,
              family: getFontFamilyStr(opts.fontFamily),
            },
            formatter: pieLabelFormatter,
          }
        : { display: false },
    } as any,
  }

  if (!isPieOrDoughnut) {
    const showXGrid = opts.showXGridLines ?? opts.showGrid ?? true
    const showYGrid = opts.showYGridLines ?? opts.showGrid ?? true
    const leftCfg = opts.yAxisLeft ?? {}
    const rightCfg = opts.yAxisRight ?? {}
    const xCfg = opts.xAxis ?? {}

    // Tick callback always formats (thousands separators; K/M/B when rounding).
    const tickCallback = (value: unknown) => formatValue(value)

    // Base font (from the Style → Font section) applied to axis labels.
    const baseTickFont = { family: getFontFamilyStr(opts.fontFamily), size: getFontSizePx(opts.fontSize) }
    const baseTickColor = opts.fontColor ?? colors.tickColor

    // Time scale only when labels are real ISO dates. Bucketed category labels
    // (quarter "2024-Q1", year "2024", month "2024-03", parts "08:00"/"Mon"/"Jan")
    // can't be parsed by the date adapter → fall back to the category scale.
    const lbls = (config.data?.labels ?? []) as any[]
    const labelsAreDates = lbls.length > 0 && lbls.every(
      l => typeof l === 'string' && /^\d{4}-\d{2}-\d{2}/.test(l),
    )
    const isDateAxis = !isScatter && opts.xAxisMode === 'date' && labelsAreDates

    // Category (dimension/label) axis — physical X when vertical, Y when horizontal.
    const categoryScale: Record<string, any> = {
      // Scatter → linear; date mode → time (needs chartjs-adapter-date-fns); default → category
      type: isScatter ? 'linear' : (isDateAxis ? 'time' : 'category'),
      ...(isDateAxis ? {
        time: {
          tooltipFormat: 'MMM d, yyyy',
          displayFormats: {
            millisecond: 'HH:mm:ss.SSS',
            second: 'HH:mm:ss',
            minute: 'HH:mm',
            hour: 'MMM d, HH:mm',
            day: 'MMM d',
            week: 'MMM d',
            month: 'MMM yyyy',
            quarter: 'qqq yyyy',
            year: 'yyyy',
          },
        },
      } : {}),
      grid: {
        display: showXGrid,
        color: gridColor,
        borderDash: gridDash.length ? gridDash : undefined,
      },
      stacked: stackedActive,
      ticks: {
        color: baseTickColor,
        font: baseTickFont,
        maxRotation: xCfg.labelRotation ?? undefined,
        display: xCfg.showLabels !== false,
      },
      title: {
        display: !!(xCfg.showTitle && xCfg.title),
        text: xCfg.title ?? '',
        color: baseTickColor,
        font: baseTickFont,
      },
      border: { display: xCfg.showLine !== false },
    }

    // Value (metric) axis — physical Y when vertical, X when horizontal.
    const valueScale: Record<string, any> = {
      type: (leftCfg.logScale ? 'logarithmic' : 'linear') as any,
      grid: {
        display: showYGrid,
        color: gridColor,
        borderDash: gridDash.length ? gridDash : undefined,
      },
      stacked: stackedActive,
      ticks: {
        color: baseTickColor,
        font: baseTickFont,
        maxRotation: leftCfg.labelRotation ?? undefined,
        display: leftCfg.showLabels !== false,
        stepSize: leftCfg.tickInterval ?? undefined,
        ...(tickCallback ? { callback: tickCallback } : {}),
      },
      title: {
        display: !!(leftCfg.showTitle && leftCfg.title),
        text: leftCfg.title ?? '',
        color: baseTickColor,
        font: baseTickFont,
      },
      border: { display: leftCfg.showLine !== false },
      min: isPercentage ? (leftCfg.min ?? 0) : leftCfg.min,
      max: isPercentage ? (leftCfg.max ?? 100) : leftCfg.max,
      grace: opts.showValues ? '10%' : undefined,
    }

    // Horizontal bars (indexAxis:'y') need the value scale on X and category on Y.
    const scales: Record<string, any> = isHorizontal
      ? {
          x: { ...valueScale, position: 'bottom', reverse: opts.reverseXAxis ?? false },
          y: { ...categoryScale, position: 'left', reverse: opts.reverseYAxis ?? false },
        }
      : {
          x: { ...categoryScale, position: 'bottom', reverse: opts.reverseXAxis ?? false },
          y: { ...valueScale, position: 'left', reverse: opts.reverseYAxis ?? false },
        }

    if (hasRightAxis) {
      scales.y1 = {
        type: (rightCfg.logScale ? 'logarithmic' : 'linear') as any,
        position: 'right',
        grid: { display: false },
        ticks: {
          color: colors.tickColor,
          maxRotation: rightCfg.labelRotation ?? undefined,
          display: rightCfg.showLabels !== false,
          stepSize: rightCfg.tickInterval ?? undefined,
          ...(tickCallback ? { callback: tickCallback } : {}),
        },
        title: {
          display: !!(rightCfg.showTitle && rightCfg.title),
          text: rightCfg.title ?? '',
          color: colors.tickColor,
        },
        border: { display: rightCfg.showLine !== false },
        min: rightCfg.min,
        max: rightCfg.max,
      }
      if (opts.alignBothAxesToZero) {
        scales.y.min = scales.y.min ?? 0
        scales.y1.min = 0
      }
    }

    ;(options as any).scales = scales
    if (opts.indexAxis && !isScatter) {
      ;(options as any).indexAxis = opts.indexAxis
    }

    if (spanGaps !== undefined) {
      ;(options as any).spanGaps = spanGaps
    }
  }

  if (opts.aspectRatio !== undefined) {
    (options as any).aspectRatio = opts.aspectRatio
  }

  return options
}

// ── Composable ────────────────────────────────────────────────────────────────

export function useChart(canvasRef: Ref<HTMLCanvasElement | null>, configRef: Ref<ChartConfig>) {
  let chartInstance: Chart | null = null
  let currentChartJsType: string | null = null
  let darkModeObserver: MutationObserver | null = null

  function createChart() {
    const canvas = canvasRef.value
    if (!canvas) return

    const config = configRef.value
    if (!config.data) return
    const enableAnimation = config.animation?.chartAnimation ?? true
    const chartJsType = resolveChartJsType(config.type)
    const sorted = sortChartData(config)
    const datasets = applyDefaultColors(sorted.datasets, config.type)
    const trendlineDatasets = computeTrendlineDatasets(datasets, sorted.datasets)
    const options = buildChartJsOptions(config, enableAnimation)

    chartInstance = new Chart(canvas, {
      type: chartJsType,
      data: {
        labels: sorted.labels,
        datasets: [...datasets, ...trendlineDatasets],
      },
      options,
    })
    currentChartJsType = chartJsType
  }

  function updateChart() {
    if (!chartInstance) {
      createChart()
      return
    }

    const config = configRef.value
    const sorted = sortChartData(config)
    const datasets = applyDefaultColors(sorted.datasets, config.type)
    const trendlineDatasets = computeTrendlineDatasets(datasets, sorted.datasets)
    const enableAnimation = config.animation?.chartAnimation ?? true
    const options = buildChartJsOptions(config, enableAnimation)

    chartInstance.data.labels = sorted.labels
    chartInstance.data.datasets = [...datasets, ...trendlineDatasets] as any
    chartInstance.options = options as any
    chartInstance.update()
  }

  function destroyChart() {
    chartInstance?.destroy()
    chartInstance = null
    currentChartJsType = null
  }

  onMounted(() => {
    try {
      createChart()
    } catch (e) {
      console.warn('[useChart] Failed to create chart:', e)
    }

    if (typeof document !== 'undefined') {
      darkModeObserver = new MutationObserver(() => updateChart())
      darkModeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    }
  })

  watch(configRef, () => {
    const newType = resolveChartJsType(configRef.value.type)
    if (chartInstance && currentChartJsType !== newType) {
      destroyChart()
      createChart()
    } else {
      updateChart()
    }
  }, { deep: true, flush: 'post' })

  onBeforeUnmount(() => {
    darkModeObserver?.disconnect()
    destroyChart()
  })
}
