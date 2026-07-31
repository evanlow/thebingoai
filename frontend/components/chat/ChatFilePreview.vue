<template>
  <div
    class="relative flex items-center gap-2 rounded-lg border bg-neutral-50 dark:bg-neutral-800"
    :class="[
      isImage ? 'h-16 w-16 p-0 overflow-hidden' : 'h-12 px-3 py-2 max-w-48',
      displayStatus === 'ready' && !isImage
        ? 'border-[#22c55e44]'
        : 'border-neutral-200 dark:border-neutral-700',
    ]"
    :title="statusTitle"
  >
    <!-- Image thumbnail -->
    <template v-if="isImage">
      <img
        v-if="file.preview_url"
        :src="file.preview_url"
        :alt="file.file.name"
        class="h-full w-full object-cover"
      />
      <div
        v-else
        class="flex h-full w-full items-center justify-center bg-neutral-100 dark:bg-neutral-700"
      >
        <component :is="ImageIcon" class="h-6 w-6 text-neutral-400 dark:text-neutral-500" />
      </div>
    </template>

    <!-- Document icon + metadata -->
    <template v-else>
      <!-- eslint-disable-next-line vue/no-v-html -- static bundled SVG asset -->
      <div v-if="brandIcon" class="h-5 w-5 flex-shrink-0" v-html="brandIcon" />
      <component
        v-else
        :is="fileIcon"
        class="h-5 w-5 flex-shrink-0 text-neutral-500 dark:text-neutral-400"
      />
      <div class="min-w-0 flex-1">
        <p class="truncate text-sm font-medium text-neutral-800 dark:text-neutral-200">
          {{ file.file.name }}
        </p>
        <p class="text-sm text-neutral-500 dark:text-neutral-400">
          {{ formattedSize }}<span v-if="showBar"> · {{ Math.round(barPercent) }}%</span>
        </p>
      </div>
    </template>

    <!-- Error indicator -->
    <div
      v-if="displayStatus === 'error'"
      class="absolute inset-0 flex items-center justify-center rounded-lg bg-red-50/80 dark:bg-red-950/60"
      :title="file.error ?? 'Upload failed'"
    >
      <component
        :is="AlertCircle"
        class="h-4 w-4 text-red-500 dark:text-red-400"
      />
    </div>

    <!-- Upload / processing bar along the bottom edge — never covers the filename.
         One continuous 0→99% run across transfer + server-side processing. -->
    <div
      v-if="showBar"
      class="absolute inset-x-0 bottom-0 h-[3px] overflow-hidden rounded-b-lg bg-neutral-200 dark:bg-neutral-700"
      role="progressbar"
      :aria-label="serverPhase ? 'Processing file' : 'Uploading file'"
      :aria-valuenow="Math.round(barPercent)"
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <div
        class="h-full bg-violet-500 transition-all duration-500 ease-out"
        :style="{ width: `${barPercent}%` }"
      />
    </div>

    <!-- Remove button — shown on hover, always visible when error/uploading is not active -->
    <button
      v-if="displayStatus !== 'uploading'"
      type="button"
      class="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-neutral-600 text-white opacity-0 transition-opacity group-hover:opacity-100 hover:bg-neutral-800 dark:bg-neutral-500 dark:hover:bg-neutral-300 dark:hover:text-neutral-900"
      :title="`Remove ${file.file.name}`"
      @click.stop="emit('remove', index)"
    >
      <component :is="X" class="h-2.5 w-2.5" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { IMAGE_MIME_TYPES } from '~/composables/_chatConstants'
import { fileIconHtml } from '~/composables/useFileIcons'
import { Image as ImageIcon, FileText, File, AlertCircle, X } from 'lucide-vue-next'
import type { UploadingFile } from '~/composables/useChatFileUpload'

interface Props {
  file: UploadingFile
  index: number
  effectiveStatus?: UploadingFile['status']
}

const props = defineProps<Props>()

const displayStatus = computed(() => props.effectiveStatus ?? props.file.status)

const emit = defineEmits<{
  remove: [index: number]
}>()

// Browser MIME is unreliable on drag-and-drop; addFiles stores the corrected one.
const resolvedType = computed(() => props.file.resolved_type || props.file.file.type)

const isImage = computed(() => IMAGE_MIME_TYPES.has(resolvedType.value))

const brandIcon = computed(() => fileIconHtml(resolvedType.value, props.file.file.name))

const fileIcon = computed(() => {
  const type = resolvedType.value
  if (type === 'application/pdf') return FileText
  if (type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') return FileText
  return File
})

const showBar = computed(() => displayStatus.value === 'uploading' || displayStatus.value === 'processing')

// Bytes are in but the server is still parsing/profiling. 'uploading' at 100%
// belongs here too — it's the gap before markProcessing lands.
const serverPhase = computed(() =>
  displayStatus.value === 'processing' ||
  (displayStatus.value === 'uploading' && (props.file.progress ?? 0) >= 100)
)

const statusTitle = computed(() => {
  if (displayStatus.value === 'error') return props.file.error ?? 'Upload failed'
  if (!showBar.value) return props.file.file.name
  return serverPhase.value ? 'Processing…' : 'Uploading…'
})

// One monotonic 0→99 run for the whole lifecycle: bytes transferred fill the
// first UPLOAD_SHARE, then the server phase eases toward CEILING. Never 100 —
// that's the 'ready' state, which hides the bar entirely.
const UPLOAD_SHARE = 0.7
const CEILING = 99
const CREEP_MS = 400

const barPercent = ref(0)
let creepTimer: ReturnType<typeof setInterval> | null = null

function stopCreep() {
  if (creepTimer) {
    clearInterval(creepTimer)
    creepTimer = null
  }
}

watch(
  () => [displayStatus.value, props.file.progress ?? 0] as const,
  ([status, progress]) => {
    if (!showBar.value) {
      stopCreep()
      barPercent.value = 0
      return
    }
    if (serverPhase.value) {
      barPercent.value = Math.max(barPercent.value, 100 * UPLOAD_SHARE)
      // No server-side percentage exists for schema build + profiling, so ease
      // toward the ceiling instead. ponytail: swap for real step progress if the
      // profiling API ever reports one.
      if (!creepTimer) {
        creepTimer = setInterval(() => {
          barPercent.value += (CEILING - barPercent.value) * 0.08
        }, CREEP_MS)
      }
      return
    }
    stopCreep()
    // max() so a late/out-of-order progress event can't walk the bar backwards
    barPercent.value = Math.max(barPercent.value, progress * UPLOAD_SHARE)
  },
  { immediate: true }
)

onUnmounted(stopCreep)

const formattedSize = computed(() => {
  const bytes = props.file.file.size
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
})
</script>
