import type { Config } from 'tailwindcss'

export default {
  darkMode: 'class',
  content: [
    './components/**/*.{js,vue,ts}',
    './layouts/**/*.vue',
    './pages/**/*.vue',
    './plugins/**/*.{js,ts}',
    './app.vue',
    './error.vue'
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#6E489D',
          soft: '#DAC7E1',
        },
      },
      fontFamily: {
        sans: ['DM Sans', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        display: ['Instrument Serif', 'serif']
      },
      // Font-size tokens reference --fs-* vars so the Text size preference
      // (font-sm/font-lg classes on <html>, see assets/css/main.css) can swap
      // whole-px scales at runtime. Line-heights kept at Tailwind defaults so
      // the Medium/default size renders identically to before.
      fontSize: {
        xs:    ['var(--fs-xs)',   { lineHeight: '1rem'    }],
        sm:    ['var(--fs-sm)',   { lineHeight: '1.25rem' }],
        base:  ['var(--fs-base)', { lineHeight: '1.5rem'  }],
        lg:    ['var(--fs-lg)',   { lineHeight: '1.75rem' }],
        xl:    ['var(--fs-xl)',   { lineHeight: '1.75rem' }],
        '2xl': ['var(--fs-2xl)',  { lineHeight: '2rem'    }],
        '3xl': ['var(--fs-3xl)',  { lineHeight: '2.25rem' }],
        '4xl': ['var(--fs-4xl)',  { lineHeight: '2.5rem'  }],
        '5xl': ['var(--fs-5xl)',  { lineHeight: '1'       }],
        '6xl': ['var(--fs-6xl)',  { lineHeight: '1'       }],
      },
      spacing: {
        'sidebar': '220px',
        'upload-panel': '300px'
      },
      borderRadius: {
        'xl': '0.75rem',
        '2xl': '1rem'
      },
      boxShadow: {
        'sm': '0 1px 2px 0 rgb(0 0 0 / 0.05)',
        'md': '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
        'lg': '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
        'xl': '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)'
      }
    }
  },
  plugins: []
} satisfies Config
