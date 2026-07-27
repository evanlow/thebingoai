import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { ref, computed, reactive } from 'vue'

// ── Stub Nuxt auto-imports as globals (before module import) ──────
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('watch', vi.fn())
vi.stubGlobal('onUnmounted', vi.fn())
vi.stubGlobal('useRuntimeConfig', () => ({ public: { chatFileMaxSizeMb: 50 } }))
// Add missing URL methods for happy-dom
if (!URL.createObjectURL) {
  (URL as any).createObjectURL = vi.fn(() => 'blob:mock')
}
if (!URL.revokeObjectURL) {
  (URL as any).revokeObjectURL = vi.fn()
}

// reactive: allFilesReady is a computed over docsPendingConnections, so a plain
// object would leave it serving a stale cached value after the test mutates it.
const mockChatStore = reactive({
  currentThreadId: null as string | null,
  docsPendingConnections: [] as number[],
  setCurrentThread: vi.fn(),
  addConversation: vi.fn(),
})
vi.stubGlobal('useChatStore', () => mockChatStore)

const mockUploadChatFiles = vi.fn()
const mockCreateConversation = vi.fn()
const mockUploadDataset = vi.fn()
vi.stubGlobal('useApi', () => ({
  chat: {
    uploadChatFiles: mockUploadChatFiles,
    createConversation: mockCreateConversation,
  },
  connections: {
    uploadDataset: mockUploadDataset,
  },
}))

// Use dynamic import to ensure stubs are applied before module loads
let useChatFileUpload: any

beforeAll(async () => {
  const mod = await import('~/composables/useChatFileUpload')
  useChatFileUpload = mod.useChatFileUpload
})

