import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, computed, watch } from 'vue'

// ── Stub Nuxt auto-imports ───────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', watch)

// ── Mock html2canvas + jsPDF (browser-only; no canvas in happy-dom) ──
const html2canvasMock = vi.fn()
vi.mock('html2canvas', () => ({ default: html2canvasMock }))

const addImageMock = vi.fn()
const addPageMock = vi.fn()
const saveMock = vi.fn()
function jsPDFImpl(this: any) {
  this.internal = { pageSize: { getWidth: () => 210, getHeight: () => 297 } }
  this.addImage = addImageMock
  this.addPage = addPageMock
  this.save = saveMock
}
const jsPDFMock = vi.fn(jsPDFImpl)
vi.mock('jspdf', () => ({ jsPDF: jsPDFMock }))

import { useBriefingPdf, paginate } from '~/composables/useBriefingPdf'

describe('useBriefingPdf', () => {
  beforeEach(() => {
    html2canvasMock.mockReset()
    addImageMock.mockClear()
    addPageMock.mockClear()
    saveMock.mockClear()
    jsPDFMock.mockClear()
  })

  describe('slug', () => {
    it('lowercases, strips punctuation, and hyphenates spaces', () => {
      const { slug } = useBriefingPdf()
      expect(slug('Revenue held flat!')).toBe('revenue-held-flat')
    })

    it('collapses repeated separators and trims edges', () => {
      const { slug } = useBriefingPdf()
      expect(slug('  Q3 — Big   Win  ')).toBe('q3-big-win')
    })

    it('falls back to "briefing" for empty/symbol-only input', () => {
      const { slug } = useBriefingPdf()
      expect(slug('!!!')).toBe('briefing')
      expect(slug('')).toBe('briefing')
    })
  })

  describe('waitForWidgets', () => {
    it('resolves immediately when expected is 0', async () => {
      const { waitForWidgets } = useBriefingPdf()
      await expect(waitForWidgets(0)).resolves.toBeUndefined()
    })

    it('resolves once markWidgetLoaded reaches the expected count', async () => {
      const { waitForWidgets, markWidgetLoaded } = useBriefingPdf()
      let resolved = false
      const p = waitForWidgets(2).then(() => { resolved = true })
      expect(resolved).toBe(false)
      markWidgetLoaded()
      await Promise.resolve()
      expect(resolved).toBe(false)
      markWidgetLoaded()
      await p
      expect(resolved).toBe(true)
    })

    it('resolves on timeout even if widgets never load', async () => {
      vi.useFakeTimers()
      const { waitForWidgets } = useBriefingPdf()
      let resolved = false
      const p = waitForWidgets(3, 8000).then(() => { resolved = true })
      await vi.advanceTimersByTimeAsync(8000)
      await p
      expect(resolved).toBe(true)
      vi.useRealTimers()
    })

    it('resetWidgets zeroes the counter so a later wait blocks again', async () => {
      const { waitForWidgets, markWidgetLoaded, resetWidgets } = useBriefingPdf()
      markWidgetLoaded()
      markWidgetLoaded()
      await waitForWidgets(2) // resolves: count already 2
      resetWidgets()
      let resolved = false
      const p = waitForWidgets(1).then(() => { resolved = true })
      await Promise.resolve()
      expect(resolved).toBe(false) // count back to 0, must wait
      markWidgetLoaded()
      await p
      expect(resolved).toBe(true)
    })
  })

  describe('exportPdf', () => {
    afterEach(() => vi.restoreAllMocks())

    function makeEl(blockMms: number[]): HTMLElement {
      const blocks = blockMms.map((mm) => ({}) as Element)
      // html2canvas returns, per block in order, a canvas sized so contentW(186)→mm.
      blockMms.forEach((mm) =>
        html2canvasMock.mockResolvedValueOnce({ width: 186, height: mm } as HTMLCanvasElement),
      )
      return { querySelectorAll: () => blocks } as unknown as HTMLElement
    }

    it('is a no-op when el is null', async () => {
      const { exportPdf } = useBriefingPdf()
      await exportPdf(null, 'x', 0)
      expect(saveMock).not.toHaveBeenCalled()
    })

    it('is a no-op when the element has no [data-pdf-block] children', async () => {
      const { exportPdf } = useBriefingPdf()
      const el = { querySelectorAll: () => [] } as unknown as HTMLElement
      await exportPdf(el, 'x', 0)
      expect(saveMock).not.toHaveBeenCalled()
    })

    it('is a no-op when already exporting', async () => {
      const { exportPdf, exporting } = useBriefingPdf()
      exporting.value = true
      await exportPdf(makeEl([50]), 'x', 0)
      expect(saveMock).not.toHaveBeenCalled()
    })

    it('places two fitting blocks on one page and saves with a slugged filename', async () => {
      const { exportPdf } = useBriefingPdf()
      await exportPdf(makeEl([100, 100]), 'Revenue held flat!', 0)
      expect(addImageMock).toHaveBeenCalledTimes(2)
      expect(addPageMock).not.toHaveBeenCalled()
      expect(saveMock).toHaveBeenCalledWith('briefing-revenue-held-flat.pdf')
    })

    it('adds a page when a block overflows the current page', async () => {
      const { exportPdf } = useBriefingPdf()
      await exportPdf(makeEl([200, 100]), 'x', 0) // 200+gap+100 > 273
      expect(addPageMock).toHaveBeenCalledTimes(1)
      expect(addImageMock).toHaveBeenCalledTimes(2)
    })

    it('splits an oversized block into bands, one addPage per extra band', async () => {
      // happy-dom's canvas getContext('2d') returns null; stub createElement('canvas')
      // so cropCanvas gets a working stub context.
      const origCreateElement = document.createElement.bind(document)
      vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
        if (tag === 'canvas') {
          return { width: 0, height: 0, getContext: () => ({ drawImage: vi.fn() }) } as unknown as HTMLCanvasElement
        }
        return origCreateElement(tag)
      })
      const { exportPdf } = useBriefingPdf()
      await exportPdf(makeEl([600]), 'x', 0) // 600 / 273 → 3 bands
      expect(addImageMock).toHaveBeenCalledTimes(3)
      expect(addPageMock).toHaveBeenCalledTimes(2)
    })

    it('resets exporting to false even if capture throws', async () => {
      html2canvasMock.mockReset()
      html2canvasMock.mockRejectedValueOnce(new Error('boom'))
      const { exportPdf, exporting } = useBriefingPdf()
      const el = { querySelectorAll: () => [{}] } as unknown as HTMLElement
      await exportPdf(el, 'x', 0)
      expect(exporting.value).toBe(false)
    })
  })

  describe('paginate', () => {
    const C = 250 // content height mm
    it('keeps two small blocks that fit on one page', () => {
      const ops = paginate([100, 100], C, 4)
      expect(ops).toEqual([
        { block: 0, page: 0, y: 0, h: 100, srcTop: 0, srcBot: 100 },
        { block: 1, page: 0, y: 104, h: 100, srcTop: 0, srcBot: 100 },
      ])
    })

    it('pushes a block that overflows the current page to the next page', () => {
      const ops = paginate([200, 100], C, 4)
      expect(ops[0]).toEqual({ block: 0, page: 0, y: 0, h: 200, srcTop: 0, srcBot: 200 })
      // 200 + 4 + 100 = 304 > 250 → block 1 starts fresh page at y 0
      expect(ops[1]).toEqual({ block: 1, page: 1, y: 0, h: 100, srcTop: 0, srcBot: 100 })
    })

    it('never adds a page for a block already at the top of an empty page', () => {
      // single block exactly equal to content height: one op, page 0, no overflow page
      const ops = paginate([250], C, 4)
      expect(ops).toEqual([{ block: 0, page: 0, y: 0, h: 250, srcTop: 0, srcBot: 250 }])
    })

    it('splits an oversized block into page-height bands across consecutive pages', () => {
      // 600mm block, content 250 → bands 250,250,100 on pages 0,1,2
      const ops = paginate([600], C, 4)
      expect(ops).toEqual([
        { block: 0, page: 0, y: 0, h: 250, srcTop: 0, srcBot: 250 },
        { block: 0, page: 1, y: 0, h: 250, srcTop: 250, srcBot: 500 },
        { block: 0, page: 2, y: 0, h: 100, srcTop: 500, srcBot: 600 },
      ])
    })

    it('starts an oversized block on a fresh page and resumes after its last band', () => {
      // small block fills part of page 0, then a 300mm oversized block
      const ops = paginate([50, 300, 40], C, 4)
      expect(ops[0]).toEqual({ block: 0, page: 0, y: 0, h: 50, srcTop: 0, srcBot: 50 })
      // oversized block 1 cannot share page 0 (cursor > 0) → fresh page 1
      expect(ops[1]).toEqual({ block: 1, page: 1, y: 0, h: 250, srcTop: 0, srcBot: 250 })
      expect(ops[2]).toEqual({ block: 1, page: 2, y: 0, h: 50, srcTop: 250, srcBot: 300 })
      // block 2 resumes on page 2 after the last band (50) + gap (4)
      expect(ops[3]).toEqual({ block: 2, page: 2, y: 54, h: 40, srcTop: 0, srcBot: 40 })
    })

    it('returns empty for no blocks', () => {
      expect(paginate([], C, 4)).toEqual([])
    })
  })
})
