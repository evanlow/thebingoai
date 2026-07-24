<template>
  <div class="relative min-h-screen overflow-hidden">
    <!-- Instant top progress bar on every navigation so a slow page load never
         looks like the app is frozen on the previous page. -->
    <NuxtLoadingIndicator :height="3" color="#6366f1" />
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
