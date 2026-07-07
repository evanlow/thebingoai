import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

// ── Mock the API composable + auth store (imported by the component) ──
const h = vi.hoisted(() => ({
  listForConnection: vi.fn(),
  run: vi.fn(),
  updateSchedule: vi.fn(),
  update: vi.fn(),
  redetectWatermark: vi.fn(),
  loadHistory: vi.fn(),
  del: vi.fn(),
}))
vi.mock('~/composables/useApi', () => ({
  useApi: () => ({
    pipelines: {
      listForConnection: h.listForConnection,
      run: h.run,
      updateSchedule: h.updateSchedule,
      update: h.update,
      redetectWatermark: h.redetectWatermark,
      loadHistory: h.loadHistory,
      delete: h.del,
    },
  }),
}))
vi.mock('~/stores/auth', () => ({ useAuthStore: () => ({ user: { id: 'u1' } }) }))

// ── Stub lucide icons ────────────────────────────────────────────────
vi.mock('lucide-vue-next', () => {
  const stub = { render: () => null }
  return {
    Check: stub, History: stub, Loader2: stub, Pencil: stub,
    Play: stub, Power: stub, Search: stub, Trash2: stub,
  }
})

import SettingsConnectionSync from '~/components/settings/SettingsConnectionSync.vue'

// UiButton stub: a real <button> that reflects :loading and forwards @click.
const UiButton = {
  props: ['loading', 'variant', 'size', 'disabled', 'type'],
  emits: ['click'],
  template: `<button :data-loading="loading ? '1' : '0'" @click="$emit('click')"><slot/></button>`,
}

const newModelPipeline = () => ({
  id: 'p1', name: 'pg sync', cron: null, timezone: 'UTC',
  last_run_at: null, last_run_status: null, next_run_at: null,
  enabled: true, extraction_config: {},
  schedules: [{
    id: 's1', cron: '0 2 * * *', timezone: 'UTC', enabled: true,
    tables: [{ source_table: 'orders' }, { source_table: 'customers' }],
  }],
})

const legacyPipeline = () => ({
  id: 'p2', name: 'pg sync', cron: '0 5 * * *', timezone: 'UTC',
  last_run_at: null, last_run_status: null, next_run_at: null,
  enabled: true, extraction_config: { tables: ['orders'] }, schedules: [],
})

function mountWith(pipeline: any) {
  h.listForConnection.mockResolvedValue([pipeline])
  return mount(SettingsConnectionSync, {
    props: { connection: { id: 1, name: 'pg' }, schema: null },
    global: { stubs: { UiButton } },
  })
}

async function flush() {
  await new Promise(r => setTimeout(r, 0))
  await new Promise(r => setTimeout(r, 0))
}

const btn = (w: any, label: string) =>
  w.findAll('button').find((b: any) => b.text().includes(label))

beforeEach(() => {
  vi.clearAllMocks()
  h.run.mockResolvedValue(undefined)
})

describe('SettingsConnectionSync — schedule expansion', () => {
  it('new-model pipeline reads cron + table count from the active schedule', async () => {
    const w = mountWith(newModelPipeline())
    await flush()
    const text = w.text()
    expect(text).toContain('2 tables')      // scheduleTableNames.length
    expect(text).toContain('0 2 * * *')      // activeSchedule.cron
  })

  it('legacy pipeline (no schedules) reads cron + tables from the Pipeline row', async () => {
    const w = mountWith(legacyPipeline())
    await flush()
    const text = w.text()
    expect(text).toContain('1 table')        // extraction_config.tables
    expect(text).toContain('0 5 * * *')      // pipeline.cron, not a schedule
  })
})

describe('SettingsConnectionSync — optimistic in-progress status', () => {
  it('"Sync now" shows loading immediately, before the run promise resolves', async () => {
    let resolveRun: () => void = () => {}
    h.run.mockReturnValue(new Promise<void>((r) => { resolveRun = r }))

    const w = mountWith(newModelPipeline())
    await flush()
    const sync = btn(w, 'Sync now')!

    await sync.trigger('click')
    expect(h.run).toHaveBeenCalledWith('p1')
    expect(sync.attributes('data-loading')).toBe('1')   // optimistic, pre-resolve

    resolveRun()
    await flush()
    expect(btn(w, 'Sync now')!.attributes('data-loading')).toBe('0')
  })

  it('toggleEnabled flips enabled via updateSchedule and reflects the result', async () => {
    const disabled = newModelPipeline()
    disabled.schedules[0].enabled = false
    h.updateSchedule.mockResolvedValue(disabled)

    const w = mountWith(newModelPipeline())
    await flush()
    expect(btn(w, 'Disable')).toBeTruthy()              // effectiveEnabled true → "Disable"

    await btn(w, 'Disable')!.trigger('click')
    expect(h.updateSchedule).toHaveBeenCalledWith('p1', 's1', { enabled: false })
    await flush()
    expect(btn(w, 'Enable')).toBeTruthy()               // now disabled → "Enable"
  })
})
