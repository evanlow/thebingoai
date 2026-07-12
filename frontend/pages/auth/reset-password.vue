<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-neutral-950">
    <div class="max-w-md w-full p-8 bg-white dark:bg-neutral-900 rounded-lg shadow-md">
      <div class="mb-8">
        <h2 class="text-3xl font-medium text-center text-gray-900 dark:text-neutral-100">New Password</h2>
      </div>

      <div v-if="!hasToken" class="p-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/60 rounded-lg text-sm text-red-600 dark:text-red-300 text-center">
        Invalid reset link. Please request a new one.
      </div>

      <div v-else-if="success" class="p-4 bg-green-50 dark:bg-green-950/40 border border-green-200 dark:border-green-900/60 rounded-lg text-sm text-green-700 dark:text-green-300 text-center">
        Password reset successfully.
        <NuxtLink to="/login" class="underline ml-1">Sign in</NuxtLink>
      </div>

      <form v-else @submit.prevent="handleSubmit" class="space-y-6">
        <div v-if="error" class="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/60 rounded-lg text-sm text-red-600 dark:text-red-300">
          {{ error }}
        </div>

        <UiInput
          v-model="newPassword"
          type="password"
          label="New Password"
          placeholder="••••••••"
          required
        />

        <UiInput
          v-model="confirmPassword"
          type="password"
          label="Confirm Password"
          placeholder="••••••••"
          required
        />

        <UiButton
          type="submit"
          variant="primary"
          :loading="loading"
          :disabled="loading"
          full-width
        >
          Reset Password
        </UiButton>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
const authStore = useAuthStore()
const route = useRoute()

const token = computed(() => route.query.token as string)
const hasToken = computed(() => !!token.value)
const newPassword = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const error = ref('')
const success = ref(false)

async function handleSubmit() {
  if (newPassword.value !== confirmPassword.value) {
    error.value = 'Passwords do not match'
    return
  }
  loading.value = true
  error.value = ''
  const result = await authStore.resetPassword(token.value || '', newPassword.value)
  loading.value = false
  if (result.success) {
    success.value = true
  } else {
    error.value = result.error || 'Password reset failed'
  }
}

definePageMeta({
  layout: 'blank'
})
</script>
