<template>
  <div class="toast-container">
    <div
      v-for="toast in toasts"
      :key="toast.id"
      class="toast"
      :class="toast.type"
    >
      <span class="toast-icon">{{ getIcon(toast.type) }}</span>
      <span class="toast-text">{{ toast.message }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  toasts: {
    type: Array,
    default: () => []
  }
})

const getIcon = (type) => {
  const icons = {
    success: '✅',
    error: '❌',
    warning: '⚠️'
  }
  return icons[type] || '✅'
}
</script>
