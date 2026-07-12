import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { h, computed, nextTick } from 'vue'

vi.stubGlobal('computed', computed)

import UiDropdown from '~/components/ui/UiDropdown.vue'

// Mount UiDropdown with a trigger button in the #trigger slot. headlessui's
// MenuItems only render once the menu is open, so tests open via the trigger.
function mountDropdown(props: Record<string, any>) {
  return mount(UiDropdown, {
    props,
    slots: { trigger: () => h('button', { class: 'trigger' }, 'Menu') },
  })
}

const triggerBtn = (w: any) => w.findAll('button').find((b: any) => b.text() === 'Menu')!
const itemByText = (w: any, text: string) =>
  w.findAll('button').find((b: any) => b.text() === text)

async function open(w: any) {
  await triggerBtn(w).trigger('click')
  await nextTick()
  await flushPromises()
}

describe('UiDropdown', () => {
  let onCsv: ReturnType<typeof vi.fn>
  let onExcel: ReturnType<typeof vi.fn>

  beforeEach(() => {
    onCsv = vi.fn()
    onExcel = vi.fn()
  })

  const items = () => [
    { label: 'CSV', onClick: onCsv },
    { label: 'Excel', onClick: onExcel },
  ]

  it('renders the trigger slot', () => {
    const w = mountDropdown({ items: items() })
    expect(triggerBtn(w)).toBeTruthy()
  })

  it('does not render items until opened', async () => {
    const w = mountDropdown({ items: items() })
    expect(itemByText(w, 'CSV')).toBeUndefined()
    await open(w)
    expect(itemByText(w, 'CSV')).toBeTruthy()
    expect(itemByText(w, 'Excel')).toBeTruthy()
  })

  it('invokes an item onClick when clicked', async () => {
    const w = mountDropdown({ items: items() })
    await open(w)
    await itemByText(w, 'Excel')!.trigger('click')
    expect(onExcel).toHaveBeenCalledTimes(1)
    expect(onCsv).not.toHaveBeenCalled()
  })

  it('applies danger styling to a danger item', async () => {
    const w = mountDropdown({ items: [{ label: 'Delete', onClick: vi.fn(), danger: true }] })
    await open(w)
    expect(itemByText(w, 'Delete')!.classes()).toContain('text-red-600')
  })

  it('aligns right by default and left when align="left"', async () => {
    const right = mountDropdown({ items: items() })
    await open(right)
    expect(right.find('.origin-top-right').exists()).toBe(true)

    const left = mountDropdown({ items: items(), align: 'left' })
    await open(left)
    expect(left.find('.origin-top-left').exists()).toBe(true)
  })
})
