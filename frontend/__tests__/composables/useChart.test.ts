import { describe, it, expect } from 'vitest'
import { applyDefaultColors } from '~/composables/useChart'

describe('applyDefaultColors — scatter defaults', () => {
  const scatterPoints = [{ x: 1, y: 2 }, { x: 3, y: 4 }] as any

  it('scatter: datalabels off and points visible by default', () => {
    const [ds] = applyDefaultColors([{ label: 'Scatter', data: scatterPoints }], 'scatter')
    expect((ds as any).datalabels.display).toBe(false)
    expect((ds as any).pointRadius).toBe(3)
  })

  it('scatter: explicit showDataLabels wins', () => {
    const [ds] = applyDefaultColors(
      [{ label: 'Scatter', data: scatterPoints, showDataLabels: true } as any],
      'scatter'
    )
    expect((ds as any).datalabels.display).toBe(true)
  })

  it('bar: datalabels still default on', () => {
    const [ds] = applyDefaultColors([{ label: 'Sales', data: [1, 2, 3] }], 'bar')
    expect((ds as any).datalabels.display).toBe(true)
  })
})
