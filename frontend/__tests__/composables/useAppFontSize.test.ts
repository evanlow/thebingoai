import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, watch, nextTick } from 'vue'

// ── Stub Nuxt auto-imports ───────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('watch', watch) // composable calls watch(preference, ...) — pass the real one through

// useState in Nuxt returns a shared, named ref. Route each key to its own
// shared ref so repeated invocations share state (like Nuxt's cache).
const stateStore = new Map<string, any>()
vi.stubGlobal('useState', (key: string, init: () => any) => {
  if (!stateStore.has(key)) stateStore.set(key, ref(init()))
  return stateStore.get(key)
})

import { useAppFontSize } from '~/composables/useAppFontSize'

const STORAGE_KEY = 'bingo-font-size'
const html = () => document.documentElement

describe('useAppFontSize', () => {
  beforeEach(() => {
    stateStore.clear()
    localStorage.clear()
    html().className = ''
  })

  it('defaults to md with no font-* class when nothing stored', () => {
    const { preference } = useAppFontSize()
    expect(preference.value).toBe('md')
    expect(html().classList.contains('font-sm')).toBe(false)
    expect(html().classList.contains('font-lg')).toBe(false)
  })

  it('exposes the size options', () => {
    const { sizes } = useAppFontSize()
    expect(sizes).toEqual(['sm', 'md', 'lg'])
  })

  it('reads a valid stored value and applies its class on init', () => {
    localStorage.setItem(STORAGE_KEY, 'lg')
    const { preference } = useAppFontSize()
    expect(preference.value).toBe('lg')
    expect(html().classList.contains('font-lg')).toBe(true)
  })

  it('ignores an invalid stored value and falls back to md', () => {
    localStorage.setItem(STORAGE_KEY, 'xl')
    const { preference } = useAppFontSize()
    expect(preference.value).toBe('md')
    expect(html().classList.contains('font-md')).toBe(false)
  })

  it('persists and applies the class when preference changes', async () => {
    const { preference } = useAppFontSize()
    preference.value = 'sm'
    await nextTick()
    expect(localStorage.getItem(STORAGE_KEY)).toBe('sm')
    expect(html().classList.contains('font-sm')).toBe(true)
    expect(html().classList.contains('font-lg')).toBe(false)
  })

  it('removes all font-* classes when switching back to md', async () => {
    localStorage.setItem(STORAGE_KEY, 'lg')
    const { preference } = useAppFontSize()
    expect(html().classList.contains('font-lg')).toBe(true)
    preference.value = 'md'
    await nextTick()
    expect(localStorage.getItem(STORAGE_KEY)).toBe('md')
    expect(html().classList.contains('font-sm')).toBe(false)
    expect(html().classList.contains('font-lg')).toBe(false)
  })

  it('shares preference state across invocations', () => {
    const a = useAppFontSize()
    const b = useAppFontSize()
    a.preference.value = 'lg'
    expect(b.preference.value).toBe('lg')
  })
})
