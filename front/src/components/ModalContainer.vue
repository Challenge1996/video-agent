<template>
  <div class="modal-overlay" @click.self="$emit('cancel')">
    <div class="modal">
      <h3 class="modal-title">{{ modal.title }}</h3>
      <p class="modal-desc">{{ modal.desc }}</p>
      <div class="modal-actions">
        <button class="modal-btn secondary" @click="$emit('cancel')">取消</button>
        <button 
          class="modal-btn" 
          :class="modal.confirmType"
          @click="$emit('confirm')"
        >
          {{ modal.confirmText }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  modal: {
    type: Object,
    required: true
  }
})

defineEmits(['cancel', 'confirm'])
</script>
