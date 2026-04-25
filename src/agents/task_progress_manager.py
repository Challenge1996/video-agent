import uuid
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime


class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TodoItem:
    id: str
    title: str
    status: TodoStatus = TodoStatus.PENDING
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value if isinstance(self.status, TodoStatus) else self.status,
            "error": self.error,
            "result": self.result,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TodoItem":
        status = data.get("status", TodoStatus.PENDING)
        if isinstance(status, str):
            status = TodoStatus(status)
        
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()
        
        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.now()
        
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", ""),
            status=status,
            error=data.get("error"),
            result=data.get("result"),
            created_at=created_at,
            updated_at=updated_at,
            metadata=data.get("metadata", {}),
        )


@dataclass
class TaskProgress:
    task_id: str
    message_id: Optional[str] = None
    conversation_id: Optional[str] = None
    title: str = ""
    todos: List[TodoItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_complete: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "title": self.title,
            "todos": [todo.to_dict() for todo in self.todos],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_complete": self.is_complete,
        }

    def get_completed_count(self) -> int:
        return sum(1 for todo in self.todos if todo.status == TodoStatus.COMPLETED)

    def get_total_count(self) -> int:
        return len(self.todos)

    def get_progress_percentage(self) -> float:
        total = self.get_total_count()
        if total == 0:
            return 0.0
        return (self.get_completed_count() / total) * 100

    def all_completed(self) -> bool:
        return all(todo.status in (TodoStatus.COMPLETED, TodoStatus.FAILED) for todo in self.todos)


ProgressCallback = Callable[[TaskProgress, TodoItem], None]


class TaskProgressManager:
    def __init__(self):
        self._tasks: Dict[str, TaskProgress] = {}
        self._callbacks: List[ProgressCallback] = []

    def register_callback(self, callback: ProgressCallback):
        self._callbacks.append(callback)

    def unregister_callback(self, callback: ProgressCallback):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_callbacks(self, task: TaskProgress, todo: TodoItem):
        for callback in self._callbacks:
            try:
                callback(task, todo)
            except Exception as e:
                print(f"Progress callback error: {e}")

    def create_task(
        self,
        title: str,
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> TaskProgress:
        task_id = str(uuid.uuid4())
        task = TaskProgress(
            task_id=task_id,
            title=title,
            conversation_id=conversation_id,
            message_id=message_id,
        )
        self._tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[TaskProgress]:
        return self._tasks.get(task_id)

    def add_todo(
        self,
        task_id: str,
        title: str,
        status: TodoStatus = TodoStatus.PENDING,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TodoItem:
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        todo = TodoItem(
            id=str(uuid.uuid4()),
            title=title,
            status=status,
            metadata=metadata or {},
        )
        task.todos.append(todo)
        task.updated_at = datetime.now()
        
        self._notify_callbacks(task, todo)
        return todo

    def update_todo_status(
        self,
        task_id: str,
        todo_id: str,
        status: TodoStatus,
        error: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> TodoItem:
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        todo = next((t for t in task.todos if t.id == todo_id), None)
        if not todo:
            raise ValueError(f"Todo item not found: {todo_id}")
        
        todo.status = status
        todo.updated_at = datetime.now()
        
        if error:
            todo.error = error
        if result:
            todo.result = result
        
        task.updated_at = datetime.now()
        
        if task.all_completed():
            task.is_complete = True
        
        self._notify_callbacks(task, todo)
        return todo

    def start_todo(self, task_id: str, todo_id: str) -> TodoItem:
        return self.update_todo_status(task_id, todo_id, TodoStatus.IN_PROGRESS)

    def complete_todo(self, task_id: str, todo_id: str, result: Optional[Dict[str, Any]] = None) -> TodoItem:
        return self.update_todo_status(task_id, todo_id, TodoStatus.COMPLETED, result=result)

    def fail_todo(self, task_id: str, todo_id: str, error: str) -> TodoItem:
        return self.update_todo_status(task_id, todo_id, TodoStatus.FAILED, error=error)

    def clear_task(self, task_id: str):
        if task_id in self._tasks:
            del self._tasks[task_id]

    def get_all_tasks(self) -> List[TaskProgress]:
        return list(self._tasks.values())


_task_progress_manager: Optional[TaskProgressManager] = None


def get_task_progress_manager() -> TaskProgressManager:
    global _task_progress_manager
    if _task_progress_manager is None:
        _task_progress_manager = TaskProgressManager()
    return _task_progress_manager


def create_task_progress_manager() -> TaskProgressManager:
    return get_task_progress_manager()
