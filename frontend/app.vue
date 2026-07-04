<template>
  <div class="relative min-h-screen overflow-hidden">
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
    <Toaster position="top-right" />
  </div>
</template>

<script setup lang="ts">
// Initialize keyboard shortcuts
useKeyboardShortcuts()
// Apply persisted paper theme (kraft / cool / ink) on first client load
useAppTheme()
// Apply persisted text size (sm / md / lg) on first client load
useAppFontSize()
</script>
