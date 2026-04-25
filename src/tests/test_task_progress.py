import os
import sys
import json
import tempfile
import shutil
import pytest
import asyncio
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List, Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.task_progress_manager import (
    TaskProgressManager,
    TaskProgress,
    TodoItem,
    TodoStatus,
    ProgressCallback,
    get_task_progress_manager,
)

from src.agents.conversation_manager import (
    ConversationManager,
    get_conversation_manager,
    Conversation,
    ConversationMessage,
    ConversationContext,
    MessageRole,
)

from src.agents.video_editor_agent import (
    SmartVideoEditorAgent,
    ChatResponse,
    get_smart_agent,
)


class TestTodoItem:
    """TodoItem 测试"""

    def test_todo_item_creation(self):
        """测试 TodoItem 创建"""
        todo = TodoItem(
            id="test_123",
            title="测试任务",
            status=TodoStatus.PENDING,
        )
        
        assert todo.id == "test_123"
        assert todo.title == "测试任务"
        assert todo.status == TodoStatus.PENDING
        assert todo.error is None
        assert todo.result is None
        
        print(f"\n✓ TodoItem 创建成功:")
        print(f"  - ID: {todo.id}")
        print(f"  - 标题: {todo.title}")
        print(f"  - 状态: {todo.status.value}")

    def test_todo_item_to_dict(self):
        """测试 TodoItem 序列化"""
        todo = TodoItem(
            id="test_123",
            title="测试任务",
            status=TodoStatus.IN_PROGRESS,
            error=None,
            result={"output": "test"},
            metadata={"tool": "test_tool"},
        )
        
        data = todo.to_dict()
        
        assert data["id"] == "test_123"
        assert data["title"] == "测试任务"
        assert data["status"] == "in_progress"
        assert data["result"] == {"output": "test"}
        assert data["metadata"] == {"tool": "test_tool"}
        assert "created_at" in data
        assert "updated_at" in data
        
        print(f"\n✓ TodoItem 序列化成功:")
        print(f"  - 数据: {json.dumps(data, ensure_ascii=False, default=str)}")

    def test_todo_item_from_dict(self):
        """测试 TodoItem 反序列化"""
        now = datetime.now()
        data = {
            "id": "test_456",
            "title": "反序列化测试",
            "status": "completed",
            "error": None,
            "result": {"success": True},
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "metadata": {"test": True},
        }
        
        todo = TodoItem.from_dict(data)
        
        assert todo.id == "test_456"
        assert todo.title == "反序列化测试"
        assert todo.status == TodoStatus.COMPLETED
        assert todo.result == {"success": True}
        
        print(f"\n✓ TodoItem 反序列化成功:")
        print(f"  - 标题: {todo.title}")
        print(f"  - 状态: {todo.status.value}")

    def test_todo_status_enum(self):
        """测试 TodoStatus 枚举"""
        statuses = [
            TodoStatus.PENDING,
            TodoStatus.IN_PROGRESS,
            TodoStatus.COMPLETED,
            TodoStatus.FAILED,
        ]
        
        expected_values = ["pending", "in_progress", "completed", "failed"]
        
        for status, expected in zip(statuses, expected_values):
            assert status.value == expected
        
        print(f"\n✓ TodoStatus 枚举验证成功:")
        for status in statuses:
            print(f"  - {status.name}: {status.value}")


