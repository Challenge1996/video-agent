import uuid
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage


class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ConversationMessage:
    id: str
    role: MessageRole
    content: str
    timestamp: datetime
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    todo_list: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['role'] = self.role.value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationMessage':
        data = data.copy()
        data['role'] = MessageRole(data['role'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

    def to_langchain_message(self) -> BaseMessage:
        if self.role == MessageRole.SYSTEM:
            return SystemMessage(content=self.content)
        elif self.role == MessageRole.USER:
            return HumanMessage(content=self.content)
        elif self.role == MessageRole.ASSISTANT:
            return AIMessage(
                content=self.content,
                tool_calls=self.tool_calls if self.tool_calls else []
            )
        elif self.role == MessageRole.TOOL:
            return ToolMessage(
                content=self.content,
                tool_call_id=self.tool_call_id or "",
                name=self.tool_name or ""
            )
        else:
            raise ValueError(f"不支持的消息角色: {self.role}")


@dataclass
class ConversationContext:
    video_path: Optional[str] = None
    text_content: Optional[str] = None
    background_music_path: Optional[str] = None
    stickers: Optional[List[Dict[str, Any]]] = None
    output_path: Optional[str] = None
    last_action: Optional[str] = None
    action_results: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationContext':
        return cls(**data)


@dataclass
class Conversation:
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[ConversationMessage]
    context: ConversationContext
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'id': self.id,
            'title': self.title,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'messages': [m.to_dict() for m in self.messages],
            'context': self.context.to_dict(),
            'metadata': self.metadata,
        }
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Conversation':
        data = data.copy()
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        data['messages'] = [ConversationMessage.from_dict(m) for m in data['messages']]
        data['context'] = ConversationContext.from_dict(data['context'])
        return cls(**data)

    def get_langchain_messages(self) -> List[BaseMessage]:
        return [m.to_langchain_message() for m in self.messages]

    def add_message(
        self,
        role: MessageRole,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_call_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        todo_list: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationMessage:
        message = ConversationMessage(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            timestamp=datetime.now(),
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            todo_list=todo_list,
            metadata=metadata,
        )
        self.messages.append(message)
        self.updated_at = datetime.now()
        return message

    def update_context(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self.context, key):
                setattr(self.context, key, value)
        self.updated_at = datetime.now()


class ConversationManager:
    def __init__(self):
        self._conversations: Dict[str, Conversation] = {}
        self._system_prompt: Optional[str] = None

    def set_system_prompt(self, prompt: str):
        self._system_prompt = prompt

    def create_conversation(
        self,
        title: str = "新对话",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Conversation:
        conversation_id = str(uuid.uuid4())
        now = datetime.now()
        
        conversation = Conversation(
            id=conversation_id,
            title=title,
            created_at=now,
            updated_at=now,
            messages=[],
            context=ConversationContext(),
            metadata=metadata,
        )
        
        if self._system_prompt:
            conversation.add_message(
                role=MessageRole.SYSTEM,
                content=self._system_prompt,
            )
        
        self._conversations[conversation_id] = conversation
        return conversation

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        return self._conversations.get(conversation_id)

    def get_all_conversations(self) -> List[Conversation]:
        return list(self._conversations.values())

    def delete_conversation(self, conversation_id: str) -> bool:
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            return True
        return False

    def add_user_message(
        self,
        conversation_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ConversationMessage]:
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None
        return conversation.add_message(
            role=MessageRole.USER,
            content=content,
            metadata=metadata,
        )

    def add_assistant_message(
        self,
        conversation_id: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        todo_list: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ConversationMessage]:
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None
        return conversation.add_message(
            role=MessageRole.ASSISTANT,
            content=content,
            tool_calls=tool_calls,
            todo_list=todo_list,
            metadata=metadata,
        )

    def add_tool_message(
        self,
        conversation_id: str,
        content: str,
        tool_call_id: str,
        tool_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ConversationMessage]:
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None
        return conversation.add_message(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            metadata=metadata,
        )

    def update_context(
        self,
        conversation_id: str,
        **kwargs,
    ) -> bool:
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return False
        conversation.update_context(**kwargs)
        return True

    def save_conversation(self, conversation_id: str, file_path: str):
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"对话不存在: {conversation_id}")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(conversation.to_dict(), f, ensure_ascii=False, indent=2)

    def load_conversation(self, file_path: str) -> Conversation:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        conversation = Conversation.from_dict(data)
        self._conversations[conversation.id] = conversation
        return conversation


_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager
