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
import { ref, onMounted, watch, onUnmounted } from 'vue'
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

const ws = ref(null)
const clientId = ref('client_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9))
const currentTaskMessageId = ref(null)
const reconnectAttempts = ref(0)
const maxReconnectAttempts = ref(5)

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

const connectWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ws/chat/${clientId.value}`
  
  console.log('连接 WebSocket:', wsUrl)
  
  ws.value = new WebSocket(wsUrl)
  
  ws.value.onopen = () => {
    console.log('WebSocket 连接成功')
    reconnectAttempts.value = 0
  }
  
  ws.value.onclose = (event) => {
    console.log('WebSocket 连接关闭:', event.code, event.reason)
    if (reconnectAttempts.value < maxReconnectAttempts.value) {
      reconnectAttempts.value++
      console.log(`尝试重连 (${reconnectAttempts.value}/${maxReconnectAttempts.value})...`)
      setTimeout(connectWebSocket, 1000 * reconnectAttempts.value)
    }
  }
  
  ws.value.onerror = (error) => {
    console.error('WebSocket 错误:', error)
  }
  
  ws.value.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      handleWebSocketMessage(data)
    } catch (error) {
      console.error('解析 WebSocket 消息失败:', error)
    }
  }
}

const handleWebSocketMessage = (data) => {
  console.log('收到 WebSocket 消息:', data)
  
  switch (data.type) {
    case 'pong':
      break
      
    case 'typing':
      if (data.status === 'start') {
        isLoading.value = true
      } else if (data.status === 'stop') {
        isLoading.value = false
      }
      break
      
    case 'task_progress':
      handleTaskProgress(data)
      break
      
    case 'response':
      handleWebSocketResponse(data)
      break
      
    case 'error':
      handleWebSocketError(data)
      break
      
    case 'conversations':
      conversations.value = data.data
      break
  }
}

const handleTaskProgress = (data) => {
  const { message_id, todo_item, todo_list } = data
  
  if (!currentTaskMessageId.value) return
  
  const messageIndex = messages.value.findIndex(m => m.id === currentTaskMessageId.value)
  
  if (messageIndex === -1) return
  
  const message = messages.value[messageIndex]
  
  if (todo_list) {
    message.todoList = todo_list
  }
  
  if (todo_item) {
    if (!message.todoList) {
      message.todoList = []
    }
    
    const itemIndex = message.todoList.findIndex(item => item.id === todo_item.id)
    
    if (itemIndex !== -1) {
      message.todoList[itemIndex] = {
        ...message.todoList[itemIndex],
        ...todo_item
      }
    } else {
      message.todoList.push(todo_item)
    }
  }
  
  messages.value = [...messages.value]
}

const handleWebSocketResponse = (data) => {
  isLoading.value = false
  
  if (currentTaskMessageId.value) {
    const messageIndex = messages.value.findIndex(m => m.id === currentTaskMessageId.value)
    if (messageIndex !== -1) {
      messages.value[messageIndex].content = data.content
      messages.value[messageIndex].toolResults = data.tool_results || []
      messages.value = [...messages.value]
    }
  }
  
  currentTaskMessageId.value = null
  loadConversations()
}

const handleWebSocketError = (data) => {
  isLoading.value = false
  
  if (currentTaskMessageId.value) {
    const messageIndex = messages.value.findIndex(m => m.id === currentTaskMessageId.value)
    if (messageIndex !== -1) {
      messages.value[messageIndex].content = '抱歉，发生了错误：' + data.message
      messages.value = [...messages.value]
    }
  }
  
  showToast('处理失败: ' + data.message, 'error')
  currentTaskMessageId.value = null
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
          toolResults: msg.tool_calls || [],
          todoList: msg.todo_list || []
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
  
  const assistantMessageId = Date.now() + 1
  currentTaskMessageId.value = assistantMessageId
  messages.value.push({
    id: assistantMessageId,
    content: '',
    role: 'assistant',
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    toolResults: [],
    todoList: []
  })
  
  isLoading.value = true
  
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    ws.value.send(JSON.stringify({
      type: 'chat',
      message: message,
      conversation_id: currentConversationId.value,
      auto_execute_tools: true,
      message_id: assistantMessageId
    }))
  } else {
    try {
      const response = await fetchAPI('/chat', {
        method: 'POST',
        body: {
          message: message,
          conversation_id: currentConversationId.value,
          auto_execute_tools: true
        }
      })
      
      const messageIndex = messages.value.findIndex(m => m.id === assistantMessageId)
      if (messageIndex !== -1) {
        messages.value[messageIndex].content = response.content
        messages.value[messageIndex].toolResults = response.tool_results || []
        messages.value[messageIndex].todoList = response.todo_list || []
        messages.value = [...messages.value]
      }
      
      currentChatTitle.value = message.substring(0, 30) + (message.length > 30 ? '...' : '')
      loadConversations()
      
    } catch (error) {
      const messageIndex = messages.value.findIndex(m => m.id === assistantMessageId)
      if (messageIndex !== -1) {
        messages.value[messageIndex].content = '抱歉，发生了错误：' + error.message
        messages.value = [...messages.value]
      }
      showToast('发送消息失败: ' + error.message, 'error')
    } finally {
      isLoading.value = false
      currentTaskMessageId.value = null
    }
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

const sendPing = () => {
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    ws.value.send(JSON.stringify({ type: 'ping' }))
  }
}

onMounted(() => {
  initParticles()
  loadConversations()
  connectWebSocket()
  
  setInterval(sendPing, 30000)
  
  console.log('🎬 视频剪辑 Agent 前端初始化完成')
})

onUnmounted(() => {
  if (ws.value) {
    ws.value.close()
  }
})
</script>
