import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, computed, watch } from 'vue'

// ── Stub Nuxt auto-imports ───────────────────────────────────────────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', watch)

// ── Stub useApi ──────────────────────────────────────────────────────
const testUnsaved = vi.fn()
const create = vi.fn()
const uploadDataset = vi.fn()
const uploadSqlite = vi.fn()
vi.stubGlobal('useApi', () => ({
  connections: { testUnsaved, create, uploadDataset, uploadSqlite },
}))

// ── Child component stubs ────────────────────────────────────────────
const stubs = {
  UiDialog: {
    name: 'UiDialog',
    props: ['open', 'size', 'closable', 'title'],
    emits: ['update:open'],
    template: '<div v-if="open" class="ui-dialog"><slot /><slot name="footer" /></div>',
  },
  UiInput: {
    name: 'UiInput',
    props: ['modelValue', 'label', 'required', 'placeholder', 'error', 'type'],
    emits: ['update:modelValue'],
    template:
      '<div><input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" /><span class="err">{{ error }}</span></div>',
  },
  UiButton: {
    name: 'UiButton',
    props: ['variant', 'loading', 'disabled'],
    emits: ['click'],
    template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
}

import OnboardingConnectionDialog from '~/components/onboarding/OnboardingConnectionDialog.vue'

const POSTGRES = { id: 'postgres', display_name: 'PostgreSQL', default_port: 5432 }
const DATASET = { id: 'dataset', display_name: 'CSV / Excel', default_port: 0 }
const SQLITE = { id: 'sqlite', display_name: 'SQLite', default_port: 0 }

function mountDialog(connectorType: any = POSTGRES) {
  return mount(OnboardingConnectionDialog, {
    props: { open: true, connectorType },
    global: { stubs },
  })
}

const buttonByText = (wrapper: any, text: string) =>
  wrapper.findAll('button').find((b: any) => b.text().trim() === text)

// Fill the 6 sql inputs by index: name, host, port, database, username, password.
async function fillSql(wrapper: any, over: Partial<Record<string, string>> = {}) {
  const v = {
    name: 'My DB', host: 'db.example.com', port: '5432',
    database: 'app', username: 'admin', password: 'secret', ...over,
  }
  const inputs = wrapper.findAll('input')
  await inputs[0].setValue(v.name)
  await inputs[1].setValue(v.host)
  await inputs[2].setValue(v.port)
  await inputs[3].setValue(v.database)
  await inputs[4].setValue(v.username)
  await inputs[5].setValue(v.password)
}

async function setFile(wrapper: any, file: File) {
  const fileInput = wrapper.find('input[type="file"]')
  Object.defineProperty(fileInput.element, 'files', { value: [file], configurable: true })
  await fileInput.trigger('change')
}

describe('OnboardingConnectionDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders sql mode controls for a database connector', () => {
    const wrapper = mountDialog(POSTGRES)
    expect(buttonByText(wrapper, 'Test connection')).toBeTruthy()
    expect(buttonByText(wrapper, 'Save connection')).toBeTruthy()
  })

  it('renders file mode controls for a dataset connector', () => {
    const wrapper = mountDialog(DATASET)
    expect(buttonByText(wrapper, 'Upload')).toBeTruthy()
    expect(buttonByText(wrapper, 'Test connection')).toBeFalsy()
    expect(wrapper.find('input[type="file"]').exists()).toBe(true)
  })

  it('blocks save and shows errors when sql fields are empty', async () => {
    const wrapper = mountDialog(POSTGRES)
    await buttonByText(wrapper, 'Save connection')!.trigger('click')

    expect(wrapper.text()).toContain('Connection name is required')
    expect(create).not.toHaveBeenCalled()
  })

  it('rejects an out-of-range port', async () => {
    const wrapper = mountDialog(POSTGRES)
    await fillSql(wrapper, { port: '70000' })
    await buttonByText(wrapper, 'Save connection')!.trigger('click')

    expect(wrapper.text()).toContain('Port must be 1–65535')
    expect(create).not.toHaveBeenCalled()
  })

  it('creates the connection and emits created on a valid save', async () => {
    create.mockResolvedValue({ id: 7, name: 'My DB' })
    const wrapper = mountDialog(POSTGRES)
    await fillSql(wrapper)
    await buttonByText(wrapper, 'Save connection')!.trigger('click')
    await flushPromises()

    expect(create).toHaveBeenCalledWith(
      expect.objectContaining({ db_type: 'postgres', port: 5432, host: 'db.example.com', name: 'My DB' }),
    )
    expect(wrapper.emitted('created')).toEqual([[{ id: 7, name: 'My DB' }]])
  })

  it('shows a success message after a passing test', async () => {
    testUnsaved.mockResolvedValue({ success: true, message: 'Connection successful' })
    const wrapper = mountDialog(POSTGRES)
    await fillSql(wrapper)
    await buttonByText(wrapper, 'Test connection')!.trigger('click')
    await flushPromises()

    expect(testUnsaved).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('Connection successful')
  })

  it('surfaces the API detail message when a test fails', async () => {
    testUnsaved.mockRejectedValue({ data: { detail: 'boom' } })
    const wrapper = mountDialog(POSTGRES)
    await fillSql(wrapper)
    await buttonByText(wrapper, 'Test connection')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('boom')
  })

  it('surfaces the API detail message when a save fails', async () => {
    create.mockRejectedValue({ data: { detail: 'dup' } })
    const wrapper = mountDialog(POSTGRES)
    await fillSql(wrapper)
    await buttonByText(wrapper, 'Save connection')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('dup')
    expect(wrapper.emitted('created')).toBeUndefined()
  })

  it('requires a file before uploading', async () => {
    const wrapper = mountDialog(DATASET)
    await buttonByText(wrapper, 'Upload')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Please choose a file')
    expect(uploadDataset).not.toHaveBeenCalled()
  })

  it('uploads a dataset file and emits created', async () => {
    uploadDataset.mockResolvedValue({ id: 12, name: 'sales.csv' })
    const wrapper = mountDialog(DATASET)
    const file = new File(['a,b\n1,2'], 'sales.csv', { type: 'text/csv' })
    await setFile(wrapper, file)
    await buttonByText(wrapper, 'Upload')!.trigger('click')
    await flushPromises()

    expect(uploadDataset).toHaveBeenCalledWith(file, undefined, expect.any(Function))
    expect(uploadSqlite).not.toHaveBeenCalled()
    expect(wrapper.emitted('created')).toEqual([[{ id: 12, name: 'sales.csv' }]])
  })

  it('routes sqlite files through uploadSqlite', async () => {
    uploadSqlite.mockResolvedValue({ id: 13, name: 'db.sqlite' })
    const wrapper = mountDialog(SQLITE)
    const file = new File(['x'], 'db.sqlite')
    await setFile(wrapper, file)
    await buttonByText(wrapper, 'Upload')!.trigger('click')
    await flushPromises()

    expect(uploadSqlite).toHaveBeenCalledWith(file, undefined)
    expect(uploadDataset).not.toHaveBeenCalled()
  })

  it('emits update:open=false on cancel', async () => {
    const wrapper = mountDialog(POSTGRES)
    await buttonByText(wrapper, 'Cancel')!.trigger('click')

    expect(wrapper.emitted('update:open')).toEqual([[false]])
  })

  it('resets the form to the connector default port when reopened', async () => {
    const wrapper = mount(OnboardingConnectionDialog, {
      props: { open: false, connectorType: POSTGRES },
      global: { stubs },
    })
    await wrapper.setProps({ open: true })

    const portInput = wrapper.findAll('input')[2]
    expect((portInput.element as HTMLInputElement).value).toBe('5432')
  })
})
