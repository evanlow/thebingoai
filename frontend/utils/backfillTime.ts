/**
 * Helpers for the pipeline "Load history" (backfill) datetime field.
 *
 * `<input type="datetime-local">` always renders and edits wall-clock time in
 * the browser's LOCAL timezone and carries no offset. The backend expects an
 * absolute UTC instant, so we convert local → UTC explicitly. (The previous
 * inline code tagged the local value as `+00:00`, shifting the instant by the
 * user's offset.)
 */

/** Format a Date as a `datetime-local` value (YYYY-MM-DDTHH:mm) in local time. */
export function toLocalInputValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** Convert a `datetime-local` value (local wall-clock) to a UTC ISO string.
 *  `new Date(localValue)` parses the value as local time. */
export function localInputToUtcIso(localValue: string): string {
  return new Date(localValue).toISOString()
}
