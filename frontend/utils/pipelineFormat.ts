// Pure presentation helpers for the Pipelines view, extracted from
// PipelinesView.vue so the source-avatar logic can be unit-tested directly
// (inline <script setup> functions are not reachable from a test without
// mounting).

export const AVATAR_COLORS = [
  'bg-indigo-500', 'bg-sky-500', 'bg-emerald-500', 'bg-amber-500', 'bg-rose-500', 'bg-violet-500',
]

export function avatarColor(id: number): string {
  return AVATAR_COLORS[id % AVATAR_COLORS.length]
}

// Derive a single-char avatar initial from a connection label like
// "Postgres : mydb" — drop the "type:" prefix, take the first alphanumeric
// char uppercased, fall back to "#".
export function initialFromLabel(label: string): string {
  const name = label.replace(/^[^:]+:\s*/, '')
  return (name.match(/[a-z0-9]/i)?.[0] ?? '#').toUpperCase()
}
