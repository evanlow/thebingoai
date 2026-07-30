// Raw file-type SVG markup for attachment chips — pair with a sized wrapper
// (e.g. <div class="h-5 w-5" v-html="...">). Same shape as useConnectorIcons.
// Only CSV/Excel have brand marks; everything else falls back to a lucide glyph
// at the call site.
// ponytail: no Tailwind classes here on purpose — tailwind.config.ts `content`
// doesn't glob ./composables, so any class string in this file would be purged.
import csvIcon from '~/assets/icons/file/csv.svg?raw'
import excelIcon from '~/assets/icons/file/excel.svg?raw'

const MIME_TO_ICON: Record<string, string> = {
  'text/csv': csvIcon,
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': excelIcon,
  'application/vnd.ms-excel': excelIcon,
}

const EXTENSION_TO_ICON: Record<string, string> = {
  csv: csvIcon,
  xlsx: excelIcon,
  xls: excelIcon,
}

// MIME first, extension as fallback — drag-and-drop reports '' or text/plain.
export function fileIconHtml(type?: string | null, name?: string | null): string | null {
  if (type && type in MIME_TO_ICON) return MIME_TO_ICON[type]
  const ext = name?.split('.').pop()?.toLowerCase()
  if (ext && ext in EXTENSION_TO_ICON) return EXTENSION_TO_ICON[ext]
  return null
}
