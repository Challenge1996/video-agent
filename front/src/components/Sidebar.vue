<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="logo">
        <div class="logo-icon">🎬</div>
        <div class="logo-text">
          <h1>视频剪辑 Agent</h1>
          <p>智能视频编辑助手</p>
        </div>
      </div>
      <button class="new-chat-btn" @click="$emit('new-chat')">
        <span>+</span>
        <span>新建对话</span>
      </button>
    </div>

    <div class="conversations-section">
      <div class="section-title">历史对话</div>
      <div class="conversations-list">
        <div 
          v-if="conversations.length === 0" 
          class="empty-conversations"
        >
          <div class="empty-icon">💬</div>
          <div class="empty-text">暂无历史对话</div>
        </div>
        
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="conversation-item"
          :class="{ active: conv.id === currentConversationId }"
          @click="$emit('select-chat', conv.id, conv.title)"
        >
          <div class="conversation-icon">💬</div>
          <div class="conversation-info">
            <div class="conversation-title">{{ conv.title }}</div>
            <div class="conversation-preview">{{ conv.message_count || 0 }} 条消息</div>
          </div>
          <div class="conversation-time">{{ formatTime(conv.updated_at) }}</div>
        </div>
      </div>
    </div>

    <div class="sidebar-footer">
      <div class="status-bar">
        <div class="status-dot"></div>
        <span class="status-text">系统在线 - v2.0.0</span>
      </div>
    </div>
  </aside>
</template>

<script setup>
const props = defineProps({
  conversations: {
    type: Array,
    default: () => []
  },
  currentConversationId: {
    type: String,
    default: null
  }
})

defineEmits(['new-chat', 'select-chat'])

const formatTime = (isoString) => {
  const date = new Date(isoString)
  const now = new Date()
  const diff = now - date
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'
  if (diff < 604800000) return Math.floor(diff / 86400000) + '天前'
  
  return date.toLocaleDateString('zh-CN')
}
</script>
