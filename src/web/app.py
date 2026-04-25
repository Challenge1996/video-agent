import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.video_editor_agent import (
    get_smart_agent,
    SmartVideoEditorAgent,
    tools,
)
from src.agents.conversation_manager import (
    get_conversation_manager,
    ConversationManager,
    Conversation,
    ConversationMessage,
    MessageRole,
)
from src.config.config import config


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    auto_execute_tools: bool = True


class CreateConversationRequest(BaseModel):
    title: str = "新对话"


class ToolExecuteRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]
    conversation_id: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_directories()
    print("=" * 60)
    print("视频剪辑 Agent - Web 服务启动中...")
    print("=" * 60)
    print(f"输出目录: {config.output_dir}")
    print(f"临时目录: {config.temp_dir}")
    
    try:
        agent = get_smart_agent()
        print(f"已注册工具数: {len(tools)}")
        print("=" * 60)
    except Exception as e:
        print(f"警告: Agent 初始化失败: {e}")
        print("请确保 OPENAI_API_KEY 等环境变量已正确配置")
    
    yield
    
    print("=" * 60)
    print("视频剪辑 Agent - Web 服务已关闭")
    print("=" * 60)


app = FastAPI(
    title="视频剪辑 Agent",
    description="基于 AI 的智能视频剪辑系统",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_message(self, client_id: str, message: Dict[str, Any]):
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_json(message)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections.values():
            await connection.send_json(message)


manager = ConnectionManager()


@app.get("/", response_class=HTMLResponse)
async def get_index():
    static_dir = Path(__file__).parent / "web" / "static"
    index_path = static_dir / "index.html"
    
    if index_path.exists():
        return FileResponse(str(index_path))
    
    html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>视频剪辑 Agent</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 60px;
            text-align: center;
            max-width: 500px;
        }
        h1 { color: #1a1a2e; margin-bottom: 20px; font-size: 2rem; }
        p { color: #666; margin-bottom: 30px; line-height: 1.6; }
        .status { 
            background: #f0f4ff; 
            padding: 20px; 
            border-radius: 10px;
            margin-bottom: 30px;
        }
        .status-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #e0e0e0;
        }
        .status-item:last-child { border-bottom: none; }
        .status-label { color: #666; }
        .status-value { color: #1a1a2e; font-weight: 600; }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 40px;
            border-radius: 30px;
            font-size: 1rem;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            text-decoration: none;
            display: inline-block;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
        }
        .features {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 30px;
        }
        .feature {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            font-size: 0.9rem;
            color: #555;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 视频剪辑 Agent</h1>
        <p>基于 AI 的智能视频剪辑系统<br>支持自然语言对话式操作</p>
        
        <div class="status">
            <div class="status-item">
                <span class="status-label">服务状态</span>
                <span class="status-value" style="color: #10b981;">运行中</span>
            </div>
            <div class="status-item">
                <span class="status-label">API 版本</span>
                <span class="status-value">2.0.0</span>
            </div>
        </div>
        
        <a href="/chat" class="btn">开始对话</a>
        
        <div class="features">
            <div class="feature">📹 视频分割</div>
            <div class="feature">🎤 TTS 语音</div>
            <div class="feature">📝 字幕生成</div>
            <div class="feature">🎵 背景音乐</div>
            <div class="feature">✨ 贴纸添加</div>
            <div class="feature">🚀 一键合成</div>
        </div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


@app.get("/chat", response_class=HTMLResponse)
async def get_chat_page():
    static_dir = Path(__file__).parent / "web" / "static"
    chat_path = static_dir / "chat.html"
    
    if chat_path.exists():
        return FileResponse(str(chat_path))
    
    html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>视频剪辑 Agent - 对话</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f7fb;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header h1 { font-size: 1.2rem; display: flex; align-items: center; gap: 10px; }
        .header .status { font-size: 0.85rem; opacity: 0.9; }
        .container {
            display: flex;
            flex: 1;
            overflow: hidden;
        }
        .sidebar {
            width: 280px;
            background: white;
            border-right: 1px solid #e0e0e0;
            padding: 20px;
            overflow-y: auto;
        }
        .sidebar h2 { font-size: 0.9rem; color: #666; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 0.5px; }
        .conversation-item {
            padding: 12px 15px;
            border-radius: 8px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: background 0.2s;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .conversation-item:hover { background: #f5f7fb; }
        .conversation-item.active { background: #f0f4ff; border-left: 3px solid #667eea; }
        .conversation-item .title { font-size: 0.9rem; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
        .conversation-item .time { font-size: 0.75rem; color: #999; margin-left: 10px; }
        .new-chat-btn {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
            margin-bottom: 20px;
        }
        .chat-area {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: #fafbfc;
        }
        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        .message {
            max-width: 80%;
            padding: 15px 20px;
            border-radius: 18px;
            line-height: 1.5;
            font-size: 0.95rem;
        }
        .message.user {
            align-self: flex-end;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-bottom-right-radius: 4px;
        }
        .message.assistant {
            align-self: flex-start;
            background: white;
            color: #333;
            border-bottom-left-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        .message.system {
            align-self: center;
            background: #f0f4ff;
            color: #667eea;
            font-size: 0.85rem;
            padding: 8px 16px;
        }
        .tool-result {
            background: #f8f9fa;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 12px;
            margin-top: 10px;
            font-family: monospace;
            font-size: 0.85rem;
            max-height: 200px;
            overflow-y: auto;
        }
        .input-area {
            padding: 20px;
            background: white;
            border-top: 1px solid #e0e0e0;
        }
        .input-container {
            display: flex;
            gap: 10px;
            align-items: flex-end;
        }
        .input-container textarea {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid #e0e0e0;
            border-radius: 20px;
            font-size: 0.95rem;
            resize: none;
            min-height: 44px;
            max-height: 120px;
            outline: none;
            transition: border-color 0.2s;
        }
        .input-container textarea:focus {
            border-color: #667eea;
        }
        .input-container button {
            padding: 12px 24px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: transform 0.2s;
        }
        .input-container button:hover { transform: scale(1.05); }
        .input-container button:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .typing-indicator {
            display: flex;
            gap: 4px;
            padding: 10px 15px;
            background: white;
            border-radius: 18px;
            align-self: flex-start;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        .typing-indicator span {
            width: 8px;
            height: 8px;
            background: #667eea;
            border-radius: 50%;
            animation: bounce 1.4s infinite ease-in-out;
        }
        .typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
        .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }
        .tools-panel {
            padding: 15px;
            background: #f8f9fa;
            border-top: 1px solid #e0e0e0;
        }
        .tools-panel h3 { font-size: 0.85rem; color: #666; margin-bottom: 10px; }
        .tool-tags { display: flex; flex-wrap: wrap; gap: 8px; }
        .tool-tag {
            padding: 4px 10px;
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 15px;
            font-size: 0.75rem;
            color: #666;
            cursor: pointer;
            transition: all 0.2s;
        }
        .tool-tag:hover { background: #f0f4ff; border-color: #667eea; color: #667eea; }
        .welcome-message {
            text-align: center;
            padding: 40px 20px;
            color: #666;
        }
        .welcome-message h2 { color: #1a1a2e; margin-bottom: 15px; }
        .welcome-message .quick-actions {
            display: flex;
            gap: 10px;
            justify-content: center;
            flex-wrap: wrap;
            margin-top: 20px;
        }
        .quick-action {
            padding: 10px 20px;
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 20px;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        .quick-action:hover { background: #f0f4ff; border-color: #667eea; }
        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: #999;
        }
        .empty-state .icon { font-size: 4rem; margin-bottom: 20px; opacity: 0.3; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎬 视频剪辑 Agent</h1>
        <span class="status">v2.0.0 - 在线</span>
    </div>
    
    <div class="container">
        <div class="sidebar">
            <button class="new-chat-btn" onclick="createNewConversation()">+ 新建对话</button>
            <h2>历史对话</h2>
            <div id="conversationList">
                <div class="empty-state">
                    <div class="icon">💬</div>
                    <p>暂无历史对话</p>
                </div>
            </div>
        </div>
        
        <div class="chat-area">
            <div class="messages" id="messages">
                <div class="welcome-message" id="welcomeMessage">
                    <h2>👋 你好！我是你的视频剪辑助手</h2>
                    <p>我可以帮你完成视频分割、语音合成、字幕生成、添加背景音乐等任务。<br>请用自然语言告诉我你想要做什么。</p>
                    <div class="quick-actions">
                        <span class="quick-action" onclick="sendQuickAction('帮我看看这个视频的信息')">📊 查看视频信息</span>
                        <span class="quick-action" onclick="sendQuickAction('帮我分割视频')">✂️ 分割视频</span>
                        <span class="quick-action" onclick="sendQuickAction('帮我生成字幕')">📝 生成字幕</span>
                        <span class="quick-action" onclick="sendQuickAction('帮我合成视频')">🚀 一键合成</span>
                    </div>
                </div>
            </div>
            
            <div class="tools-panel">
                <h3>可用工具</h3>
                <div class="tool-tags" id="toolTags">
                    <span class="tool-tag">📹 视频信息</span>
                    <span class="tool-tag">✂️ 分割视频</span>
                    <span class="tool-tag">🎤 TTS 语音</span>
                    <span class="tool-tag">📝 字幕生成</span>
                    <span class="tool-tag">🎵 背景音乐</span>
                    <span class="tool-tag">✨ 贴纸</span>
                    <span class="tool-tag">🚀 一键合成</span>
                    <span class="tool-tag">🔗 合并视频</span>
                </div>
            </div>
            
            <div class="input-area">
                <div class="input-container">
                    <textarea 
                        id="messageInput" 
                        placeholder="输入你想要做的事情，例如：帮我查看这个视频的信息..."
                        rows="1"
                        onkeydown="handleKeyDown(event)"
                        oninput="autoResize(this)"
                    ></textarea>
                    <button id="sendButton" onclick="sendMessage()">发送</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentConversationId = null;
        let isLoading = false;

        async function loadConversations() {
            try {
                const response = await fetch('/api/conversations');
                const conversations = await response.json();
                const list = document.getElementById('conversationList');
                
                if (conversations.length === 0) {
                    list.innerHTML = `
                        <div class="empty-state">
                            <div class="icon">💬</div>
                            <p>暂无历史对话</p>
                        </div>
                    `;
                    return;
                }
                
                list.innerHTML = conversations.map(conv => `
                    <div class="conversation-item ${conv.id === currentConversationId ? 'active' : ''}" 
                         onclick="loadConversation('${conv.id}')">
                        <span class="title">${conv.title}</span>
                        <span class="time">${formatTime(conv.updated_at)}</span>
                    </div>
                `).join('');
            } catch (e) {
                console.error('加载对话列表失败:', e);
            }
        }

        async function createNewConversation() {
            try {
                const response = await fetch('/api/conversations', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: '新对话' })
                });
                const data = await response.json();
                currentConversationId = data.conversation_id;
                clearMessages();
                loadConversations();
            } catch (e) {
                console.error('创建对话失败:', e);
            }
        }

        async function loadConversation(convId) {
            currentConversationId = convId;
            loadConversations();
            clearMessages();
            
            try {
                const response = await fetch(`/api/conversations/${convId}`);
                const conversation = await response.json();
                
                conversation.messages.forEach(msg => {
                    if (msg.role === 'user') {
                        addMessage(msg.content, 'user');
                    } else if (msg.role === 'assistant') {
                        addMessage(msg.content, 'assistant');
                    }
                });
            } catch (e) {
                console.error('加载对话失败:', e);
            }
        }

        function clearMessages() {
            const messagesDiv = document.getElementById('messages');
            const welcome = document.getElementById('welcomeMessage');
            if (welcome) {
                welcome.remove();
            }
            messagesDiv.innerHTML = '';
        }

        function addMessage(content, role) {
            const messagesDiv = document.getElementById('messages');
            const welcome = document.getElementById('welcomeMessage');
            if (welcome) {
                welcome.remove();
            }
            
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${role}`;
            messageDiv.textContent = content;
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function showTypingIndicator() {
            const messagesDiv = document.getElementById('messages');
            const typingDiv = document.createElement('div');
            typingDiv.className = 'typing-indicator';
            typingDiv.id = 'typingIndicator';
            typingDiv.innerHTML = '<span></span><span></span><span></span>';
            messagesDiv.appendChild(typingDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function hideTypingIndicator() {
            const indicator = document.getElementById('typingIndicator');
            if (indicator) {
                indicator.remove();
            }
        }

        function setLoading(loading) {
            isLoading = loading;
            const button = document.getElementById('sendButton');
            const input = document.getElementById('messageInput');
            button.disabled = loading;
            input.disabled = loading;
        }

        async function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            
            if (!message || isLoading) return;
            
            input.value = '';
            autoResize(input);
            
            if (!currentConversationId) {
                await createNewConversation();
            }
            
            addMessage(message, 'user');
            setLoading(true);
            showTypingIndicator();
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: message,
                        conversation_id: currentConversationId,
                        auto_execute_tools: true
                    })
                });
                
                const data = await response.json();
                hideTypingIndicator();
                
                let responseContent = data.content;
                if (data.tool_results && data.tool_results.length > 0) {
                    responseContent += '\n\n' + data.tool_results.map(r => 
                        `[${r.tool_name}] ${r.success ? '成功' : '失败: ' + r.error}`
                    ).join('\n');
                }
                
                addMessage(responseContent, 'assistant');
                loadConversations();
                
            } catch (e) {
                hideTypingIndicator();
                addMessage('抱歉，发生了错误：' + e.message, 'assistant');
            } finally {
                setLoading(false);
            }
        }

        function sendQuickAction(text) {
            const input = document.getElementById('messageInput');
            input.value = text;
            sendMessage();
        }

        function handleKeyDown(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        }

        function autoResize(textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
        }

        function formatTime(isoString) {
            const date = new Date(isoString);
            const now = new Date();
            const diff = now - date;
            
            if (diff < 60000) return '刚刚';
            if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前';
            if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前';
            if (diff < 604800000) return Math.floor(diff / 86400000) + '天前';
            
            return date.toLocaleDateString('zh-CN');
        }

        loadConversations();
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


@app.get("/api/status")
async def get_status():
    return JSONResponse({
        "status": "running",
        "version": "2.0.0",
        "tools_count": len(tools),
        "output_dir": config.output_dir,
        "temp_dir": config.temp_dir,
    })


@app.get("/api/tools")
async def get_tools():
    agent = get_smart_agent()
    tool_info = agent.get_tool_info()
    return JSONResponse({
        "tools": tool_info,
        "count": len(tool_info)
    })


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        agent = get_smart_agent()
        
        response = await agent.chat(
            user_input=request.message,
            conversation_id=request.conversation_id,
            auto_execute_tools=request.auto_execute_tools,
        )
        
        return JSONResponse({
            "content": response.content,
            "conversation_id": response.conversation_id,
            "tool_calls": response.tool_calls,
            "tool_results": response.tool_results,
            "is_complete": response.is_complete,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversations")
async def get_conversations():
    conv_manager = get_conversation_manager()
    conversations = conv_manager.get_all_conversations()
    
    return JSONResponse([
        {
            "id": conv.id,
            "title": conv.title,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "message_count": len(conv.messages),
        }
        for conv in sorted(conversations, key=lambda x: x.updated_at, reverse=True)
    ])


@app.post("/api/conversations")
async def create_conversation(request: CreateConversationRequest):
    conv_manager = get_conversation_manager()
    conversation = conv_manager.create_conversation(title=request.title)
    
    return JSONResponse({
        "conversation_id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
    })


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    conv_manager = get_conversation_manager()
    conversation = conv_manager.get_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    return JSONResponse({
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
        "messages": [
            {
                "id": msg.id,
                "role": msg.role.value,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "tool_calls": msg.tool_calls,
            }
            for msg in conversation.messages
        ],
        "context": conversation.context.to_dict(),
    })


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    conv_manager = get_conversation_manager()
    success = conv_manager.delete_conversation(conversation_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    return JSONResponse({"success": True})


@app.post("/api/tools/execute")
async def execute_tool(request: ToolExecuteRequest):
    try:
        agent = get_smart_agent()
        
        result = await agent.execute_tool_direct(
            tool_name=request.tool_name,
            parameters=request.parameters,
            conversation_id=request.conversation_id,
        )
        
        return JSONResponse({
            "tool_name": result.tool_name,
            "success": result.success,
            "result": result.result,
            "error": result.error,
            "execution_time": result.execution_time,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/chat/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    agent = get_smart_agent()
    
    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "ping":
                await manager.send_message(client_id, {"type": "pong"})
            
            elif message_type == "chat":
                user_message = data.get("message", "")
                conversation_id = data.get("conversation_id")
                auto_execute = data.get("auto_execute_tools", True)
                
                await manager.send_message(client_id, {
                    "type": "typing",
                    "status": "start"
                })
                
                try:
                    response = await agent.chat(
                        user_input=user_message,
                        conversation_id=conversation_id,
                        auto_execute_tools=auto_execute,
                    )
                    
                    await manager.send_message(client_id, {
                        "type": "typing",
                        "status": "stop"
                    })
                    
                    await manager.send_message(client_id, {
                        "type": "response",
                        "content": response.content,
                        "conversation_id": response.conversation_id,
                        "tool_calls": response.tool_calls,
                        "tool_results": response.tool_results,
                    })
                    
                except Exception as e:
                    await manager.send_message(client_id, {
                        "type": "typing",
                        "status": "stop"
                    })
                    await manager.send_message(client_id, {
                        "type": "error",
                        "message": str(e)
                    })
            
            elif message_type == "get_conversations":
                conv_manager = get_conversation_manager()
                conversations = conv_manager.get_all_conversations()
                
                await manager.send_message(client_id, {
                    "type": "conversations",
                    "data": [
                        {
                            "id": conv.id,
                            "title": conv.title,
                            "updated_at": conv.updated_at.isoformat(),
                            "message_count": len(conv.messages),
                        }
                        for conv in sorted(conversations, key=lambda x: x.updated_at, reverse=True)
                    ]
                })
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        print(f"WebSocket 错误: {e}")
        manager.disconnect(client_id)
