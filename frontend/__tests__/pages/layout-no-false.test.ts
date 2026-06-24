import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync, existsSync } from 'fs'
import { resolve } from 'path'

// Regression guard for the onboarding→/chat "stacked pages" bug.
//
// `layout: false` pages bypass the <NuxtLayout> component path. Navigating from
// such a page into a layouted page (e.g. /chat, default layout) under
// `pageTransition: { mode: 'out-in' }` strands the leaving page's subtree in the
// DOM instead of unmounting it (Nuxt's false↔named-layout transition gap).
// Fix: full-bleed pages use the passthrough `layouts/blank.vue` instead of
// `layout: false`. This test fails if anyone reintroduces `layout: false`.

const pagesDir = resolve(__dirname, '../../pages')
const blankLayout = resolve(__dirname, '../../layouts/blank.vue')

function vueFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = resolve(dir, e.name)
    if (e.isDirectory()) return vueFiles(full)
    return e.name.endsWith('.vue') ? [full] : []
  })
}

describe('page layout meta', () => {
  it('no page uses `layout: false` (use the blank layout instead)', () => {
    const offenders = vueFiles(pagesDir).filter((f) =>
      /layout:\s*false/.test(readFileSync(f, 'utf8')),
    )
    expect(offenders).toEqual([])
  })

  it('the blank passthrough layout exists', () => {
    expect(existsSync(blankLayout)).toBe(true)
    expect(readFileSync(blankLayout, 'utf8')).toContain('<slot')
  })

  it('the reported onboarding pages use the blank layout', () => {
    for (const p of ['connect.vue', 'first-question.vue']) {
      expect(readFileSync(resolve(pagesDir, p), 'utf8')).toContain("layout: 'blank'")
    }
  })
})
