<template>
  <UiDialog
    :open="open"
    :closable="false"
    size="md"
  >
    <template #header>
      <h3 class="text-lg font-normal text-gray-900 dark:text-neutral-100 w-full text-center">Account Deactivated</h3>
    </template>
    <div class="space-y-4">
      <p class="text-center text-gray-700 dark:text-neutral-300">
        Your account has been deactivated.
      </p>

      <p class="text-sm text-gray-600 dark:text-neutral-400 text-center">
        To restore access, please contact your administrator at
        <a href="mailto:support@thebingo.ai" class="text-purple-600 hover:text-purple-700 hover:underline">support@thebingo.ai</a>.
      </p>
    </div>

    <template #footer>
      <div class="flex justify-center w-full">
        <button
          @click="handleLogout"
          class="inline-flex items-center justify-center px-4 py-2 border border-gray-300 dark:border-neutral-600 text-sm font-medium rounded-lg text-gray-700 dark:text-neutral-300 bg-white dark:bg-neutral-800 hover:bg-gray-50 dark:hover:bg-neutral-700"
        >
          Close
        </button>
      </div>
    </template>
  </UiDialog>
</template>

<script setup lang="ts">
import UiDialog from './ui/UiDialog.vue'
import { useAuthStore } from '~/stores/auth'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const authStore = useAuthStore()
const router = useRouter()

const handleLogout = async () => {
  emit('update:open', false)
  await authStore.logout()
  router.push('/login')
}
</script>
