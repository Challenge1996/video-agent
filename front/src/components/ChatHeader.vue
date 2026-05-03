<template>
  <header class="chat-header">
    <div class="chat-info">
      <div class="chat-avatar">🤖</div>
      <div class="chat-title">
        <h2>{{ currentChatTitle }}</h2>
        <p>智能视频编辑，支持自然语言操作</p>
      </div>
    </div>
    <div class="header-actions">
      <button class="icon-btn" title="设置">⚙️</button>
      <button class="icon-btn" title="清空对话" @click="$emit('clear-chat')">🗑️</button>
    </div>
  </header>
</template>

<script setup>
defineProps({
  currentChatTitle: {
    type: String,
    default: '视频剪辑助手'
  }
})

defineEmits(['clear-chat'])
</script>
