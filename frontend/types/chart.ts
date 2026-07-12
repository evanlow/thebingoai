// Chart type union
export type ChartType = 'line' | 'bar' | 'pie' | 'doughnut' | 'area' | 'scatter' | 'bubble' | 'funnel' | 'timeline'

// Entrance animation types (Anime.js)
export type EntranceAnimation = 'fadeIn' | 'slideUp' | 'grow' | 'none'

// ── New helper types ─────────────────────────────────────────────────────────
export type MissingDataMode = 'lineToZero' | 'breaks' | 'linearInterpolation'
export type TrendlineType = 'none' | 'linear' | 'polynomial' | 'exponential' | 'movingAverage'
export type ChartLineStyle = 'solid' | 'dashed' | 'dotted'
export type ChartFontFamily = 'system' | 'sans' | 'serif' | 'mono'
export type ChartFontSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl'

export interface TrendlineConfig {
  type: TrendlineType
  period?: number         // for movingAverage (window size)
  color?: string
  weight?: number         // 1..6
  style?: ChartLineStyle
}

export interface ReferenceLine {
  id?: string             // for keyed v-for
  value: number
  label?: string
  color?: string
  weight?: number
  style?: ChartLineStyle
  axis?: 'y' | 'x'       // default 'y'
}

export interface ReferenceBand {
  id?: string             // for keyed v-for
  from: number
  to: number
  label?: string
  color?: string
  axis?: 'y' | 'x'       // default 'y'
}

export interface ChartAxisConfig {
  showTitle?: boolean
  title?: string
  showLabels?: boolean
  labelRotation?: number  // 0..90
  showLine?: boolean
  min?: number
  max?: number
  tickInterval?: number
  logScale?: boolean
}

// ── Dataset configuration ────────────────────────────────────────────────────
export interface DatasetConfig {
  label: string
  data: number[]
  backgroundColor?: string | string[]
  borderColor?: string | string[]
  borderWidth?: number
  fill?: boolean
  tension?: number
  pointRadius?: number
  pointBackgroundColor?: string
  // Per-series controls
  seriesType?: 'line' | 'bars'    // combo support; defaults to chart-level type
  lineWeight?: number             // 1..6 (overrides borderWidth for lines)
  lineStyle?: ChartLineStyle      // applies via borderDash
  showPoints?: boolean            // false → pointRadius=0
  stepped?: boolean               // stepped lines
  gradient?: boolean              // area fill under line
  cumulative?: boolean            // running-sum transform
  showDataLabels?: boolean        // per-dataset datalabels override
  yAxisID?: 'left' | 'right'      // dual-axis assignment
  trendline?: TrendlineConfig
}

// ── Animation configuration ──────────────────────────────────────────────────
export interface ChartAnimationConfig {
  entrance?: EntranceAnimation
  entranceDuration?: number       // ms, default 600
  entranceDelay?: number          // ms, default 0
  chartAnimation?: boolean        // Chart.js data animations, default true
}

// ── Chart-level options ──────────────────────────────────────────────────────
export interface ChartOptions {
  // Existing options
  responsive?: boolean
  maintainAspectRatio?: boolean
  aspectRatio?: number
  showLegend?: boolean
  legendPosition?: 'top' | 'bottom' | 'left' | 'right'
  showGrid?: boolean
  showTooltips?: boolean
  // back-compat: true|false still tolerated by the renderer
  stacked?: boolean | 'none' | 'standard' | 'percentage'
  indexAxis?: 'x' | 'y'
  sortBy?: 'none' | 'label' | 'value'
  sortDirection?: 'asc' | 'desc'
  showValues?: boolean
  roundValues?: boolean
  decimalPlaces?: number
  sliceLabel?: 'none' | 'value' | 'percentage' | 'label'  // pie/doughnut slice label (Data Studio parity)

  // Setup
  xAxisMode?: 'category' | 'date'   // date = time-series semantics (category scale, date labels)
  numberOfPoints?: number           // cap displayed points (category mode)
  smooth?: boolean                  // global smoothing (per-dataset tension wins)

  // Missing data (most meaningful when xAxisMode='date')
  missingData?: MissingDataMode

  // Reference lines & bands
  referenceLines?: ReferenceLine[]
  referenceBands?: ReferenceBand[]

  // Axes
  xAxis?: ChartAxisConfig
  yAxisLeft?: ChartAxisConfig
  yAxisRight?: ChartAxisConfig
  alignBothAxesToZero?: boolean
  reverseXAxis?: boolean
  reverseYAxis?: boolean

  // Grid
  showXGridLines?: boolean
  showYGridLines?: boolean
  gridLineStyle?: ChartLineStyle
  gridLineColor?: string
  gridBackground?: string

  // Legend extensions
  legendAlignment?: 'start' | 'center' | 'end'
  legendFontFamily?: ChartFontFamily
  legendFontSize?: ChartFontSize
  legendFontColor?: string

  // Title styling
  showTitle?: boolean
  titlePosition?: 'top' | 'bottom'
  titleAlignment?: 'left' | 'center' | 'right'
  titleFontFamily?: ChartFontFamily
  titleFontSize?: ChartFontSize
  titleFontColor?: string

  // Base font (applies to legend / axis labels / title as a fallback; per-element wins)
  fontFamily?: ChartFontFamily
  fontSize?: ChartFontSize
  fontColor?: string

  // Funnel (chart type 'funnel')
  funnelShape?: 'smoothed' | 'stepped'
  funnelLabelMode?: 'number' | 'percentage' | 'numberPercentage'
  funnelPercentType?: 'max' | 'previous'      // basis when label mode shows a percentage
  funnelColorMode?: 'single' | 'byValue'      // single shade vs one palette color per bar

  // Timeline (chart type 'timeline')
  timelineGroupByRowLabel?: boolean           // collapse same-row-label bars onto one lane
  timelineColorBy?: 'row' | 'bar'             // color basis for bars
  timelineAltRows?: boolean                   // alternating row background

  // Background & border (widget wrapper)
  backgroundColor?: string
  opacity?: number
  borderColor?: string
  borderStyle?: 'solid' | 'dashed' | 'dotted' | 'none'
  borderWidth?: number     // 0..5 px
  borderRadius?: number    // 0..16 px
  addBorderShadow?: boolean
}

// ── Main chart config ────────────────────────────────────────────────────────
export interface ChartConfig {
  type: ChartType
  title?: string
  description?: string
  data: {
    labels: string[]
    datasets: DatasetConfig[]
  }
  options?: ChartOptions
  animation?: ChartAnimationConfig
}

export interface DashboardConfig {
  id: string
  title: string
  description?: string
  charts: ChartConfig[]
  createdAt?: string
  updatedAt?: string
}
