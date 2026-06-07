import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { timeAgo, formatDate, formatDateLabel, truncate, formatBytes, formatDurationShort } from '~/utils/format'

describe('utils/format', () => {
  describe('timeAgo', () => {
    it('returns a string containing "ago"', () => {
      const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000)
      const result = timeAgo(oneHourAgo)
      expect(result).toContain('ago')
    })
  })

  describe('formatDate', () => {
    it('formats with default format (MMM d, yyyy HH:mm)', () => {
      const date = new Date(2024, 0, 15, 14, 30) // Jan 15, 2024 14:30
      const result = formatDate(date)
      expect(result).toBe('Jan 15, 2024 14:30')
    })

    it('formats with a custom format string', () => {
      const date = new Date(2024, 5, 3) // June 3, 2024
      const result = formatDate(date, 'yyyy-MM-dd')
      expect(result).toBe('2024-06-03')
    })
  })

  describe('formatDateLabel', () => {
    it('returns "Today" for today\'s date', () => {
      const today = new Date()
      expect(formatDateLabel(today)).toBe('Today')
    })

    it('returns "Yesterday" for yesterday\'s date', () => {
      const yesterday = new Date()
      yesterday.setDate(yesterday.getDate() - 1)
      expect(formatDateLabel(yesterday)).toBe('Yesterday')
    })

    it('returns "Month D, YYYY" format for older dates', () => {
      const oldDate = new Date(2023, 2, 15) // March 15, 2023
      expect(formatDateLabel(oldDate)).toBe('March 15, 2023')
    })
  })

  describe('truncate', () => {
    it('returns the original string when within the limit', () => {
      expect(truncate('hello', 10)).toBe('hello')
    })

    it('truncates with "..." when over the limit', () => {
      expect(truncate('hello world', 5)).toBe('hello...')
    })
  })

  describe('formatBytes', () => {
    it('returns "0 B" for null, undefined, zero and negative input', () => {
      expect(formatBytes(null)).toBe('0 B')
      expect(formatBytes(undefined)).toBe('0 B')
      expect(formatBytes(0)).toBe('0 B')
      expect(formatBytes(-5)).toBe('0 B')
    })

    it('renders raw bytes without a decimal', () => {
      expect(formatBytes(512)).toBe('512 B')
    })

    it('steps up to KB and rounds to one decimal', () => {
      expect(formatBytes(1536)).toBe('1.5 KB')
      expect(formatBytes(1024)).toBe('1 KB')
    })

    it('scales to MB/GB', () => {
      expect(formatBytes(5 * 1024 * 1024)).toBe('5 MB')
      expect(formatBytes(2 * 1024 ** 3)).toBe('2 GB')
    })

    it('caps at PB for very large values', () => {
      expect(formatBytes(1024 ** 5)).toBe('1 PB')
      expect(formatBytes(1024 ** 6)).toBe('1024 PB')  // no unit beyond PB — value keeps growing
    })
  })

  describe('formatDurationShort', () => {
    it('returns "—" for null, undefined and negative input', () => {
      expect(formatDurationShort(null)).toBe('—')
      expect(formatDurationShort(undefined)).toBe('—')
      expect(formatDurationShort(-1)).toBe('—')
    })

    it('renders sub-minute durations in seconds with one decimal', () => {
      expect(formatDurationShort(5)).toBe('5s')
      expect(formatDurationShort(5.25)).toBe('5.3s')
    })

    it('renders minutes and seconds under an hour', () => {
      expect(formatDurationShort(90)).toBe('1m 30s')
      expect(formatDurationShort(59)).toBe('59s')
    })

    it('renders hours and minutes past an hour', () => {
      expect(formatDurationShort(3661)).toBe('1h 1m')
      expect(formatDurationShort(7200)).toBe('2h 0m')
    })
  })
})