class TestTaskProgress:
    """TaskProgress 测试"""

    def test_task_progress_creation(self):
        """测试 TaskProgress 创建"""
        task = TaskProgress(
            task_id="task_123",
            message_id="msg_456",
            conversation_id="conv_789",
            title="视频编辑任务",
        )
        
        assert task.task_id == "task_123"
        assert task.message_id == "msg_456"
        assert task.conversation_id == "conv_789"
        assert task.title == "视频编辑任务"
        assert len(task.todos) == 0
        assert task.is_complete is False
        
        print(f"\n✓ TaskProgress 创建成功:")
        print(f"  - 任务ID: {task.task_id}")
        print(f"  - 标题: {task.title}")

    def test_task_progress_to_dict(self):
        """测试 TaskProgress 序列化"""
        todo = TodoItem(id="todo_1", title="子任务1", status=TodoStatus.PENDING)
        task = TaskProgress(
            task_id="task_123",
            title="测试任务",
            todos=[todo],
            is_complete=False,
        )
        
        data = task.to_dict()
        
        assert data["task_id"] == "task_123"
        assert data["title"] == "测试任务"
        assert len(data["todos"]) == 1
        assert data["todos"][0]["id"] == "todo_1"
        assert data["is_complete"] is False
        
        print(f"\n✓ TaskProgress 序列化成功:")
        print(f"  - 任务ID: {data['task_id']}")
        print(f"  - Todo数量: {len(data['todos'])}")

    def test_task_progress_counts(self):
        """测试任务进度计数"""
        task = TaskProgress(task_id="test", title="测试")
        
        task.todos.append(TodoItem(id="1", title="已完成", status=TodoStatus.COMPLETED))
        task.todos.append(TodoItem(id="2", title="进行中", status=TodoStatus.IN_PROGRESS))
        task.todos.append(TodoItem(id="3", title="待处理", status=TodoStatus.PENDING))
        
        assert task.get_total_count() == 3
        assert task.get_completed_count() == 1
        assert task.get_progress_percentage() == (1 / 3) * 100
        assert task.all_completed() is False
        
        task.todos = []
        task.todos.append(TodoItem(id="1", title="已完成1", status=TodoStatus.COMPLETED))
        task.todos.append(TodoItem(id="2", title="已完成2", status=TodoStatus.COMPLETED))
        task.todos.append(TodoItem(id="3", title="失败", status=TodoStatus.FAILED))
        assert task.all_completed() is True
        
        print(f"\n✓ 任务进度计数测试成功:")
        print(f"  - 总任务数: {task.get_total_count()}")
        print(f"  - 已完成数: {task.get_completed_count()}")
        print(f"  - 进度百分比: {task.get_progress_percentage():.1f}%")
        print(f"  - 全部完成: {task.all_completed()}")


class TestTaskProgressManager:
    """TaskProgressManager 测试"""

    def setup_method(self):
        """测试前准备"""
        self.manager = TaskProgressManager()

    def test_create_task(self):
        """测试创建任务"""
        task = self.manager.create_task(
            title="测试任务",
            conversation_id="conv_123",
            message_id="msg_456",
        )
        
        assert task.task_id is not None
        assert task.title == "测试任务"
        assert task.conversation_id == "conv_123"
        assert task.message_id == "msg_456"
        
        retrieved = self.manager.get_task(task.task_id)
        assert retrieved is not None
        assert retrieved.task_id == task.task_id
        
        print(f"\n✓ 任务创建成功:")
        print(f"  - 任务ID: {task.task_id}")
        print(f"  - 标题: {task.title}")

    def test_add_todo(self):
        """测试添加 Todo"""
        task = self.manager.create_task(title="测试任务")
        
        todo = self.manager.add_todo(
            task_id=task.task_id,
            title="子任务1",
            status=TodoStatus.PENDING,
            metadata={"tool": "test_tool"},
        )
        
        assert todo.id is not None
        assert todo.title == "子任务1"
        assert todo.status == TodoStatus.PENDING
        assert todo.metadata == {"tool": "test_tool"}
        
        retrieved_task = self.manager.get_task(task.task_id)
        assert len(retrieved_task.todos) == 1
        assert retrieved_task.todos[0].id == todo.id
        
        print(f"\n✓ Todo 添加成功:")
        print(f"  - Todo ID: {todo.id}")
        print(f"  - 标题: {todo.title}")

    def test_update_todo_status(self):
        """测试更新 Todo 状态"""
        task = self.manager.create_task(title="测试任务")
        todo = self.manager.add_todo(task_id=task.task_id, title="测试Todo")
        
        updated = self.manager.update_todo_status(
            task_id=task.task_id,
            todo_id=todo.id,
            status=TodoStatus.IN_PROGRESS,
        )
        
        assert updated.status == TodoStatus.IN_PROGRESS
        
        completed = self.manager.complete_todo(
            task_id=task.task_id,
            todo_id=todo.id,
            result={"output": "success"},
        )
        
        assert completed.status == TodoStatus.COMPLETED
        assert completed.result == {"output": "success"}
        
        failed_todo = self.manager.add_todo(task_id=task.task_id, title="失败任务")
        failed = self.manager.fail_todo(
            task_id=task.task_id,
            todo_id=failed_todo.id,
            error="测试错误信息",
        )
        
        assert failed.status == TodoStatus.FAILED
        assert failed.error == "测试错误信息"
        
        print(f"\n✓ Todo 状态更新测试成功:")
        print(f"  - 进行中: {updated.status.value}")
        print(f"  - 已完成: {completed.status.value}")
        print(f"  - 失败: {failed.status.value}")

    def test_progress_callback(self):
        """测试进度回调"""
        callback_calls = []
        
        def callback(task: TaskProgress, todo: TodoItem):
            callback_calls.append({"task_id": task.task_id, "todo_id": todo.id, "status": todo.status})
        
        self.manager.register_callback(callback)
        
        task = self.manager.create_task(title="测试任务")
        
        assert len(callback_calls) == 0
        
        todo = self.manager.add_todo(task_id=task.task_id, title="测试Todo")
        
        assert len(callback_calls) == 1
        assert callback_calls[0]["todo_id"] == todo.id
        assert callback_calls[0]["task_id"] == task.task_id
        
        completed_todo = self.manager.complete_todo(
            task_id=task.task_id,
            todo_id=todo.id,
            result={"success": True},
        )
        
        assert len(callback_calls) == 2
        assert callback_calls[1]["status"] == TodoStatus.COMPLETED
        
        self.manager.unregister_callback(callback)
        
        self.manager.add_todo(task_id=task.task_id, title="另一个Todo")
        
        assert len(callback_calls) == 2
        
        print(f"\n✓ 进度回调测试成功:")
        print(f"  - 回调次数: {len(callback_calls)}")
        for call in callback_calls:
            print(f"    - task_id: {call['task_id']}, todo_id: {call['todo_id']}, status: {call['status']}")

    def test_get_all_tasks(self):
        """测试获取所有任务"""
        assert len(self.manager.get_all_tasks()) == 0
        
        self.manager.create_task(title="任务1")
        self.manager.create_task(title="任务2")
        
        tasks = self.manager.get_all_tasks()
        assert len(tasks) == 2
        
        print(f"\n✓ 获取所有任务测试成功:")
        print(f"  - 任务数量: {len(tasks)}")

    def test_clear_task(self):
        """测试清除任务"""
        task = self.manager.create_task(title="待删除任务")
        
        assert self.manager.get_task(task.task_id) is not None
        
        self.manager.clear_task(task.task_id)
        
        assert self.manager.get_task(task.task_id) is None
        
        print(f"\n✓ 清除任务测试成功:")
        print(f"  - 已清除任务ID: {task.task_id}")


