<template>
  <div ref="rootEl" class="prose-chat" v-html="renderedMarkdown" />
</template>

<script setup lang="ts">
import MarkdownIt from 'markdown-it'
// @ts-expect-error — markdown-it-mark ships no bundled types
import markdownItMark from 'markdown-it-mark'
import { useShikiHighlighter } from '~/composables/useShikiHighlighter'

interface Props {
  content: string
}

const props = defineProps<Props>()

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true
})

md.use(markdownItMark)

const highlighter = ref<any>(null)

onMounted(async () => {
  try {
    highlighter.value = await useShikiHighlighter()

    // Override code block rendering with syntax highlighting
    const defaultRender = md.renderer.rules.fence || ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options))

    md.renderer.rules.fence = (tokens, idx, options, env, self) => {
      const token = tokens[idx]
      const code = token.content
      const lang = token.info || 'text'

      if (highlighter.value && lang) {
        try {
          const colorMode = useColorMode()
          const theme = colorMode.value === 'dark' ? 'github-dark' : 'github-light'
          const html = highlighter.value.codeToHtml(code, { lang, theme })
          return `<div class="shiki-wrapper">${html}</div>`
        } catch (e) {
          // Fallback to default rendering if highlighting fails
        }
      }

      return defaultRender(tokens, idx, options, env, self)
    }
  } catch (error) {
    console.warn('Failed to load syntax highlighter:', error)
  }
})

const renderedMarkdown = computed(() => {
  try {
    // Wrap tables so wide previews can scroll horizontally (see tagWideTables).
    return md.render(props.content)
      .replace(/<table>/g, '<div class="table-scroll"><table>')
      .replace(/<\/table>/g, '</table></div>')
  } catch (error) {
    console.error('Failed to render markdown:', error)
    return `<p class="text-error-600">Failed to render markdown</p>`
  }
})

// Tag tables that overflow their column with --wide so CSS can break them out
// leftward into the empty margin. v-html elements can't take Vue class bindings,
// so measure + toggle after each render and on resize.
const rootEl = ref<HTMLElement | null>(null)

const TABLE_GUTTER_LEFT = 48
const TABLE_GUTTER_RIGHT = 32

// Nearest scrollable ancestor = the main content pane (right of the sidebar); its
// bounds are the breakout limits so the table never slides under the sidebar.
const scrollBounds = (el: HTMLElement): DOMRect => {
  let node: HTMLElement | null = el.parentElement
  while (node && node !== document.body) {
    const oy = getComputedStyle(node).overflowY
    if (oy === 'auto' || oy === 'scroll') return node.getBoundingClientRect()
    node = node.parentElement
  }
  return document.documentElement.getBoundingClientRect()
}

const tagWideTables = () => {
  const root = rootEl.value
  if (!root) return
  root.querySelectorAll<HTMLElement>('.table-scroll').forEach((wrap) => {
    const table = wrap.querySelector('table')
    if (!table) return
    // Reset to natural column width before measuring.
    wrap.style.width = ''
    wrap.style.marginLeft = ''
    if (table.scrollWidth <= wrap.clientWidth + 1) {
      wrap.classList.remove('table-scroll--wide')
      return
    }
    // Wide: span the main pane with a gutter each side (left gap, extend right).
    const pane = scrollBounds(wrap)
    const left = wrap.getBoundingClientRect().left
    wrap.classList.add('table-scroll--wide')
    wrap.style.width = `${pane.width - TABLE_GUTTER_LEFT - TABLE_GUTTER_RIGHT}px`
    wrap.style.marginLeft = `${pane.left + TABLE_GUTTER_LEFT - left}px`
  })
}

watch(renderedMarkdown, () => nextTick(tagWideTables))
onMounted(() => {
  nextTick(tagWideTables)
  window.addEventListener('resize', tagWideTables)
})
onBeforeUnmount(() => window.removeEventListener('resize', tagWideTables))
</script>

<style>
.shiki-wrapper {
  @apply my-3 overflow-x-auto rounded-lg;
}

.shiki-wrapper pre {
  @apply m-0 p-4;
}
</style>