describe('useChatFileUpload', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockChatStore.currentThreadId = null
    mockChatStore.docsPendingConnections = []
    const { clearFiles, attachedFiles } = useChatFileUpload()
    // clearFiles retains CSV files, so also clear attachedFiles directly for test isolation
    clearFiles()
    attachedFiles.value = []
  })

  it('routes CSV files through connectionsApi.uploadDataset', async () => {
    mockCreateConversation.mockResolvedValue({ thread_id: 'new-thread' })
    mockUploadDataset.mockResolvedValue({ id: 42, name: 'test', row_count: 10 })

    const { addFiles, uploadPendingDatasets, attachedFiles } = useChatFileUpload()
    const file = new File(['a,b\n1,2'], 'test.csv', { type: 'text/csv' })
    await addFiles([file])
    await uploadPendingDatasets()

    // Should NOT call uploadChatFiles for CSV
    expect(mockUploadChatFiles).not.toHaveBeenCalled()
    // Should call uploadDataset with thread_id
    expect(mockUploadDataset).toHaveBeenCalledWith(
      file,
      undefined,
      expect.any(Function),
      'new-thread'
    )
    // Should create conversation first
    expect(mockCreateConversation).toHaveBeenCalled()
    expect(mockChatStore.setCurrentThread).toHaveBeenCalledWith('new-thread')
    // File should be ready with connection_id
    expect(attachedFiles.value[0].status).toBe('processing')
    expect(attachedFiles.value[0].connection_id).toBe(42)
  })

  describe('attaching costs nothing', () => {
    it('attaching a CSV and an XLSX performs no API call', async () => {
      const { addFiles, attachedFiles } = useChatFileUpload()
      const csv = new File(['a,b\n1,2'], 'test.csv', { type: 'text/csv' })
      const xlsx = new File([new ArrayBuffer(50)], 'sheet.xlsx', {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      })
      await addFiles([csv, xlsx])

      expect(mockUploadDataset).not.toHaveBeenCalled()
      expect(mockUploadChatFiles).not.toHaveBeenCalled()
      // No thread is created either — a wrong file costs nothing to remove.
      expect(mockCreateConversation).not.toHaveBeenCalled()

      expect(attachedFiles.value.map(f => f.status)).toEqual(['attached', 'attached'])
      expect(attachedFiles.value.every(f => f.connection_id === null)).toBe(true)
      expect(attachedFiles.value.every(f => f.file_id === null)).toBe(true)
    })

    it('attaching a PNG still uploads immediately', async () => {
      mockChatStore.currentThreadId = 'existing-thread'
      mockUploadChatFiles.mockResolvedValue({
        files: [{ file_id: 'f1', thread_id: 'existing-thread' }],
        thread_id: 'existing-thread',
      })

      const { addFiles, attachedFiles } = useChatFileUpload()
      const png = new File([new ArrayBuffer(100)], 'photo.png', { type: 'image/png' })
      await addFiles([png])

      expect(mockUploadChatFiles).toHaveBeenCalled()
      expect(attachedFiles.value[0].status).toBe('ready')
      expect(attachedFiles.value[0].file_id).toBe('f1')
    })
  })

  describe('uploadPendingDatasets', () => {
    it('uploads only attached datasets and stamps connection_id + file_id', async () => {
      mockChatStore.currentThreadId = 'thread-1'
      mockUploadDataset.mockResolvedValue({ id: 42, name: 'test', row_count: 10 })

      const { addFiles, uploadPendingDatasets, attachedFiles } = useChatFileUpload()
      await addFiles([new File(['a,b\n1,2'], 'test.csv', { type: 'text/csv' })])
      await uploadPendingDatasets('thread-1')

      expect(mockUploadDataset).toHaveBeenCalledTimes(1)
      expect(attachedFiles.value[0].status).toBe('processing')
      expect(attachedFiles.value[0].connection_id).toBe(42)
      expect(attachedFiles.value[0].file_id).toBe('connection:42')

      // A second send must not re-upload the same file.
      await uploadPendingDatasets('thread-1')
      expect(mockUploadDataset).toHaveBeenCalledTimes(1)
    })

    it('marks a failed dataset upload as error', async () => {
      mockChatStore.currentThreadId = 'thread-1'
      mockUploadDataset.mockRejectedValue(new Error('Dataset too large'))

      const { addFiles, uploadPendingDatasets, attachedFiles } = useChatFileUpload()
      await addFiles([new File(['a,b\n1,2'], 'test.csv', { type: 'text/csv' })])
      await uploadPendingDatasets('thread-1')

      expect(attachedFiles.value[0].status).toBe('error')
      expect(attachedFiles.value[0].error).toBe('Dataset too large')
    })

    it('does nothing when no dataset is attached', async () => {
      const { uploadPendingDatasets } = useChatFileUpload()
      await uploadPendingDatasets('thread-1')
      expect(mockUploadDataset).not.toHaveBeenCalled()
    })
  })

  it('routes non-dataset files through chatApi.uploadChatFiles', async () => {
    mockChatStore.currentThreadId = 'existing-thread'
    mockUploadChatFiles.mockResolvedValue({
      files: [{ file_id: 'f1', thread_id: 'existing-thread' }],
      thread_id: 'existing-thread',
    })

    const { addFiles } = useChatFileUpload()
    const file = new File([new ArrayBuffer(100)], 'photo.png', { type: 'image/png' })
    await addFiles([file])

    // Should call uploadChatFiles for images
    expect(mockUploadChatFiles).toHaveBeenCalled()
    // Should NOT call uploadDataset
    expect(mockUploadDataset).not.toHaveBeenCalled()
  })

  describe('allFilesReady — every dataset terminal, documentation included', () => {
    async function attachAndUpload() {
      mockChatStore.currentThreadId = 'thread-1'
      mockUploadDataset.mockResolvedValue({ id: 42, name: 'test', row_count: 10 })
      const composable = useChatFileUpload()
      await composable.addFiles([new File(['a,b\n1,2'], 'test.csv', { type: 'text/csv' })])
      return composable
    }

    it('is false while a dataset is merely attached', async () => {
      const { allFilesReady } = await attachAndUpload()
      expect(allFilesReady.value).toBe(false)
    })

    it('is false while a dataset is still processing', async () => {
      const { uploadPendingDatasets, allFilesReady } = await attachAndUpload()
      await uploadPendingDatasets('thread-1')
      expect(allFilesReady.value).toBe(false)
    })

    it('is false while the connection is awaiting documentation', async () => {
      const { uploadPendingDatasets, allFilesReady, attachedFiles } = await attachAndUpload()
      await uploadPendingDatasets('thread-1')
      // Profiling finished (the chip goes ready) but the docs are still generating.
      attachedFiles.value = attachedFiles.value.map(f => ({ ...f, status: 'ready' }))
      mockChatStore.docsPendingConnections = [42]

      expect(allFilesReady.value).toBe(false)
    })

    it('is true once documentation has cleared', async () => {
      const { uploadPendingDatasets, allFilesReady, attachedFiles } = await attachAndUpload()
      await uploadPendingDatasets('thread-1')
      attachedFiles.value = attachedFiles.value.map(f => ({ ...f, status: 'ready' }))
      mockChatStore.docsPendingConnections = [42]
      expect(allFilesReady.value).toBe(false)

      mockChatStore.docsPendingConnections = []
      expect(allFilesReady.value).toBe(true)
    })

    it('treats a failed upload as terminal so the composer unlocks', async () => {
      mockChatStore.currentThreadId = 'thread-1'
      mockUploadDataset.mockRejectedValue(new Error('nope'))
      const { addFiles, uploadPendingDatasets, allFilesReady } = useChatFileUpload()
      await addFiles([new File(['a,b\n1,2'], 'test.csv', { type: 'text/csv' })])
      await uploadPendingDatasets('thread-1')

      expect(allFilesReady.value).toBe(true)
    })
  })

  describe('canSubmitFiles / hasPendingDatasets — the send gate', () => {
    it('an attached dataset is submittable and counts as pending', async () => {
      const { addFiles, canSubmitFiles, hasPendingDatasets } = useChatFileUpload()
      await addFiles([new File(['a,b\n1,2'], 'test.csv', { type: 'text/csv' })])

      // Enter is what starts the upload — it must not be gated on being uploaded.
      expect(canSubmitFiles.value).toBe(true)
      expect(hasPendingDatasets.value).toBe(true)
    })

    it('a still-transferring image blocks submission', async () => {
      mockChatStore.currentThreadId = 'existing-thread'
      // Never resolves — the file stays in 'uploading'.
      mockUploadChatFiles.mockReturnValue(new Promise(() => {}))

      const { addFiles, canSubmitFiles } = useChatFileUpload()
      addFiles([new File([new ArrayBuffer(10)], 'photo.png', { type: 'image/png' })])
      await Promise.resolve()

      expect(canSubmitFiles.value).toBe(false)
    })

    it('hasPendingDatasets is false once the datasets are sent', async () => {
      mockChatStore.currentThreadId = 'thread-1'
      mockUploadDataset.mockResolvedValue({ id: 42, name: 'test', row_count: 10 })

      const { addFiles, uploadPendingDatasets, clearFiles, hasPendingDatasets } = useChatFileUpload()
      await addFiles([new File(['a,b\n1,2'], 'test.csv', { type: 'text/csv' })])
      await uploadPendingDatasets('thread-1')
      clearFiles()

      expect(hasPendingDatasets.value).toBe(false)
    })
  })

  it('getFileIds includes processing dataset files so they are referenced in chat messages', async () => {
    mockCreateConversation.mockResolvedValue({ thread_id: 'thread-1' })
    mockUploadDataset.mockResolvedValue({ id: 42, name: 'test', row_count: 10 })

    const { addFiles, uploadPendingDatasets, getFileIds } = useChatFileUpload()
    const file = new File(['a,b\n1,2'], 'test.csv', { type: 'text/csv' })
    await addFiles([file])
    await uploadPendingDatasets()

    const ids = getFileIds()
    expect(ids).toContain('connection:42')
  })

  it('uses existing thread_id for dataset uploads', async () => {
    mockChatStore.currentThreadId = 'existing-thread'
    mockUploadDataset.mockResolvedValue({ id: 42, name: 'test', row_count: 10 })

    const { addFiles, uploadPendingDatasets } = useChatFileUpload()
    const file = new File(['a,b\n1,2'], 'data.csv', { type: 'text/csv' })
    await addFiles([file])
    await uploadPendingDatasets('existing-thread')

    // Should NOT create a new conversation
    expect(mockCreateConversation).not.toHaveBeenCalled()
    // Should pass existing thread_id
    expect(mockUploadDataset).toHaveBeenCalledWith(
      file,
      undefined,
      expect.any(Function),
      'existing-thread'
    )
  })

  describe('drag-and-drop MIME type fallback', () => {
    it('accepts CSV file with empty MIME type (drag-and-drop)', async () => {
      mockCreateConversation.mockResolvedValue({ thread_id: 'thread-1' })
      mockUploadDataset.mockResolvedValue({ id: 10, name: 'data', row_count: 5 })

      const { addFiles, uploadPendingDatasets, attachedFiles } = useChatFileUpload()
      // Browsers sometimes report empty type for dragged CSV files
      const file = new File(['a,b\n1,2'], 'data.csv', { type: '' })
      const rejections = await addFiles([file])
      await uploadPendingDatasets()

      expect(rejections).toHaveLength(0)
      expect(mockUploadDataset).toHaveBeenCalled()
      expect(attachedFiles.value[0].status).toBe('processing')
    })

    it('accepts CSV file reported as text/plain (drag-and-drop)', async () => {
      mockCreateConversation.mockResolvedValue({ thread_id: 'thread-2' })
      mockUploadDataset.mockResolvedValue({ id: 11, name: 'data', row_count: 5 })

      const { addFiles, uploadPendingDatasets } = useChatFileUpload()
      const file = new File(['a,b\n1,2'], 'report.csv', { type: 'text/plain' })
      const rejections = await addFiles([file])
      await uploadPendingDatasets()

      expect(rejections).toHaveLength(0)
      expect(mockUploadDataset).toHaveBeenCalled()
    })

    it('treats a text/plain .csv as a dataset in clearFiles and getFileIds', async () => {
      // Regression: both used to test the raw file.type, so a drag-dropped CSV
      // was dropped from the send and purged from the panel instead of kept.
      mockChatStore.currentThreadId = 'thread-2'
      mockUploadDataset.mockResolvedValue({ id: 11, name: 'data', row_count: 5 })

      const { addFiles, uploadPendingDatasets, getFileIds, clearFiles, attachedFiles } =
        useChatFileUpload()
      await addFiles([new File(['a,b\n1,2'], 'report.csv', { type: 'text/plain' })])
      await uploadPendingDatasets('thread-2')

      expect(getFileIds()).toEqual(['connection:11'])

      clearFiles()
      // Kept (not revoked away) and marked sent, exactly like a text/csv file.
      expect(attachedFiles.value).toHaveLength(1)
      expect(attachedFiles.value[0].sent).toBe(true)
    })

    it('accepts XLSX file reported as application/octet-stream (drag-and-drop)', async () => {
      mockCreateConversation.mockResolvedValue({ thread_id: 'thread-3' })
      mockUploadDataset.mockResolvedValue({ id: 12, name: 'sheet', row_count: 100 })

      const { addFiles, uploadPendingDatasets } = useChatFileUpload()
      const file = new File([new ArrayBuffer(100)], 'sheet.xlsx', { type: 'application/octet-stream' })
      const rejections = await addFiles([file])
      await uploadPendingDatasets()

      expect(rejections).toHaveLength(0)
      expect(mockUploadDataset).toHaveBeenCalled()
    })

    it('rejects file with unrecognized extension and wrong MIME type', async () => {
      const { addFiles } = useChatFileUpload()
      const file = new File(['data'], 'archive.zip', { type: 'application/zip' })
      const rejections = await addFiles([file])

      expect(rejections).toHaveLength(1)
      expect(rejections[0].error).toBe('Unsupported file type')
      expect(mockUploadDataset).not.toHaveBeenCalled()
    })

    it('rejects file with no extension and unknown MIME type', async () => {
      const { addFiles } = useChatFileUpload()
      const file = new File(['data'], 'unknownfile', { type: '' })
      const rejections = await addFiles([file])

      expect(rejections).toHaveLength(1)
      expect(rejections[0].error).toBe('Unsupported file type')
    })
  })

  describe('sent flag', () => {
    it('getFileIds excludes files marked as sent', async () => {
      mockCreateConversation.mockResolvedValue({ thread_id: 'thread-1' })
      mockUploadDataset.mockResolvedValue({ id: 42, name: 'test', row_count: 10 })

      const { addFiles, uploadPendingDatasets, getFileIds, clearFiles } = useChatFileUpload()
      const file = new File(['a,b\n1,2'], 'test.csv', { type: 'text/csv' })
      await addFiles([file])
      await uploadPendingDatasets()

      clearFiles()

      const ids = getFileIds()
      expect(ids).toEqual([])
    })

    it('clearFiles marks CSV files as sent', async () => {
      mockCreateConversation.mockResolvedValue({ thread_id: 'thread-1' })
      mockUploadDataset.mockResolvedValue({ id: 42, name: 'test', row_count: 10 })

      const { addFiles, uploadPendingDatasets, clearFiles, attachedFiles } = useChatFileUpload()
      const file = new File(['a,b\n1,2'], 'test.csv', { type: 'text/csv' })
      await addFiles([file])
      await uploadPendingDatasets()

      clearFiles()

      expect(attachedFiles.value).toHaveLength(1)
      expect(attachedFiles.value[0].sent).toBe(true)
    })

    it('clearFiles does not mark ready files as sent (removes them)', async () => {
      mockCreateConversation.mockResolvedValue({ thread_id: 'thread-1' })
      mockUploadDataset.mockResolvedValue({ id: 42, name: 'test', row_count: 10 })

      const { addFiles, uploadPendingDatasets, clearFiles, attachedFiles } = useChatFileUpload()
      const file = new File(['a,b\n1,2'], 'sales.csv', { type: 'text/csv' })
      await addFiles([file])
      await uploadPendingDatasets()

      // Simulate ready state
      attachedFiles.value = attachedFiles.value.map(f => ({ ...f, status: 'ready' }))

      clearFiles()
      expect(attachedFiles.value).toHaveLength(1)
      expect(attachedFiles.value[0].sent).toBe(true)
    })
  })
})