class TestChatResponseWithTodo:
    """带 TodoList 的 ChatResponse 测试"""

    def test_chat_response_with_todo_list(self):
        """测试包含 todo_list 的 ChatResponse"""
        todo_list = [
            {"id": "1", "title": "任务1", "status": "completed"},
            {"id": "2", "title": "任务2", "status": "in_progress"},
        ]
        
        response = ChatResponse(
            content="测试回复",
            todo_list=todo_list,
            task_id="task_123",
            conversation_id="conv_456",
            is_complete=True,
        )
        
        assert response.content == "测试回复"
        assert response.todo_list == todo_list
        assert response.task_id == "task_123"
        assert response.conversation_id == "conv_456"
        assert response.is_complete is True
        
        print(f"\n✓ ChatResponse with todo_list 测试成功:")
        print(f"  - 内容: {response.content}")
        print(f"  - Todo数量: {len(response.todo_list)}")
        print(f"  - 任务ID: {response.task_id}")


class TestConversationMessageWithTodo:
    """带 TodoList 的 ConversationMessage 测试"""

    def test_conversation_message_with_todo_list(self):
        """测试包含 todo_list 的 ConversationMessage"""
        todo_list = [
            {"id": "1", "title": "获取视频信息", "status": "completed"},
            {"id": "2", "title": "生成字幕", "status": "in_progress"},
        ]
        
        message = ConversationMessage(
            id="msg_123",
            role=MessageRole.ASSISTANT,
            content="这是助手回复",
            timestamp=datetime.now(),
            todo_list=todo_list,
        )
        
        assert message.id == "msg_123"
        assert message.role == MessageRole.ASSISTANT
        assert message.content == "这是助手回复"
        assert message.todo_list == todo_list
        
        data = message.to_dict()
        assert data["todo_list"] == todo_list
        
        print(f"\n✓ ConversationMessage with todo_list 测试成功:")
        print(f"  - 消息ID: {message.id}")
        print(f"  - Todo数量: {len(message.todo_list)}")


class TestSingleton:
    """单例模式测试"""

    def test_get_task_progress_manager_singleton(self):
        """测试 TaskProgressManager 单例"""
        manager1 = get_task_progress_manager()
        manager2 = get_task_progress_manager()
        
        assert manager1 is manager2
        
        print(f"\n✓ TaskProgressManager 单例测试成功:")
        print(f"  - 两次获取同一实例: {manager1 is manager2}")


if __name__ == "__main__":
    print("=" * 60)
    print("任务进度管理 - 单元测试")
    print("=" * 60)
    
    pytest.main([__file__, "-v", "-s"])
