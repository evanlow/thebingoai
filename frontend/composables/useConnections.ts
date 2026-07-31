// Module-level reactive cache shared across all component instances
const cache = ref<
  Record<number, { name: string; dbType: string; sourceFilename: string | null }> | null
>(null)
let fetchPromise: Promise<void> | null = null

// Dynamic type labels populated from /api/connections/types
const typeLabels = ref<Record<string, string>>({})
let typesFetched = false

// Non-upload connectors reuse `source_filename` for internal metadata (a JSON
// blob on Facebook Ads, a seed marker on the sample DB), so only accept a value
// that actually looks like a filename — anything else is never shown.
const FILENAME_RE = /^[^{}\n]+\.[A-Za-z0-9]{1,8}$/

export const useConnections = () => {
  const api = useApi()

  const ensureLoaded = async () => {
    if (cache.value !== null) return
    if (fetchPromise) return fetchPromise

    fetchPromise = Promise.all([
      api.connections.list(),
      !typesFetched ? api.connections.getTypes().catch(() => []) : Promise.resolve(null),
    ]).then(([data, types]: [any, any]) => {
      const connections = Array.isArray(data) ? data : (data?.connections ?? [])
      cache.value = Object.fromEntries(
        connections.map((c: any) => [
          c.id,
          {
            name: c.name,
            dbType: c.db_type ?? '',
            sourceFilename: FILENAME_RE.test(c.source_filename ?? '')
              ? c.source_filename
              : null,
          },
        ])
      )
      if (types) {
        typesFetched = true
        for (const t of types) {
          typeLabels.value[t.id] = t.display_name
        }
      }
    }).catch(() => {
      cache.value = {}
    }).finally(() => {
      fetchPromise = null
    })

    return fetchPromise
  }

  const getConnectionLabel = (id: number): string => {
    const entry = cache.value?.[id]
    if (!entry) return `Connection #${id}`
    const label = typeLabels.value[entry.dbType] ?? entry.dbType
    return label ? `${label} : ${entry.name}` : entry.name
  }

  // The file the user uploaded. null when there is nothing readable to show
  // (SQL connections) — callers hide the label rather than fall back to the
  // internal storage table name.
  const getSourceLabel = (id: number): string | null =>
    cache.value?.[id]?.sourceFilename ?? null

  // Fold a just-created connection in. `ensureLoaded` returns early forever once
  // the cache is warm, so without this a dataset uploaded later in the session has
  // no entry and its dashboards silently lose their source label. Upsert rather
  // than invalidate: nulling the cache lets an in-flight fetch's `.then` write
  // pre-upload data back over it.
  const upsertConnection = (c: {
    id: number
    name: string
    db_type?: string
    source_filename?: string | null
  }) => {
    if (cache.value === null) return  // ensureLoaded will fetch it from the server
    cache.value = {
      ...cache.value,
      [c.id]: {
        name: c.name,
        dbType: c.db_type ?? '',
        sourceFilename: FILENAME_RE.test(c.source_filename ?? '')
          ? (c.source_filename as string)
          : null,
      },
    }
  }

  return { ensureLoaded, getConnectionLabel, getSourceLabel, upsertConnection }
}
