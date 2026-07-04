import { defineConfig } from 'vitest/config'
import { resolve } from 'path'
import vue from '@vitejs/plugin-vue'

// Nuxt replaces import.meta.client with true/false at build time; Vite's `define`
// refuses to touch import.meta, so vitest leaves it undefined and every composable's
// client-only branch (localStorage / <html> class / watch) is skipped. happy-dom
// gives us those browser APIs, so mirror Nuxt and hard-replace it to true in app code.
const clientTrue = {
  name: 'import-meta-client-true',
  transform(code: string, id: string) {
    if (id.includes('/node_modules/') || !code.includes('import.meta.client')) return null
    return code.replace(/import\.meta\.client/g, 'true')
  },
}

export default defineConfig({
  plugins: [vue(), clientTrue],
  test: {
    environment: 'happy-dom',
    include: ['__tests__/**/*.test.ts'],
  },
  resolve: {
    alias: {
      '~': resolve(__dirname, '.'),
      '@': resolve(__dirname, '.'),
      '#imports': resolve(__dirname, '.'),
      '#app': resolve(__dirname, '.'),
    },
  },
})
