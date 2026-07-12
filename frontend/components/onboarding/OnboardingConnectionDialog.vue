<template>
  <UiDialog
    :open="open"
    size="lg"
    :closable="!saving"
    :title="dialogTitle"
    @update:open="onClose"
  >
    <!-- SQL connectors: postgres / mysql -->
    <div v-if="mode === 'sql'" class="space-y-4">
      <UiInput
        v-model="form.name"
        label="Connection name"
        required
        placeholder="My database"
        :error="formErrors.name"
      />
      <div class="grid grid-cols-3 gap-3">
        <div class="col-span-2">
          <UiInput v-model="form.host" label="Host" required placeholder="db.example.com" :error="formErrors.host" />
        </div>
        <UiInput v-model="form.port" type="number" label="Port" required :error="formErrors.port" />
      </div>
      <UiInput v-model="form.database" label="Database" required placeholder="postgres" :error="formErrors.database" />
      <div class="grid grid-cols-2 gap-3">
        <UiInput v-model="form.username" label="Username" required :error="formErrors.username" />
        <UiInput v-model="form.password" type="password" label="Password" required :error="formErrors.password" />
      </div>
      <label class="flex items-center gap-2 text-sm text-gray-700 dark:text-neutral-300">
        <input v-model="form.ssl_enabled" type="checkbox" class="rounded border-gray-300 dark:border-neutral-600" />
        Use SSL
      </label>
      <p v-if="testMsg" :class="testOk ? 'text-sm text-green-600' : 'text-sm text-red-600'">{{ testMsg }}</p>
    </div>

    <!-- File connectors: dataset (CSV/Excel) / sqlite -->
    <div v-else-if="mode === 'file'" class="space-y-4">
      <UiInput
        v-model="form.name"
        :label="fileNameLabel"
        placeholder="Optional — defaults to the file name"
        :error="formErrors.name"
      />
      <div>
        <label class="mb-1.5 block text-sm font-light text-gray-700 dark:text-neutral-300">
          File <span class="text-red-600">*</span>
        </label>
        <input
          type="file"
          :accept="fileAccept"
          class="block w-full text-sm text-gray-600 dark:text-neutral-300 file:mr-3 file:rounded-lg file:border-0 file:bg-gray-100 dark:file:bg-neutral-700 file:px-4 file:py-2 file:text-sm file:font-medium"
          @change="onFileChange"
        />
        <p v-if="formErrors.file" class="mt-1.5 text-sm text-red-600">{{ formErrors.file }}</p>
        <p v-if="uploadingProgress > 0 && uploadingProgress < 100" class="mt-1.5 text-sm text-gray-500 dark:text-neutral-400">
          Uploading… {{ uploadingProgress }}%
        </p>
      </div>
    </div>

    <template #footer>
      <UiButton variant="outline" :disabled="saving" @click="onClose(false)">Cancel</UiButton>
      <UiButton v-if="mode === 'sql'" variant="secondary" :loading="testing" :disabled="saving" @click="onTest">
        Test connection
      </UiButton>
      <UiButton :loading="saving" :disabled="testing" @click="onSave">
        {{ mode === 'file' ? 'Upload' : 'Save connection' }}
      </UiButton>
    </template>
  </UiDialog>
</template>

<script setup lang="ts">
interface ConnectorType {
  id: string
  display_name: string
  default_port: number
}

const props = defineProps<{
  open: boolean
  connectorType: ConnectorType | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  created: [conn: { id: number; name?: string }]
}>()

const api = useApi() as any

const FILE_TYPES = new Set(['dataset', 'sqlite'])

const mode = computed<'sql' | 'file'>(() =>
  props.connectorType && FILE_TYPES.has(props.connectorType.id) ? 'file' : 'sql'
)

