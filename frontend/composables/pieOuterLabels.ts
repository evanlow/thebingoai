import type { Plugin } from 'chart.js'

// Hybrid slice-label plugin for pie/doughnut:
//   • If the label fits inside its slice, draw it centered inside (contrast-
//     colored so it stays readable on light or dark slice fills).
//   • If it doesn't fit (thin slice), push it OUTSIDE the arc.
//   • Outside labels are de-collided per side and connected with a leader line
//     back to their slice; the smallest slices' labels drop when the column
//     runs out of vertical room.
// Re-runs on every draw, so it reflows automatically as the widget resizes.
//
// Options (chart.options.plugins.pieOuterLabels):
//   display: boolean               — master toggle (mode !== 'none')
//   color: string                  — outside text + leader-line color (theme-aware)
//   font: { size, weight, family } — label font
//   formatter: (value, index) => string

export interface PieOuterLabelsOptions {
  display?: boolean
  color?: string
  font?: { size?: number, weight?: string, family?: string }
  formatter?: (value: number, index: number) => string
}

interface OutsideItem {
  index: number
  value: number
  side: 1 | -1         // +1 right, -1 left
  targetY: number      // ideal label y (before de-collide)
  y: number            // resolved label y
  text: string
  edgeX: number        // point on the arc's outer edge
  edgeY: number
}

interface InsideItem { x: number, y: number, text: string }

// De-collide a column of labels sorted by targetY: push apart by lineHeight,
// clamp within [top, bottom]. Two passes (down then up) settle the stack.
export function resolveColumn(items: OutsideItem[], top: number, bottom: number, lineHeight: number) {
  items.sort((a, b) => a.targetY - b.targetY)
  let prev = -Infinity
  for (const it of items) {
    it.y = Math.max(it.targetY, top, prev + lineHeight)
    prev = it.y
  }
  if (items.length && items[items.length - 1].y > bottom) {
    items[items.length - 1].y = bottom
    for (let i = items.length - 2; i >= 0; i--) {
      if (items[i].y > items[i + 1].y - lineHeight) items[i].y = items[i + 1].y - lineHeight
    }
  }
}

export const pieOuterLabelsPlugin: Plugin = {
  id: 'pieOuterLabels',

  afterDatasetsDraw(chart, _args, opts: PieOuterLabelsOptions) {
    const type = (chart.config as any).type
    if (type !== 'pie' && type !== 'doughnut') return
    if (!opts || opts.display === false) return

    const meta = chart.getDatasetMeta(0)
    if (!meta || !meta.data || meta.data.length === 0) return
    const dataset = chart.data.datasets[0]
    if (!dataset) return

    const { ctx, chartArea } = chart
    const themeColor = opts.color ?? '#374151'
    const fontSize = opts.font?.size ?? 11
    const fontWeight = opts.font?.weight ?? 'bold'
    const fontFamily = opts.font?.family ?? 'sans-serif'
    const lineHeight = fontSize + 5
    const gap = 18          // leader-line length beyond the arc
    const textPad = 4

    ctx.save()
    ctx.font = `${fontWeight} ${fontSize}px ${fontFamily}`
    ctx.textBaseline = 'middle'

    const inside: InsideItem[] = []
    const left: OutsideItem[] = []
    const right: OutsideItem[] = []

    meta.data.forEach((arc: any, index: number) => {
      const value = Number((dataset.data as any[])[index])
      if (!Number.isFinite(value)) return
      const props = arc.getProps(['x', 'y', 'startAngle', 'endAngle', 'innerRadius', 'outerRadius', 'circumference'], true)
      if (!props.circumference) return   // hidden / zero slice
      const cx = props.x
      const cy = props.y
      const mid = (props.startAngle + props.endAngle) / 2
      const or = props.outerRadius
      const ir = props.innerRadius || 0
      const span = props.endAngle - props.startAngle
      const text = opts.formatter ? opts.formatter(value, index) : String(value)
      if (!text) return

      // Does the label fit inside the slice? Compare its width against the arc
      // length at the label radius, and the font height against the ring depth.
      const rMid = ir > 0 ? (ir + or) / 2 : or * 0.62
      const arcLen = rMid * span
      const radialDepth = ir > 0 ? (or - ir) : or
      const textWidth = ctx.measureText(text).width
      const fitsInside = textWidth <= arcLen - 6 && fontSize <= radialDepth - 4

      if (fitsInside) {
        inside.push({
          x: cx + Math.cos(mid) * rMid,
          y: cy + Math.sin(mid) * rMid,
          text,
        })
        return
      }

      const side: 1 | -1 = Math.cos(mid) >= 0 ? 1 : -1
      ;(side === 1 ? right : left).push({
        index, value, side,
        edgeX: cx + Math.cos(mid) * or,
        edgeY: cy + Math.sin(mid) * or,
        targetY: cy + Math.sin(mid) * (or + gap),
        y: 0,
        text,
      })
    })

    // Inside labels: plain fill (no outline) to match other charts' datalabels.
    ctx.textAlign = 'center'
    ctx.fillStyle = themeColor
    for (const it of inside) {
      ctx.fillText(it.text, it.x, it.y)
    }

    // Outside labels: de-collide per side, drop smallest when a column overflows.
    const available = chartArea.bottom - chartArea.top
    const maxPerSide = Math.max(0, Math.floor(available / lineHeight))
    const trim = (items: OutsideItem[]) =>
      items.length <= maxPerSide ? items : [...items].sort((a, b) => b.value - a.value).slice(0, maxPerSide)
    const rightKept = trim(right)
    const leftKept = trim(left)
    resolveColumn(rightKept, chartArea.top, chartArea.bottom, lineHeight)
    resolveColumn(leftKept, chartArea.top, chartArea.bottom, lineHeight)

    ctx.fillStyle = themeColor
    ctx.strokeStyle = themeColor
    ctx.lineWidth = 1
    const drawOutside = (items: OutsideItem[]) => {
      for (const it of items) {
        const el = chart.getDatasetMeta(0).data[it.index] as any
        const cx = el.x
        const or = el.outerRadius
        const bendX = cx + it.side * (or + gap * 0.55)
        const textX = cx + it.side * (or + gap)
        ctx.beginPath()
        ctx.moveTo(it.edgeX, it.edgeY)
        ctx.lineTo(bendX, it.y)
        ctx.lineTo(textX, it.y)
        ctx.stroke()
        ctx.textAlign = it.side === 1 ? 'left' : 'right'
        ctx.fillText(it.text, textX + it.side * textPad, it.y)
      }
    }
    drawOutside(rightKept)
    drawOutside(leftKept)
    ctx.restore()
  },
}
