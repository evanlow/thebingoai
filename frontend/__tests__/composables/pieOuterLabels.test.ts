import { describe, it, expect } from 'vitest'
import { resolveColumn } from '~/composables/pieOuterLabels'

// Minimal Item shape resolveColumn touches (targetY / y).
const mk = (targetY: number) => ({ targetY, y: 0 } as any)

describe('resolveColumn', () => {
  it('separates colliding labels by at least lineHeight', () => {
    const items = [mk(100), mk(105), mk(108)] // all within 8px, need 15px apart
    resolveColumn(items, 0, 400, 15)
    for (let i = 1; i < items.length; i++) {
      expect(items[i].y - items[i - 1].y).toBeGreaterThanOrEqual(15 - 0.001)
    }
  })

  it('keeps sorted order and stays within bounds', () => {
    const items = [mk(390), mk(395), mk(398)] // clustered near the bottom edge
    resolveColumn(items, 0, 400, 15)
    expect(items[0].y).toBeGreaterThanOrEqual(0)
    expect(items[items.length - 1].y).toBeLessThanOrEqual(400 + 0.001)
    for (let i = 1; i < items.length; i++) {
      expect(items[i].y).toBeGreaterThan(items[i - 1].y)
    }
  })

  it('leaves already-spaced labels untouched', () => {
    const items = [mk(50), mk(100), mk(150)]
    resolveColumn(items, 0, 400, 15)
    expect(items.map(i => i.y)).toEqual([50, 100, 150])
  })
})
