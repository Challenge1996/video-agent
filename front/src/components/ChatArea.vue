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
            <div v-html="msg.content.replace(/\n/g, '<br>')"></div>
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
import { ref, watch, nextTick } from 'vue'

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
