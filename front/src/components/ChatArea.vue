<template>
  <div class="chat-area" ref="chatAreaRef">
    <div v-if="showWelcome" class="welcome-screen">
      <div class="welcome-icon">🎬</div>
      <h2 class="welcome-title">你好！我是视频剪辑助手</h2>
      <p class="welcome-subtitle">
        我可以帮你完成视频分割、语音合成、字幕生成、添加背景音乐等任务。
        请用自然语言告诉我你想要做什么。
      </p>
      <div class="quick-actions">
        <div 
          class="quick-action" 
          @click="$emit('quick-action', '帮我查看这个视频的信息：')"
        >
          <div class="quick-action-icon">📊</div>
          <div class="quick-action-title">查看视频信息</div>
          <div class="quick-action-desc">获取视频时长、分辨率等</div>
        </div>
        <div 
          class="quick-action" 
          @click="$emit('quick-action', '帮我分割这个视频：')"
        >
          <div class="quick-action-icon">✂️</div>
          <div class="quick-action-title">分割视频</div>
          <div class="quick-action-desc">将长视频剪成多个片段</div>
        </div>
        <div 
          class="quick-action" 
          @click="$emit('quick-action', '帮我生成字幕：')"
        >
          <div class="quick-action-icon">📝</div>
          <div class="quick-action-title">生成字幕</div>
          <div class="quick-action-desc">从文本生成SRT字幕</div>
        </div>
        <div 
          class="quick-action" 
          @click="$emit('quick-action', '帮我合成视频：')"
        >
          <div class="quick-action-icon">🚀</div>
          <div class="quick-action-title">一键合成</div>
          <div class="quick-action-desc">添加语音、字幕、音乐</div>
        </div>
      </div>
    </div>

    <div class="messages" :class="{ hidden: showWelcome }">
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="message"
        :class="msg.role"
      >
        <div class="message-avatar">
          {{ msg.role === 'user' ? '👤' : '🤖' }}
        </div>
        <div class="message-content">
          <div class="message-bubble">
            <div 
              v-if="msg.content" 
              class="markdown-content"
              v-html="renderMarkdown(msg.content)"
            ></div>
            
            <div 
              v-if="msg.todoList && msg.todoList.length > 0" 
              class="todo-list"
            >
              <div class="todo-header">
                <span class="todo-title">📋 任务进度</span>
                <span class="todo-progress">
                  {{ getCompletedCount(msg.todoList) }}/{{ msg.todoList.length }}
                </span>
              </div>
              <div 
                v-for="(item, idx) in msg.todoList" 
                :key="idx" 
                class="todo-item"
                :class="item.status"
              >
                <div class="todo-icon">
                  <span v-if="item.status === 'pending'">⏳</span>
                  <span v-else-if="item.status === 'in_progress'">🔄</span>
                  <span v-else-if="item.status === 'completed'">✅</span>
                  <span v-else-if="item.status === 'failed'">❌</span>
                </div>
                <div class="todo-content">
                  <div class="todo-text">{{ item.title }}</div>
                  <div v-if="item.error" class="todo-error">{{ item.error }}</div>
                  <div v-if="item.result" class="todo-result">{{ item.result }}</div>
                </div>
              </div>
            </div>
            
            <div
              v-for="(result, idx) in (msg.toolResults || [])"
              :key="idx"
              class="tool-result"
              :class="{ error: !result.success }"
            >
              <div class="tool-name">[{{ result.tool_name }}]</div>
              <div>{{ result.success ? '执行成功' : '失败: ' + result.error }}</div>
              <pre v-if="result.result">{{ JSON.stringify(result.result, null, 2).substring(0, 500) }}</pre>
            </div>
          </div>
          <div class="message-meta">
            <span>{{ msg.time }}</span>
          </div>
        </div>
      </div>

      <div v-if="isLoading" class="typing-indicator">
        <div class="message-avatar">🤖</div>
        <div class="typing-bubble">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, computed } from 'vue'
import { marked } from 'marked'

marked.setOptions({
  breaks: true,
  gfm: true,
})

const props = defineProps({
  showWelcome: {
    type: Boolean,
    default: true
  },
  messages: {
    type: Array,
    default: () => []
  },
  isLoading: {
    type: Boolean,
    default: false
  }
})

defineEmits(['quick-action'])

const chatAreaRef = ref(null)

const renderMarkdown = (content) => {
  if (!content) return ''
  try {
    return marked.parse(content)
  } catch (e) {
    console.error('Markdown解析错误:', e)
    return content.replace(/\n/g, '<br>')
  }
}

const getCompletedCount = (todoList) => {
  if (!todoList) return 0
  return todoList.filter(item => item.status === 'completed').length
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatAreaRef.value) {
      chatAreaRef.value.scrollTop = chatAreaRef.value.scrollHeight
    }
  })
}

watch(() => props.messages.length, () => {
  scrollToBottom()
})

watch(() => props.isLoading, () => {
  scrollToBottom()
})
</script>