const dialogTitle = computed(() =>
  props.connectorType ? `Connect ${props.connectorType.display_name}` : 'Connect a source'
)
const fileNameLabel = computed(() =>
  props.connectorType?.id === 'sqlite' ? 'Connection name' : 'Dataset name'
)
const fileAccept = computed(() =>
  props.connectorType?.id === 'sqlite' ? '.sqlite,.db' : '.csv,.xlsx'
)

const form = ref({
  name: '',
  host: '',
  port: 0 as number | string,
  database: '',
  username: '',
  password: '',
  ssl_enabled: false,
})
const formErrors = ref<Record<string, string>>({})
const file = ref<File | null>(null)

const testing = ref(false)
const saving = ref(false)
const testOk = ref(false)
const testMsg = ref('')
const uploadingProgress = ref(0)

// Reset state each time the dialog opens for a (possibly new) connector type.
watch(() => props.open, (isOpen) => {
  if (!isOpen) return
  form.value = {
    name: '',
    host: '',
    port: props.connectorType?.default_port ?? 0,
    database: '',
    username: '',
    password: '',
    ssl_enabled: false,
  }
  formErrors.value = {}
  file.value = null
  testing.value = false
  saving.value = false
  testOk.value = false
  testMsg.value = ''
  uploadingProgress.value = 0
})

function onClose(value: boolean) {
  if (saving.value) return
  emit('update:open', value)
}

function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  file.value = target.files?.[0] ?? null
  formErrors.value.file = ''
}

function extractError(err: any, fallback: string): string {
  const detail = err?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && typeof detail.message === 'string') return detail.message
  if (typeof err?.message === 'string') return err.message
  return fallback
}

function validateSql(): boolean {
  const errs: Record<string, string> = {}
  if (!form.value.name.trim()) errs.name = 'Connection name is required'
  if (!form.value.host.trim()) errs.host = 'Host is required'
  const port = Number(form.value.port)
  if (!port || port < 1 || port > 65535) errs.port = 'Port must be 1–65535'
  if (!form.value.database.trim()) errs.database = 'Database is required'
  if (!form.value.username.trim()) errs.username = 'Username is required'
  if (!form.value.password) errs.password = 'Password is required'
  formErrors.value = errs
  return Object.keys(errs).length === 0
}

function sqlPayload() {
  return {
    name: form.value.name,
    db_type: props.connectorType!.id,
    host: form.value.host,
    port: Number(form.value.port),
    database: form.value.database,
    username: form.value.username,
    password: form.value.password,
    ssl_enabled: form.value.ssl_enabled,
  }
}

async function onTest() {
  if (!validateSql()) return
  testing.value = true
  testMsg.value = ''
  try {
    const res = await api.connections.testUnsaved(sqlPayload())
    testOk.value = !!res.success
    testMsg.value = res.message || (res.success ? 'Connection successful' : 'Connection failed')
  } catch (err: any) {
    testOk.value = false
    testMsg.value = extractError(err, 'Connection test failed')
  } finally {
    testing.value = false
  }
}

async function onSave() {
  if (mode.value === 'file') return onUpload()
  if (!validateSql()) return
  saving.value = true
  try {
    const conn = await api.connections.create(sqlPayload())
    emit('created', { id: conn.id, name: conn.name })
  } catch (err: any) {
    testOk.value = false
    testMsg.value = extractError(err, 'Failed to save connection')
  } finally {
    saving.value = false
  }
}

async function onUpload() {
  if (!file.value) {
    formErrors.value.file = 'Please choose a file'
    return
  }
  saving.value = true
  try {
    const name = form.value.name.trim() || undefined
    let res: any
    if (props.connectorType?.id === 'sqlite') {
      res = await api.connections.uploadSqlite(file.value, name)
    } else {
      res = await api.connections.uploadDataset(file.value, name, (p: number) => { uploadingProgress.value = p })
    }
    emit('created', { id: res.id, name: res.name })
  } catch (err: any) {
    formErrors.value.file = extractError(err, 'Upload failed')
  } finally {
    saving.value = false
    uploadingProgress.value = 0
  }
}
</script>
