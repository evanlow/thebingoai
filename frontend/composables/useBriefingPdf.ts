export interface PdfOp {
  block: number
  page: number
  y: number
  h: number
  srcTop: number
  srcBot: number
}

/**
 * Compute page placements for a stack of blocks. Blocks flow top-to-bottom; a
 * block that does not fit the remaining page moves whole to the next page. A
 * block taller than one content page is the only thing that splits: it starts
 * on a fresh page and is sliced into page-height bands.
 */
export function paginate(heights: number[], contentH: number, gap: number): PdfOp[] {
  const ops: PdfOp[] = []
  let page = 0
  let cursorY = 0
  for (let block = 0; block < heights.length; block++) {
    const h = heights[block]
    if (h <= contentH) {
      // Won't fit remaining space and we're not already at the top → new page.
      if (cursorY > 0 && cursorY + h > contentH) {
        page++
        cursorY = 0
      }
      ops.push({ block, page, y: cursorY, h, srcTop: 0, srcBot: h })
      cursorY += h + gap
    } else {
      // Oversized: start on a fresh page if the current one isn't empty.
      if (cursorY > 0) {
        page++
        cursorY = 0
      }
      let srcTop = 0
      let bandH = 0
      while (srcTop < h) {
        bandH = Math.min(contentH, h - srcTop)
        ops.push({ block, page, y: 0, h: bandH, srcTop, srcBot: srcTop + bandH })
        srcTop += bandH
        if (srcTop < h) page++
      }
      cursorY = bandH + gap
    }
  }
  return ops
}

/** Crop a vertical band [srcTopMm, srcBotMm) of `src` (whose full height is
 *  `fullMm`) into a new canvas, for oversized-block page splitting. */
function cropCanvas(
  src: HTMLCanvasElement,
  srcTopMm: number,
  srcBotMm: number,
  fullMm: number,
): HTMLCanvasElement {
  const y0 = Math.round((srcTopMm / fullMm) * src.height)
  const y1 = Math.round((srcBotMm / fullMm) * src.height)
  const out = document.createElement('canvas')
  out.width = src.width
  out.height = y1 - y0
  const ctx = out.getContext('2d')!
  ctx.drawImage(src, 0, y0, src.width, y1 - y0, 0, 0, src.width, y1 - y0)
  return out
}

/**
 * Briefing PDF export. Client-side only.
 *
 * Captures each [data-pdf-block] element with html2canvas, places them on a
 * jsPDF document using the paginate() helper, and triggers a download. Waits
 * for async-loaded section widgets (Chart.js canvases) before capturing, and
 * strips dark mode on the cloned document so the PDF is always light.
 */
export function useBriefingPdf() {
  const exporting = ref(false)
  const loadedCount = ref(0)

  /** Page wires this to BriefingWidgetEmbed's @loaded event. */
  function markWidgetLoaded() {
    loadedCount.value += 1
  }

  /** Page calls this when the briefing id changes (page is reused, not remounted). */
  function resetWidgets() {
    loadedCount.value = 0
  }

  /** Turn a headline into a filename-safe slug; fall back to "briefing". */
  function slug(text: string): string {
    const s = (text || '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
    return s || 'briefing'
  }

  /**
   * Resolve once `loadedCount` reaches `expected`, or after `timeoutMs`
   * (export anyway — a stuck widget must not block the download).
   */
  function waitForWidgets(expected: number, timeoutMs = 8000): Promise<void> {
    return new Promise((resolve) => {
      if (loadedCount.value >= expected) {
        resolve()
        return
      }
      const stop = watch(loadedCount, (v: number) => {
        if (v >= expected) {
          stop()
          clearTimeout(timer)
          resolve()
        }
      })
      const timer = setTimeout(() => {
        stop()
        resolve()
      }, timeoutMs)
    })
  }

  /** Wait two animation frames so Chart.js has painted its canvases. */
  function nextFrame(): Promise<void> {
    return new Promise((resolve) => requestAnimationFrame(() => resolve()))
  }

  /**
   * Generate and download the PDF.
   * @param el            the <article> element to capture
   * @param headline      briefing headline (used for the filename)
   * @param expectedWidgets number of sections with a widget_id
   */
  async function exportPdf(
    el: HTMLElement | null,
    headline: string,
    expectedWidgets: number,
  ): Promise<void> {
    if (exporting.value || !el) return
    exporting.value = true
    try {
      await waitForWidgets(expectedWidgets)
      await nextFrame()
      await nextFrame()

      const html2canvas = (await import('html2canvas')).default
      const { jsPDF } = await import('jspdf')

      const doc = new jsPDF({ unit: 'mm', format: 'a4', orientation: 'portrait' })
      const margin = 12
      const gap = 4
      const pageW = doc.internal.pageSize.getWidth()
      const pageH = doc.internal.pageSize.getHeight()
      const contentW = pageW - margin * 2
      const contentH = pageH - margin * 2

      const blocks = Array.from(el.querySelectorAll<HTMLElement>('[data-pdf-block]'))
      if (blocks.length === 0) return
      const canvases = await Promise.all(
        blocks.map((b) =>
          html2canvas(b, {
            scale: 2,
            backgroundColor: '#ffffff',
            useCORS: true,
            onclone: (doc2: Document) => {
              doc2.documentElement.classList.remove('dark', 'theme-kraft', 'theme-cool', 'theme-ink')
              // html2canvas can shave a few px off a block's bottom edge, clipping the
              // last text line (the block's trailing margin lives outside its box, so
              // text sits flush). Pad the box in the clone so the shave eats padding,
              // not words. Clone-only — the live page is untouched.
              const s = doc2.createElement('style')
              s.textContent = '[data-pdf-block]{padding-bottom:10px}'
              doc2.head.appendChild(s)
            },
          }),
        ),
      )

      // Each block's rendered height in mm, scaled to the content width.
      const heights = canvases.map((c) => (c.height * contentW) / c.width)
      const ops = paginate(heights, contentH, gap)

      const pageStarted = new Set<number>()
      for (const op of ops) {
        if (op.page > 0 && !pageStarted.has(op.page)) {
          doc.addPage()
          pageStarted.add(op.page)
        }
        const c = canvases[op.block]
        const img = op.srcTop === 0 && op.srcBot >= heights[op.block]
          ? c
          : cropCanvas(c, op.srcTop, op.srcBot, heights[op.block])
        doc.addImage(img, 'JPEG', margin, margin + op.y, contentW, op.h)
      }

      doc.save(`briefing-${slug(headline)}.pdf`)
    } catch (e) {
      console.error('Briefing PDF export failed', e)
    } finally {
      exporting.value = false
    }
  }

  return { exporting, markWidgetLoaded, resetWidgets, slug, waitForWidgets, exportPdf }
}
