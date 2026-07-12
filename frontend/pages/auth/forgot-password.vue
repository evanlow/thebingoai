<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-neutral-950">
    <div class="max-w-md w-full p-8 bg-white dark:bg-neutral-900 rounded-lg shadow-md">
      <div class="mb-8">
        <h2 class="text-3xl font-medium text-center text-gray-900 dark:text-neutral-100">Forgot Password</h2>
        <p class="text-center text-sm text-gray-500 dark:text-neutral-400 mt-2">
          Enter your email and we'll send you a reset link.
        </p>
      </div>

      <div v-if="sent" class="p-4 bg-green-50 dark:bg-green-950/40 border border-green-200 dark:border-green-900/60 rounded-lg text-sm text-green-700 dark:text-green-300 text-center">
        Check your email for a password reset link.
      </div>

      <form v-else @submit.prevent="handleSubmit" class="space-y-6">
        <div v-if="error" class="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/60 rounded-lg text-sm text-red-600 dark:text-red-300">
          {{ error }}
        </div>

        <UiInput
          v-model="email"
          type="email"
          label="Email"
          placeholder="you@example.com"
          required
        />

        <UiButton
          type="submit"
          variant="primary"
          :loading="loading"
          :disabled="loading"
          full-width
        >
          Send Reset Link
        </UiButton>
      </form>

      <p class="mt-6 text-center text-sm text-gray-500 dark:text-neutral-400">
        <NuxtLink to="/login" class="text-gray-900 dark:text-neutral-100 hover:underline">Back to sign in</NuxtLink>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
const authStore = useAuthStore()

const email = ref('')
const loading = ref(false)
const error = ref('')
const sent = ref(false)

async function handleSubmit() {
  loading.value = true
  error.value = ''
  const result = await authStore.forgotPassword(email.value)
  loading.value = false
  if (result.success) {
    sent.value = true
  } else {
    error.value = result.error || 'Failed to send reset email'
  }
}

definePageMeta({
  layout: 'blank'
})
</script>
