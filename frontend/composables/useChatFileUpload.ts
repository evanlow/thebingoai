export interface UploadingFile {
  file: File
  file_id: string | null
  connection_id?: number | null  // for dataset files uploaded via connections API
  preview_url: string | null  // object URL for images
  resolved_type: string  // corrected MIME from resolveFileType — file.type lies on drag-drop
  // 'attached' is the resting state for datasets: picked in the composer but not
  // yet sent anywhere. Nothing is uploaded until the user presses Enter.
  status: 'attached' | 'uploading' | 'processing' | 'ready' | 'error'
  error?: string
  progress?: number  // 0-100, only meaningful when status === 'uploading'
  row_count?: number | null  // reported by the dataset upload response
  sent?: boolean  // true after first send — skip in subsequent message embeddings
  transferCompletedAt?: string  // ISO, stamped when progress hits 100
  processingStartedAt?: string  // ISO, stamped when the server takes over
}

interface FileRejection {
  name: string
  error: string
}

const MAX_FILE_COUNT = 5

const ACCEPTED_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
  'text/csv',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
])

const IMAGE_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
])

const DATASET_TYPES = new Set([
  'text/csv',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
])

// Extension-to-MIME fallback for drag-and-drop where browsers may report
// incorrect or empty MIME types (e.g. CSV as 'text/plain' or '').
const EXTENSION_TO_MIME: Record<string, string> = {
  csv: 'text/csv',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  pdf: 'application/pdf',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
  webp: 'image/webp',
}

function resolveFileType(file: File): string | null {
  if (ACCEPTED_TYPES.has(file.type)) return file.type
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (ext && ext in EXTENSION_TO_MIME) return EXTENSION_TO_MIME[ext]
  return null
}

// Module-level singleton state (shared across all callers)
// Exported so useDatasetStatus can read it reactively without a circular import.
export const attachedFiles = ref<UploadingFile[]>([])

/**
 * True once nothing is mid-transfer, i.e. pressing Enter now is safe. A dataset
 * sitting in 'attached' is the normal case — its upload is what Enter starts.
 */
const canSubmitFiles = computed<boolean>(() =>
  attachedFiles.value.every(f => f.status !== 'uploading')
)

/** Locate a file's current index — it can shift if another attachment is removed. */
function indexOfFile(file: File): number {
  return attachedFiles.value.findIndex(f => f.file === file)
}

function patchFile(fileIndex: number, patch: Partial<UploadingFile>) {
  const updated = [...attachedFiles.value]
  if (!updated[fileIndex]) return
  updated[fileIndex] = { ...updated[fileIndex], ...patch }
  attachedFiles.value = updated
}

function updateProgress(fileIndex: number, percent: number) {
  const existing = attachedFiles.value[fileIndex]
  if (existing?.status !== 'uploading') return
  patchFile(fileIndex, {
    progress: percent,
    ...(percent >= 100 && !existing.transferCompletedAt
      ? { transferCompletedAt: new Date().toISOString() }
      : {}),
  })
}

function markReady(fileIndex: number, extra: Partial<UploadingFile>) {
  patchFile(fileIndex, { ...extra, status: 'ready' })
}

function markError(fileIndex: number, error: string) {
  patchFile(fileIndex, { status: 'error', error })
}

function markProcessing(fileIndex: number, extra: Partial<UploadingFile>) {
  patchFile(fileIndex, {
    ...extra,
    status: 'processing',
    processingStartedAt: new Date().toISOString(),
  })
}

