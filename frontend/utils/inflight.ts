// Tracks in-flight widget-data fetch controllers so navigation (leaving the
// dashboard, or switching to another dashboard) can cancel pending requests
// instead of letting them resolve into a torn-down / reset store.
// Module-scoped on purpose: an AbortController must NOT live in reactive state.
const controllers = new Set<AbortController>()

/** Create a tracked AbortController; pass its `.signal` to the fetch. */
export function trackAbort(): AbortController {
  const c = new AbortController()
  controllers.add(c)
  return c
}

/** Stop tracking a controller once its request settled. */
export function releaseAbort(c: AbortController): void {
  controllers.delete(c)
}

/** Abort every in-flight tracked request (navigation / reset). */
export function abortAllInflight(): void {
  for (const c of controllers) c.abort()
  controllers.clear()
}

/** True if the error is an abort we triggered (so callers can swallow it). */
export function isAbortError(err: any): boolean {
  return err?.name === 'AbortError' || err?.cause?.name === 'AbortError'
}
