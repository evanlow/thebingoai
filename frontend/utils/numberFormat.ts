/**
 * Shared numeric formatting util.
 * Replaces duplicated formatCell / formatCompact logic in Table, Pivot, and KPI renderers.
 */

export type NumericFormat = 'number' | 'currency' | 'percent' | 'date' | 'text' | 'duration' | ''

export interface FormatOptions {
  format?: NumericFormat
  decimalPlaces?: number
  compact?: boolean
}

/** K / M / B compact notation (shared with KPI). */
export function formatCompact(num: number): string {
  const abs = Math.abs(num)
  if (abs >= 1e9) return (num / 1e9).toFixed(1).replace(/\.0$/, '') + 'B'
  if (abs >= 1e6) return (num / 1e6).toFixed(1).replace(/\.0$/, '') + 'M'
  if (abs >= 1e3) return (num / 1e3).toFixed(1).replace(/\.0$/, '') + 'K'
  return num.toLocaleString()
}

/**
 * Default decimal places per format type.
 * Number → 0 (whole numbers grouped), Currency → 2, Percent → 1.
 */
function defaultDp(format?: NumericFormat): number {
  if (format === 'currency') return 2
  if (format === 'percent') return 1
  return 0
}

/**
 * Format a numeric value for display in a widget cell.
 *
 * Rules:
 * - `number` / `currency`: always group thousands; `decimalPlaces` controls fraction (default 0 / 2).
 * - Default / unset format AND the raw value is finite numeric: group thousands with 0 decimals.
 * - `percent`: `+/−` prefix, `decimalPlaces` controls fraction (default 1).
 * - `currency`: hard-coded `$` prefix (locale-agnostic, matches existing behaviour).
 * - `compact`: K/M/B override for number & currency.
 */
export function formatNumericValue(value: any, opts: FormatOptions = {}): string {
  const { format, decimalPlaces, compact } = opts
  const num = Number(value)

  // Non-numeric values fall through to string coercion (caller handles nulls)
  if (!isFinite(num)) return String(value)

  // Compact takes priority for numeric formats
  if (compact && (format === 'number' || format === 'currency' || !format)) {
    return formatCompact(num)
  }

  switch (format) {
    case 'currency': {
      const dp = decimalPlaces ?? defaultDp('currency')
      return '$' + num.toLocaleString(undefined, {
        minimumFractionDigits: dp,
        maximumFractionDigits: dp,
      })
    }

    case 'number': {
      const dp = decimalPlaces ?? defaultDp('number')
      return num.toLocaleString(undefined, {
        minimumFractionDigits: dp,
        maximumFractionDigits: dp,
      })
    }

    case 'percent': {
      const dp = decimalPlaces ?? defaultDp('percent')
      return (num > 0 ? '+' : '') + num.toFixed(dp) + '%'
    }

    default: {
      // No explicit format: if numeric, still group thousands (req 2)
      return num.toLocaleString(undefined, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      })
    }
  }
}

/** True for formats that render as a number in cells (drives right-align + tabular-nums). */
export const NUMERIC_FORMATS = new Set<string>(['number', 'currency', 'percent', 'duration'])

export function isNumericFormat(format?: string): boolean {
  return NUMERIC_FORMATS.has(format ?? '')
}
