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
from src.agents.task_progress_manager import (
    get_task_progress_manager,
    TaskProgress,
    TodoItem,
    TodoStatus,
    ProgressCallback,
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
        print("请确保 LLM API 配置正确")
    
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

FRONT_DIR = PROJECT_ROOT / "front"


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
    index_path = FRONT_DIR / "index.html"
    
    if index_path.exists():
        return FileResponse(str(index_path))
    
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>视频剪辑 Agent</title>
</head>
<body style="margin:0;padding:0;display:flex;justify-content:center;align-items:center;height:100vh;background:#0a0a1a;font-family:Arial,sans-serif;color:white;">
    <div style="text-align:center;">
        <h1 style="font-size:48px;margin-bottom:20px;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">🎬 视频剪辑 Agent</h1>
        <p style="color:#a0a0c0;margin-bottom:40px;">前端页面未找到，请确保 front/index.html 存在</p>
        <a href="/docs" style="display:inline-block;padding:15px 30px;background:linear-gradient(135deg,#667eea,#764ba2);color:white;text-decoration:none;border-radius:10px;">查看 API 文档</a>
    </div>
</body>
</html>
""")


@app.get("/chat", response_class=HTMLResponse)
async def get_chat_page():
    return await get_index()


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
            "todo_list": response.todo_list,
            "task_id": response.task_id,
            "is_complete": response.is_complete,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
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
                "todo_list": msg.todo_list,
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
    task_progress_manager = get_task_progress_manager()
    
    progress_callback: Optional[ProgressCallback] = None
    event_loop = asyncio.get_event_loop()
    
    async def send_task_progress_async(cid: str, task: TaskProgress, todo: TodoItem):
        todo_list_data = [t.to_dict() for t in task.todos]
        
        await manager.send_message(cid, {
            "type": "task_progress",
            "message_id": task.message_id,
            "task_id": task.task_id,
            "conversation_id": task.conversation_id,
            "todo_item": todo.to_dict(),
            "todo_list": todo_list_data,
        })
    
    def create_progress_callback(cid: str, loop):
        def callback(task: TaskProgress, todo: TodoItem):
            try:
                asyncio.run_coroutine_threadsafe(
                    send_task_progress_async(cid, task, todo),
                    loop
                )
            except Exception as e:
                print(f"发送进度更新失败: {e}")
        
        return callback
    
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
                message_id = data.get("message_id")
                
                await manager.send_message(client_id, {
                    "type": "typing",
                    "status": "start"
                })
                
                if progress_callback:
                    task_progress_manager.unregister_callback(progress_callback)
                
                progress_callback = create_progress_callback(client_id, event_loop)
                task_progress_manager.register_callback(progress_callback)
                
                try:
                    response = await agent.chat(
                        user_input=user_message,
                        conversation_id=conversation_id,
                        auto_execute_tools=auto_execute,
                        message_id=message_id,
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
                        "todo_list": response.todo_list,
                        "task_id": response.task_id,
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
                
                finally:
                    if progress_callback:
                        task_progress_manager.unregister_callback(progress_callback)
                        progress_callback = None
            
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
        if progress_callback:
            task_progress_manager.unregister_callback(progress_callback)
        manager.disconnect(client_id)
    except Exception as e:
        print(f"WebSocket 错误: {e}")
        if progress_callback:
            task_progress_manager.unregister_callback(progress_callback)
        manager.disconnect(client_id)
