import { describe, it, expect } from 'vitest'
import { toLocalInputValue, localInputToUtcIso } from '~/utils/backfillTime'

describe('utils/backfillTime', () => {
  describe('toLocalInputValue', () => {
    it('formats a Date as YYYY-MM-DDTHH:mm in local time', () => {
      const d = new Date(2024, 5, 3, 14, 30) // local: Jun 3, 2024 14:30
      expect(toLocalInputValue(d)).toBe('2024-06-03T14:30')
    })

    it('zero-pads month, day, hour and minute', () => {
      const d = new Date(2024, 0, 5, 9, 7) // local: Jan 5, 2024 09:07
      expect(toLocalInputValue(d)).toBe('2024-01-05T09:07')
    })
  })

  describe('localInputToUtcIso', () => {
    it('round-trips a Date through the input value preserving the instant', () => {
      // toLocalInputValue + localInputToUtcIso must not shift the moment in time
      // (the bug was tagging local wall-clock as +00:00, shifting by the offset).
      const d = new Date(2024, 5, 3, 12, 0)
      expect(localInputToUtcIso(toLocalInputValue(d))).toBe(d.toISOString())
    })

    it('returns a Z-suffixed UTC ISO string', () => {
      const iso = localInputToUtcIso('2024-06-03T12:00')
      expect(iso).toMatch(/Z$/)
      // Equivalent to interpreting the input as local time.
      expect(iso).toBe(new Date(2024, 5, 3, 12, 0).toISOString())
    })
  })
})
