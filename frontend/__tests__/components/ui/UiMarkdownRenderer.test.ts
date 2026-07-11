import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

// Shiki is awaited in onMounted; stub it (and useColorMode, used only by the fence
// rule) so mounting doesn't pull the real highlighter.
vi.mock('~/composables/useShikiHighlighter', () => ({
  useShikiHighlighter: () => ({ codeToHtml: () => '' }),
}))

vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', watch)
vi.stubGlobal('onMounted', onMounted)
vi.stubGlobal('onBeforeUnmount', onBeforeUnmount)
vi.stubGlobal('nextTick', nextTick)
vi.stubGlobal('useColorMode', () => ({ value: 'light' }))

import UiMarkdownRenderer from '~/components/ui/UiMarkdownRenderer.vue'

const TABLE_MD = '| a | b |\n| - | - |\n| 1 | 2 |\n'

// happy-dom has no layout engine, so scrollWidth/clientWidth are 0. Force them to
// stage the wide/narrow decision, then re-run tagWideTables via a resize event.
function setGeometry(el: Element, prop: 'scrollWidth' | 'clientWidth', value: number) {
  Object.defineProperty(el, prop, { value, configurable: true })
}

async function mountTable() {
  const wrapper = mount(UiMarkdownRenderer, { props: { content: TABLE_MD }, attachTo: document.body })
  await nextTick()
  await nextTick()
  return wrapper
}

describe('UiMarkdownRenderer — wide-table breakout', () => {
  it('wraps every table in a .table-scroll container', async () => {
    const wrapper = await mountTable()
    const wrap = wrapper.find('.table-scroll')
    expect(wrap.exists()).toBe(true)
    expect(wrap.find('table').exists()).toBe(true)
  })

  it('leaves a table that fits its column unmarked (no --wide, no inline width)', async () => {
    const wrapper = await mountTable()
    const wrap = wrapper.find('.table-scroll').element as HTMLElement
    const table = wrap.querySelector('table')!
    setGeometry(table, 'scrollWidth', 100)
    setGeometry(wrap, 'clientWidth', 200)   // fits

    window.dispatchEvent(new Event('resize'))
    await nextTick()

    expect(wrap.classList.contains('table-scroll--wide')).toBe(false)
    expect(wrap.style.width).toBe('')
    expect(wrap.style.marginLeft).toBe('')
  })

  it('breaks out a table that overflows its column (--wide + inline width/marginLeft)', async () => {
    const wrapper = await mountTable()
    const wrap = wrapper.find('.table-scroll').element as HTMLElement
    const table = wrap.querySelector('table')!
    setGeometry(table, 'scrollWidth', 1000)
    setGeometry(wrap, 'clientWidth', 100)   // overflows

    window.dispatchEvent(new Event('resize'))
    await nextTick()

    expect(wrap.classList.contains('table-scroll--wide')).toBe(true)
    expect(wrap.style.width).not.toBe('')
    expect(wrap.style.marginLeft).not.toBe('')
  })
})
