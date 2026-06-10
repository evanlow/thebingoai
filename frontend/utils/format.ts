import { formatDistanceToNow, format as dateFnsFormat, isToday, isYesterday, isSameDay } from 'date-fns'

/**
 * Parses a date string as UTC, appending Z when no timezone designator is present.
 * The backend stores timezone-naive datetimes (UTC) and serializes them without Z,
 * so without this fix JavaScript treats them as local time instead of UTC.
 */
export function parseUtcDate(date: string | Date): Date {
  if (date instanceof Date) return date
  const s = date.trim()
  if (!s.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(s)) {
    return new Date(s + 'Z')
  }
  return new Date(s)
}

/**
 * Formats a date to a relative time string (e.g., "2 hours ago")
 */
export function timeAgo(date: string | Date): string {
  return formatDistanceToNow(parseUtcDate(date), { addSuffix: true })
}

/**
 * Formats a date to a specific format
 */
export function formatDate(date: string | Date, formatStr: string = 'MMM d, yyyy HH:mm'): string {
  return dateFnsFormat(parseUtcDate(date), formatStr)
}

/**
 * Returns a human-readable date label: "Today", "Yesterday", or "Month D, YYYY"
 */
export function formatDateLabel(date: string | Date): string {
  const d = parseUtcDate(date)
  if (isToday(d)) return 'Today'
  if (isYesterday(d)) return 'Yesterday'
  return dateFnsFormat(d, 'MMMM d, yyyy')
}

export { isSameDay }

/**
 * Formats a byte count as a human-readable size using binary units (e.g., "38.2 GB").
 */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  let value = bytes
  let i = 0
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024
    i++
  }
  const rounded = i === 0 ? value : Math.round(value * 10) / 10
  return `${rounded} ${units[i]}`
}

/**
 * Formats a duration in seconds as a short string (e.g., "8.4s", "5m 8s", "1h 3m").
 */
export function formatDurationShort(seconds: number | null | undefined): string {
  if (seconds == null || seconds < 0) return '—'
  if (seconds < 60) return `${Math.round(seconds * 10) / 10}s`
  const total = Math.round(seconds)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) return `${h}h ${m}m`
  return `${m}m ${s}s`
}

/**
 * Truncates a string to a maximum length with ellipsis
 */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str
  return `${str.slice(0, maxLength)}...`
}
