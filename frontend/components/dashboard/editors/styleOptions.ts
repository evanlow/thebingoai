// Shared option lists for the widget Style editors. KPI keeps a local
// font-size list (it also offers 'xl'); chart keeps a local border list
// (different option order).
export const FONT_SIZE_OPTIONS = [
  { value: 'xs' as const, label: 'XS' },
  { value: 'sm' as const, label: 'S' },
  { value: 'md' as const, label: 'M' },
  { value: 'lg' as const, label: 'L' },
]

export const BORDER_STYLE_OPTIONS = [
  { value: 'solid' as const, label: 'Solid' },
  { value: 'dashed' as const, label: 'Dashed' },
  { value: 'dotted' as const, label: 'Dotted' },
  { value: 'none' as const, label: 'None' },
]
