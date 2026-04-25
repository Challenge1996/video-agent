<template>
  <div class="bg-animated">
    <div class="particles" ref="particlesRef"></div>
  </div>

  <div class="app-container">
    <Sidebar
      :conversations="conversations"
      :currentConversationId="currentConversationId"
      @new-chat="handleNewChat"
      @select-chat="handleSelectChat"
    />

    <main class="main-area">
      <ChatHeader
        :currentChatTitle="currentChatTitle"
        @clear-chat="handleClearChat"
      />

      <ChatArea
        :showWelcome="showWelcome"
        :messages="messages"
        :isLoading="isLoading"
        @quick-action="handleQuickAction"
      />

      <ToolsPanel />

      <InputArea
        v-model="messageInput"
        :isLoading="isLoading"
        @send="handleSendMessage"
      />
    </main>

    <ToastContainer :toasts="toasts" />
    <ModalContainer
      v-if="modal"
      :modal="modal"
      @cancel="modal = null"
      @confirm="handleModalConfirm"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import Sidebar from './components/Sidebar.vue'
import ChatHeader from './components/ChatHeader.vue'
import ChatArea from './components/ChatArea.vue'
import ToolsPanel from './components/ToolsPanel.vue'
import InputArea from './components/InputArea.vue'
import ToastContainer from './components/ToastContainer.vue'
import ModalContainer from './components/ModalContainer.vue'

const particlesRef = ref(null)
const conversations = ref([])
const currentConversationId = ref(null)
const currentChatTitle = ref('视频剪辑助手')
const showWelcome = ref(true)
const messages = ref([])
const messageInput = ref('')
const isLoading = ref(false)
const toasts = ref([])
const modal = ref(null)
const pendingModalAction = ref(null)

let toastId = 0

const showToast = (message, type = 'success') => {
  const id = toastId++
  toasts.value.push({ id, message, type })
  setTimeout(() => {
    const index = toasts.value.findIndex(t => t.id === id)
    if (index > -1) {
      toasts.value.splice(index, 1)
    }
  }, 3000)
}

const showModal = (title, desc, onConfirm, confirmText = '确认', confirmType = 'danger') => {
  pendingModalAction.value = onConfirm
  modal.value = { title, desc, confirmText, confirmType }
}

const handleModalConfirm = () => {
  if (pendingModalAction.value) {
    pendingModalAction.value()
  }
  modal.value = null
}

const fetchAPI = async (endpoint, options = {}) => {
  const url = '/api' + endpoint
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    },
    ...options
  }
  
  if (options.body) {
    config.body = JSON.stringify(options.body)
  }
  
  try {
    const response = await fetch(url, config)
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }
    return await response.json()
  } catch (error) {
    console.error('API Error:', error)
    throw error
  }
}

const loadConversations = async () => {
  try {
    const data = await fetchAPI('/conversations')
    conversations.value = data
  } catch (error) {
    console.error('加载对话列表失败:', error)
  }
}

const handleNewChat = async () => {
  try {
    const data = await fetchAPI('/conversations', {
      method: 'POST',
      body: { title: '新对话' }
    })
    
    currentConversationId.value = data.conversation_id
    messages.value = []
    showWelcome.value = true
    currentChatTitle.value = '视频剪辑助手'
    loadConversations()
    showToast('新建对话成功')
  } catch (error) {
    showToast('创建对话失败: ' + error.message, 'error')
  }
}

const handleSelectChat = async (convId, title) => {
  if (currentConversationId.value === convId) return
  
  currentConversationId.value = convId
  currentChatTitle.value = title
  
  try {
    const conversation = await fetchAPI(`/conversations/${convId}`)
    messages.value = []
    showWelcome.value = false
    
    conversation.messages.forEach(msg => {
      if (msg.role === 'user') {
        messages.value.push({
          id: msg.id,
          content: msg.content,
          role: 'user',
          time: formatTime(msg.timestamp)
        })
      } else if (msg.role === 'assistant') {
        messages.value.push({
          id: msg.id,
          content: msg.content,
          role: 'assistant',
          time: formatTime(msg.timestamp),
          toolResults: msg.tool_calls || []
        })
      }
    })
    
    loadConversations()
  } catch (error) {
    showToast('加载对话失败: ' + error.message, 'error')
  }
}

const handleClearChat = () => {
  if (!currentConversationId.value) return
  
  showModal(
    '清空对话',
    '确定要清空当前对话吗？此操作不可恢复。',
    () => {
      messages.value = []
      showWelcome.value = true
      showToast('对话已清空')
    }
  )
}

const handleQuickAction = (prompt) => {
  messageInput.value = prompt
}

const handleSendMessage = async () => {
  const message = messageInput.value.trim()
  
  if (!message || isLoading.value) return
  
  messageInput.value = ''
  
  if (!currentConversationId.value) {
    await handleNewChat()
  }
  
  showWelcome.value = false
  
  const userMessageId = Date.now()
  messages.value.push({
    id: userMessageId,
    content: message,
    role: 'user',
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  })
  
  isLoading.value = true
  
  try {
    const response = await fetchAPI('/chat', {
      method: 'POST',
      body: {
        message: message,
        conversation_id: currentConversationId.value,
        auto_execute_tools: true
      }
    })
    
    const assistantMessageId = Date.now() + 1
    messages.value.push({
      id: assistantMessageId,
      content: response.content,
      role: 'assistant',
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      toolResults: response.tool_results || []
    })
    
    currentChatTitle.value = message.substring(0, 30) + (message.length > 30 ? '...' : '')
    loadConversations()
    
  } catch (error) {
    const errorMessageId = Date.now() + 1
    messages.value.push({
      id: errorMessageId,
      content: '抱歉，发生了错误：' + error.message,
      role: 'assistant',
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    })
    showToast('发送消息失败: ' + error.message, 'error')
  } finally {
    isLoading.value = false
  }
}

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

const initParticles = () => {
  if (!particlesRef.value) return
  
  for (let i = 0; i < 20; i++) {
    const particle = document.createElement('div')
    particle.className = 'particle'
    particle.style.left = Math.random() * 100 + '%'
    particle.style.animationDelay = Math.random() * 15 + 's'
    particle.style.animationDuration = (15 + Math.random() * 10) + 's'
    particlesRef.value.appendChild(particle)
  }
}

onMounted(() => {
  initParticles()
  loadConversations()
  console.log('🎬 视频剪辑 Agent 前端初始化完成')
})
</script>
