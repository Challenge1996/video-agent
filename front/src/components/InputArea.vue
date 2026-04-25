<template>
  <div class="input-area">
    <div class="input-container">
      <div class="input-actions">
        <button class="icon-btn" title="上传文件">📎</button>
      </div>
      <textarea 
        v-model="internalValue"
        placeholder="输入你想要做的事情，例如：帮我查看这个视频的信息..."
        :rows="1"
        :disabled="isLoading"
        @keydown="handleKeydown"
        @input="handleInput"
        ref="textareaRef"
      ></textarea>
      <button 
        class="send-btn" 
        :disabled="isLoading || !internalValue.trim()"
        @click="$emit('send')"
      >
        ➤
      </button>
    </div>
    <div class="input-hint">
      按 <kbd>Enter</kbd> 发送消息，<kbd>Shift</kbd> + <kbd>Enter</kbd> 换行
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  isLoading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'send'])

const internalValue = ref(props.modelValue)
const textareaRef = ref(null)

watch(() => props.modelValue, (newVal) => {
  internalValue.value = newVal
  autoResize()
})

watch(internalValue, (newVal) => {
  emit('update:modelValue', newVal)
})

const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (internalValue.value.trim() && !props.isLoading) {
      emit('send')
    }
  }
}

const handleInput = () => {
  autoResize()
}

const autoResize = () => {
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
    textareaRef.value.style.height = Math.min(textareaRef.value.scrollHeight, 120) + 'px'
  }
}
</script>