export const useChatFileUpload = () => {
  const api = useApi()
  const chatStore = useChatStore()
  const config = useRuntimeConfig()
  const { upsertConnection } = useConnections()

  /**
   * True when every attached file has finished everything the send is waiting on:
   * transfer, server-side profiling and — for datasets — documentation. Drives the
   * composer's "reading your data" lock, not the send button.
   */
  const allFilesReady = computed<boolean>(() => {
    if (attachedFiles.value.length === 0) return false
    return attachedFiles.value.every(f => {
      if (f.status === 'error') return true   // terminal, just unsuccessfully
      if (f.status !== 'ready') return false  // attached / uploading / processing
      if (!DATASET_TYPES.has(f.resolved_type)) return true
      return f.connection_id == null ||
        !chatStore.docsPendingConnections.includes(f.connection_id)
    })
  })

  /** Ensure a conversation exists for file uploads, creating one if needed. */
  const ensureThread = async (): Promise<string> => {
    if (chatStore.currentThreadId) return chatStore.currentThreadId

    const chatApi = api.chat as any
    const { thread_id: tid } = await chatApi.createConversation() as { thread_id: string }
    chatStore.setCurrentThread(tid)
    chatStore.addConversation({
      id: tid,
      title: 'File Upload',
      type: 'task',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      message_count: 0,
    })
    return tid
  }

  const addFiles = async (files: File[]): Promise<FileRejection[]> => {
    const rejections: FileRejection[] = []
    const validFiles: File[] = []
    const resolvedTypes = new Map<File, string>()

    // Check count limit first
    const currentCount = attachedFiles.value.length
    const slotsAvailable = MAX_FILE_COUNT - currentCount

    for (const file of files) {
      if (validFiles.length >= slotsAvailable) {
        rejections.push({
          name: file.name,
          error: `Cannot attach more than ${MAX_FILE_COUNT} files`,
        })
        continue
      }

      const resolvedType = resolveFileType(file)
      if (!resolvedType) {
        rejections.push({ name: file.name, error: 'Unsupported file type' })
        continue
      }

      const maxFileSizeMb = config.public.chatFileMaxSizeMb
      if (file.size > maxFileSizeMb * 1024 * 1024) {
        rejections.push({ name: file.name, error: `File size exceeds ${maxFileSizeMb}MB limit` })
        continue
      }

      resolvedTypes.set(file, resolvedType)
      validFiles.push(file)
    }

    if (validFiles.length === 0) {
      return rejections
    }

    // Datasets are uploaded on send (see uploadPendingDatasets) — attaching one
    // must cost nothing, so a file removed before Enter leaves no connection
    // behind. Everything else still uploads now: it is free of LLM cost and the
    // text path needs the resulting file_ids.
    const otherFiles = validFiles.filter(f => !DATASET_TYPES.has(resolvedTypes.get(f)!))

    // Build attachment objects with initial status and preview URLs
    const newAttachments: UploadingFile[] = validFiles.map(file => ({
      file,
      file_id: null,
      connection_id: null,
      preview_url: IMAGE_TYPES.has(resolvedTypes.get(file)!) ? URL.createObjectURL(file) : null,
      resolved_type: resolvedTypes.get(file)!,
      status: DATASET_TYPES.has(resolvedTypes.get(file)!) ? 'attached' as const : 'uploading' as const,
      progress: 0,
    }))

    const startIndex = attachedFiles.value.length
    attachedFiles.value = [...attachedFiles.value, ...newAttachments]

    // Upload non-dataset files via chat files API
    if (otherFiles.length > 0) {
      try {
        const chatApi = api.chat as any
        const response = await chatApi.uploadChatFiles(
          otherFiles,
          (percent: number) => {
            for (const file of otherFiles) {
              const idx = startIndex + validFiles.indexOf(file)
              updateProgress(idx, percent)
            }
          },
          chatStore.currentThreadId || null
        ) as { files: Array<{ file_id: string; thread_id: string }>; thread_id: string }

        // Handle auto-created conversation
        if (response.thread_id && !chatStore.currentThreadId) {
          chatStore.setCurrentThread(response.thread_id)
          chatStore.addConversation({
            id: response.thread_id,
            title: 'File Upload',
            type: 'task',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            message_count: 0,
          })
        }

        response.files.forEach((fileResult, i) => {
          const idx = startIndex + validFiles.indexOf(otherFiles[i])
          markReady(idx, { file_id: fileResult.file_id })
        })
      } catch (err: any) {
        for (const file of otherFiles) {
          const idx = startIndex + validFiles.indexOf(file)
          markError(idx, err?.message || 'Upload failed')
        }
      }
    }

    return rejections
  }

  /**
   * Upload every dataset still sitting in 'attached'. Called from the send path,
   * so nothing reaches the server until the user actually asks a question.
   */
  const uploadPendingDatasets = async (threadId?: string): Promise<void> => {
    const pending = attachedFiles.value.filter(f => f.status === 'attached')
    if (pending.length === 0) return

    for (const pendingFile of pending) {
      const file = pendingFile.file
      const idx = indexOfFile(file)
      if (idx === -1) continue  // removed from the composer while an earlier one uploaded
      patchFile(idx, { status: 'uploading', progress: 0 })
      try {
        const tid = threadId || await ensureThread()
        const connectionsApi = api.connections as any
        const result = await connectionsApi.uploadDataset(
          file,
          undefined,
          (percent: number) => updateProgress(indexOfFile(file), percent),
          tid,
        ) as { id: number; name: string; row_count: number; source_filename?: string | null }
        markProcessing(indexOfFile(file), {
          file_id: `connection:${result.id}`,
          connection_id: result.id,
          row_count: result.row_count ?? null,
        })
        // Seed the connection cache now — a dashboard built from this upload in the
        // same session needs the filename to label its source, and the cache never
        // refetches once warm.
        upsertConnection({
          id: result.id,
          name: result.name,
          db_type: 'dataset',
          source_filename: result.source_filename,
        })
      } catch (err: any) {
        markError(indexOfFile(file), err?.message || 'Dataset upload failed')
      }
    }
  }

  const removeFile = (index: number) => {
    const file = attachedFiles.value[index]
    if (file?.preview_url) {
      URL.revokeObjectURL(file.preview_url)
    }
    attachedFiles.value = attachedFiles.value.filter((_, i) => i !== index)
  }

  const clearFiles = () => {
    // Keep all CSV/Excel files so the dataset panel continues showing them
    // across multiple messages in the same conversation. Mark them as sent so
    // subsequent messages don't re-embed them. The conversation-change watch
    // in useDatasetStatus clears them when switching chats.
    // resolved_type, not file.type: a drag-dropped CSV is often reported as
    // text/plain, and testing the raw type silently drops it from the send.
    attachedFiles.value = attachedFiles.value.map(f => {
      if (DATASET_TYPES.has(f.resolved_type)) return { ...f, sent: true }
      if (f.preview_url) URL.revokeObjectURL(f.preview_url)
      return null as any
    }).filter(Boolean)
  }

  const getFileIds = (): string[] => {
    return attachedFiles.value
      .filter(f => !f.sent && f.file_id !== null && DATASET_TYPES.has(f.resolved_type))
      .map(f => f.file_id as string)
  }

  /** Unsent datasets waiting for Enter — they make an empty message worth sending. */
  const hasPendingDatasets = computed<boolean>(() =>
    attachedFiles.value.some(f => !f.sent && DATASET_TYPES.has(f.resolved_type))
  )

  return {
    attachedFiles,
    addFiles,
    uploadPendingDatasets,
    removeFile,
    clearFiles,
    allFilesReady,
    canSubmitFiles,
    hasPendingDatasets,
    getFileIds,
  }
}
