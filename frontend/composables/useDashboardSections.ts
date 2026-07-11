import type { Ref } from 'vue'
import type { DashboardWidget, SectionColor, TextWidgetConfig } from '~/types/dashboard'
import { isSectionHeader } from '~/types/dashboard'

export interface DashboardSection {
  id: string          // header widget id — stable scroll/jump target
  title: string
  color: SectionColor
}

export interface SectionBounds {
  top: number         // px, relative to the grid wrapper
  height: number
}

/** First content line without markdown heading markers. */
export function sectionTitle(content: string): string {
  return (content ?? '').trimStart().split('\n')[0].replace(/^#+\s*/, '').trim()
}

/**
 * Derives dashboard sections from the flat widget list (a section = a
 * section-header text widget + every widget below it until the next header)
 * and measures each section's pixel bounding box from the gridstack item DOM.
 * Purely a visual layer — the grid and the persisted JSON stay flat.
 */
export function useDashboardSections(
  widgets: Ref<DashboardWidget[]>,
  wrapperRef: Ref<HTMLElement | null>,
) {
  const readingOrder = computed(() =>
    [...widgets.value].sort((a, b) => (a.position.y - b.position.y) || (a.position.x - b.position.x)),
  )

  const sections = computed<DashboardSection[]>(() =>
    readingOrder.value.filter(isSectionHeader).map((w) => {
      const config = w.widget.config as TextWidgetConfig
      return {
        id: w.id,
        title: sectionTitle(config.content),
        color: config.sectionColor ?? 'default',
      }
    }),
  )

  /** section id → member widget ids (header included). */
  const membership = computed<Map<string, string[]>>(() => {
    const map = new Map<string, string[]>()
    let current: string[] | null = null
    for (const w of readingOrder.value) {
      if (isSectionHeader(w)) {
        current = [w.id]
        map.set(w.id, current)
      } else {
        current?.push(w.id)  // widgets above the first header stay ungrouped
      }
    }
    return map
  })

  const bounds = ref<Record<string, SectionBounds>>({})

  // px beyond the members' bounding box — items already carry a 4px content
  // inset, and adjacent sections are only 8px apart, so keep this ≤ 3.
  const BAND_PAD = 2

  function measure() {
    const wrapper = wrapperRef.value
    if (!wrapper) return
    const next: Record<string, SectionBounds> = {}
    for (const [sectionId, memberIds] of membership.value) {
      let top = Infinity
      let bottom = -Infinity
      for (const id of memberIds) {
        const el = wrapper.querySelector<HTMLElement>(`[data-widget-id="${CSS.escape(id)}"]`)
        if (!el) continue
        top = Math.min(top, el.offsetTop)
        bottom = Math.max(bottom, el.offsetTop + el.offsetHeight)
      }
      if (top === Infinity) continue
      next[sectionId] = {
        top: Math.max(0, top - BAND_PAD),
        height: bottom - top + BAND_PAD * 2,
      }
    }
    bounds.value = next
  }

  let raf = 0
  let settleTimer: ReturnType<typeof setTimeout> | undefined
  function scheduleMeasure() {
    cancelAnimationFrame(raf)
    raf = requestAnimationFrame(measure)
    // gridstack animates item moves (~0.3s CSS transition) — re-measure after
    // it settles so bands land on final positions.
    clearTimeout(settleTimer)
    settleTimer = setTimeout(measure, 360)
  }

  // Any position/size/membership change (drag, resize, add/remove, text
  // auto-resize — all synced to the store by the gridstack change handler).
  watch(
    () => widgets.value.map(w => `${w.id}:${w.position.x},${w.position.y},${w.position.w},${w.position.h}`).join('|'),
    () => nextTick(scheduleMeasure),
  )
  // Header flag/color edits change sections without moving anything.
  watch([sections, membership], () => nextTick(scheduleMeasure))

  let resizeObserver: ResizeObserver | undefined
  onMounted(() => {
    scheduleMeasure()
    // Catches container reflows the store can't see: initial staggered widget
    // mount, window resize, mobile 1-column collapse.
    resizeObserver = new ResizeObserver(scheduleMeasure)
    if (wrapperRef.value) resizeObserver.observe(wrapperRef.value)
  })
  onBeforeUnmount(() => {
    resizeObserver?.disconnect()
    cancelAnimationFrame(raf)
    clearTimeout(settleTimer)
  })

  return { sections, bounds, remeasure: scheduleMeasure }
}
