// Text size switcher (sm / md / lg) for the Settings surface.
// Mirrors useAppTheme: persisted in localStorage, applied as `font-{size}` class
// on <html> (md = no class → :root default scale). Drives the --fs-* vars that
// Tailwind's text-* tokens read, so text scales while spacing stays fixed.

export type FontSize = 'sm' | 'md' | 'lg'

const SIZES: FontSize[] = ['sm', 'md', 'lg']
const STORAGE_KEY = 'bingo-font-size'

const isFontSize = (v: unknown): v is FontSize =>
  typeof v === 'string' && (SIZES as string[]).includes(v)

export const useAppFontSize = () => {
  const preference = useState<FontSize>('app-font-size', () => {
    if (import.meta.client) {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (isFontSize(stored)) return stored
    }
    return 'md'
  })

  const apply = (size: FontSize) => {
    if (!import.meta.client) return
    const cl = document.documentElement.classList
    cl.remove('font-sm', 'font-lg')
    if (size !== 'md') cl.add(`font-${size}`)
  }

  if (import.meta.client) {
    apply(preference.value)
    watch(preference, val => {
      localStorage.setItem(STORAGE_KEY, val)
      apply(val)
    })
  }

  return { preference, sizes: SIZES }
}
