<template>
  <div class="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
    <h1 class="text-2xl font-semibold">Something went wrong</h1>
    <p class="max-w-md text-sm text-gray-500">
      {{ error?.statusCode === 404 ? 'Page not found.' : 'The app failed to load. The server may be busy — please try again.' }}
    </p>
    <button
      class="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
      @click="handleReload"
    >
      Reload
    </button>
  </div>
</template>

<script setup lang="ts">
import type { NuxtError } from '#app'

defineProps<{ error?: NuxtError }>()

const handleReload = () => clearError({ redirect: '/' })
</script>
