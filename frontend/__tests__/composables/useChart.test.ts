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

  it('bubble: points with r get scriptable radius scaled 4-20px', () => {
    const data = [{ x: 1, y: 1, r: 4 }, { x: 2, y: 2, r: 100 }] as any
    const [ds] = applyDefaultColors([{ label: 'Scatter', data }], 'bubble')
    const radius = (ds as any).pointRadius
    expect(typeof radius).toBe('function')
    expect(radius({ raw: data[0] })).toBeCloseTo(4)
    expect(radius({ raw: data[1] })).toBeCloseTo(20)
    expect(radius({ raw: { x: 3, y: 3 } })).toBe(3)
  })

  it('bubble: radius scale is global across datasets (1 point each)', () => {
    const small = [{ x: 1, y: 1, r: 4 }] as any
    const big = [{ x: 2, y: 2, r: 100 }] as any
    const [dsSmall, dsBig] = applyDefaultColors(
      [{ label: 'A', data: small }, { label: 'B', data: big }],
      'bubble'
    )
    expect((dsSmall as any).pointRadius({ raw: small[0] })).toBeCloseTo(4)
    expect((dsBig as any).pointRadius({ raw: big[0] })).toBeCloseTo(20)
  })
})
