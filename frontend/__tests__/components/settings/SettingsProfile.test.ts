import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, computed, reactive } from 'vue'

// ── Nuxt auto-imports the SFC calls bare — expose as globals ──────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)

// Held across a mount so tests can assert the ref value after clicks.
let fontPref: ReturnType<typeof ref<'sm' | 'md' | 'lg'>>
let themePref: ReturnType<typeof ref<'kraft' | 'cool' | 'ink'>>

vi.stubGlobal('useAppFontSize', () => ({ preference: fontPref, sizes: ['sm', 'md', 'lg'] }))
vi.stubGlobal('useAppTheme', () => ({ preference: themePref, themes: ['kraft', 'cool', 'ink'] }))
vi.stubGlobal('useColorMode', () => reactive({ value: 'light', preference: 'light' }))
vi.stubGlobal('useAuthStore', () => ({
  user: { email: 'a@b.co', name: 'Ann', roles: ['admin'], created_at: '2026-01-01T00:00:00Z' },
  logout: vi.fn(),
}))
vi.stubGlobal('useRouter', () => ({ push: vi.fn() }))

import SettingsProfile from '~/components/settings/SettingsProfile.vue'

const globalStubs = {
  UiCard: { template: `<div><slot/></div>` },
  UiButton: { template: `<button><slot/></button>` },
}

function mountView() {
  return mount(SettingsProfile, { global: { stubs: globalStubs } })
}

const fontBtn = (w: any, label: string) =>
  w.findAll('button').find((b: any) => b.text() === label)

beforeEach(() => {
  fontPref = ref('md')
  themePref = ref('kraft')
  vi.clearAllMocks()
})

describe('SettingsProfile — text size control', () => {
  it('renders a Small / Medium / Large option', () => {
    const w = mountView()
    expect(fontBtn(w, 'Small')).toBeTruthy()
    expect(fontBtn(w, 'Medium')).toBeTruthy()
    expect(fontBtn(w, 'Large')).toBeTruthy()
  })

  it('marks the current size (md) as active', () => {
    const w = mountView()
    expect(fontBtn(w, 'Medium').classes()).toContain('bg-gray-900')
    expect(fontBtn(w, 'Small').classes()).not.toContain('bg-gray-900')
    expect(fontBtn(w, 'Large').classes()).not.toContain('bg-gray-900')
  })

  it('selecting Large sets the preference and moves the active class', async () => {
    const w = mountView()
    await fontBtn(w, 'Large').trigger('click')
    expect(fontPref.value).toBe('lg')
    expect(fontBtn(w, 'Large').classes()).toContain('bg-gray-900')
    expect(fontBtn(w, 'Medium').classes()).not.toContain('bg-gray-900')
  })

  it('selecting back to Medium round-trips the preference', async () => {
    const w = mountView()
    await fontBtn(w, 'Large').trigger('click')
    await fontBtn(w, 'Medium').trigger('click')
    expect(fontPref.value).toBe('md')
    expect(fontBtn(w, 'Medium').classes()).toContain('bg-gray-900')
    expect(fontBtn(w, 'Large').classes()).not.toContain('bg-gray-900')
  })
})

describe('SettingsProfile — theme switcher', () => {
  // Theme swatches carry no text; find them by their title attribute.
  const swatch = (w: any, theme: string) =>
    w.findAll('button').find((b: any) => b.attributes('title') === theme)

  it('renders a swatch per theme with the current one (kraft) active', () => {
    const w = mountView()
    expect(swatch(w, 'kraft').classes()).toContain('scale-110')
    expect(swatch(w, 'cool').classes()).not.toContain('scale-110')
    expect(swatch(w, 'ink').classes()).not.toContain('scale-110')
  })

  it('selecting a theme sets the preference and moves the active class', async () => {
    const w = mountView()
    await swatch(w, 'cool').trigger('click')
    expect(themePref.value).toBe('cool')
    expect(swatch(w, 'cool').classes()).toContain('scale-110')
    expect(swatch(w, 'kraft').classes()).not.toContain('scale-110')
  })
})
