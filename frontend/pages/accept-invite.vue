<template>
  <div class="min-h-screen flex items-center justify-center p-6">
    <div class="w-full max-w-md rounded-xl border border-[var(--line)] p-6 text-center">
      <h1 class="text-xl font-medium mb-2">Workspace invitation</h1>
      <p v-if="state === 'working'" class="text-sm text-gray-500 dark:text-neutral-400">Accepting your invitation…</p>
      <template v-else-if="state === 'success'">
        <p class="text-sm text-green-600 mb-4">You've joined as a viewer.</p>
        <button class="rounded-lg border border-[var(--line)] px-3 py-1.5 text-sm" @click="goToWorkspace">Open workspace</button>
      </template>
      <p v-else-if="state === 'expired'" class="text-sm text-red-600">This invitation has expired. Ask the admin to resend it.</p>
      <p v-else-if="state === 'invalid'" class="text-sm text-red-600">This invitation link is invalid or already used.</p>
      <p v-else-if="state === 'mismatch'" class="text-sm text-red-600">{{ message }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '~/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const api = useApi() as any

const state = ref<'working' | 'success' | 'expired' | 'invalid' | 'mismatch'>('working')
const message = ref('')
const joinedOrgId = ref<string | null>(null)

onMounted(async () => {
  const token = String(route.query.token || '')
  if (!token) { state.value = 'invalid'; return }
  if (!auth.token) {
    router.push(`/login?returnTo=${encodeURIComponent(route.fullPath)}`)
    return
  }
  try {
    const res = await api.governance.acceptInvite(token)
    joinedOrgId.value = res.org_id
    state.value = 'success'
  } catch (e: any) {
    const detail = (e?.data?.detail ?? e?.message ?? '').toString().toLowerCase()
    if (detail.includes('expired')) state.value = 'expired'
    else if (detail.includes('already')) state.value = 'invalid'
    else if (detail.includes('sent to') || detail.includes('email')) { state.value = 'mismatch'; message.value = e?.data?.detail }
    else state.value = 'invalid'
  }
})

async function goToWorkspace() {
  // No workspace switching — shared dashboards surface in the dashboards view.
  window.location.href = '/'
}

definePageMeta({
  layout: 'blank',
})
</script>
