import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, watch, nextTick } from 'vue'

// ── Stub Nuxt auto-imports ───────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('watch', watch) // composable calls watch(preference, ...) — pass the real one through

const stateStore = new Map<string, any>()
vi.stubGlobal('useState', (key: string, init: () => any) => {
  if (!stateStore.has(key)) stateStore.set(key, ref(init()))
  return stateStore.get(key)
})

import { useAppTheme } from '~/composables/useAppTheme'

const STORAGE_KEY = 'bingo-app-theme'
const html = () => document.documentElement

describe('useAppTheme', () => {
  beforeEach(() => {
    stateStore.clear()
    localStorage.clear()
    html().className = ''
  })

  it('defaults to kraft and applies theme-kraft on init', () => {
    const { preference } = useAppTheme()
    expect(preference.value).toBe('kraft')
    expect(html().classList.contains('theme-kraft')).toBe(true)
  })

  it('exposes the theme options', () => {
    const { themes } = useAppTheme()
    expect(themes).toEqual(['kraft', 'cool', 'ink'])
  })

  it('reads a valid stored value and applies its class on init', () => {
    localStorage.setItem(STORAGE_KEY, 'ink')
    const { preference } = useAppTheme()
    expect(preference.value).toBe('ink')
    expect(html().classList.contains('theme-ink')).toBe(true)
  })

  it('ignores an invalid stored value and falls back to kraft', () => {
    localStorage.setItem(STORAGE_KEY, 'neon')
    const { preference } = useAppTheme()
    expect(preference.value).toBe('kraft')
    expect(html().classList.contains('theme-kraft')).toBe(true)
  })

  it('persists and swaps the class when preference changes', async () => {
    const { preference } = useAppTheme()
    preference.value = 'cool'
    await nextTick()
    expect(localStorage.getItem(STORAGE_KEY)).toBe('cool')
    expect(html().classList.contains('theme-cool')).toBe(true)
    expect(html().classList.contains('theme-kraft')).toBe(false)
  })

  it('shares preference state across invocations', () => {
    const a = useAppTheme()
    const b = useAppTheme()
    a.preference.value = 'ink'
    expect(b.preference.value).toBe('ink')
  })
})
