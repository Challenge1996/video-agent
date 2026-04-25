import os
import sys
import json
import tempfile
import shutil
import pytest
import asyncio
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, List

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.conversation_manager import (
    ConversationManager,
    Conversation,
    ConversationMessage,
    ConversationContext,
    MessageRole,
)

from src.agents.llm_service import (
    LLMProvider,
    LLMResponse,
    LLMConfig,
    OpenAIService,
    LLMServiceFactory,
    get_default_llm_config,
)

from src.agents.intent_router import (
    IntentType,
    IntentResult,
    ToolExecutionResult,
)

from src.agents.video_editor_agent import (
    SmartVideoEditorAgent,
    ChatResponse,
    tools,
)


class TestConversationManager:
    """对话管理器测试"""

    def setup_method(self):
        self.manager = ConversationManager()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_conversation(self):
        """测试创建对话"""
        conversation = self.manager.create_conversation(title="测试对话")
        
        assert conversation.id is not None
        assert conversation.title == "测试对话"
        assert len(conversation.messages) == 0
        assert isinstance(conversation.context, ConversationContext)
        
        print(f"\n✓ 对话创建成功:")
        print(f"  - ID: {conversation.id}")
        print(f"  - 标题: {conversation.title}")

    def test_create_conversation_with_system_prompt(self):
        """测试创建带系统提示的对话"""
        self.manager.set_system_prompt("你是一个测试助手")
        conversation = self.manager.create_conversation(title="测试对话")
        
        assert len(conversation.messages) == 1
        assert conversation.messages[0].role == MessageRole.SYSTEM
        assert conversation.messages[0].content == "你是一个测试助手"
        
        print(f"\n✓ 系统提示设置成功:")
        print(f"  - 提示内容: {conversation.messages[0].content}")

    def test_add_user_message(self):
        """测试添加用户消息"""
        conv_id = self.manager.create_conversation().id
        message = self.manager.add_user_message(conv_id, "你好，这是测试消息")
        
        assert message is not None
        assert message.role == MessageRole.USER
        assert message.content == "你好，这是测试消息"
        
        conversation = self.manager.get_conversation(conv_id)
        assert len(conversation.messages) == 1
        
        print(f"\n✓ 用户消息添加成功:")
        print(f"  - 内容: {message.content}")
        print(f"  - 角色: {message.role.value}")

    def test_add_assistant_message(self):
        """测试添加助手消息"""
        conv_id = self.manager.create_conversation().id
        message = self.manager.add_assistant_message(conv_id, "我是测试助手")
        
        assert message is not None
        assert message.role == MessageRole.ASSISTANT
        assert message.content == "我是测试助手"
        
        print(f"\n✓ 助手消息添加成功:")
        print(f"  - 内容: {message.content}")

    def test_add_tool_message(self):
        """测试添加工具消息"""
        conv_id = self.manager.create_conversation().id
        message = self.manager.add_tool_message(
            conv_id,
            content='{"result": "success"}',
            tool_call_id="test_call_123",
            tool_name="get_video_info_tool",
        )
        
        assert message is not None
        assert message.role == MessageRole.TOOL
        assert message.tool_call_id == "test_call_123"
        assert message.tool_name == "get_video_info_tool"
        
        print(f"\n✓ 工具消息添加成功:")
        print(f"  - 工具名称: {message.tool_name}")
        print(f"  - 调用ID: {message.tool_call_id}")

    def test_get_all_conversations(self):
        """测试获取所有对话"""
        self.manager.create_conversation(title="对话1")
        self.manager.create_conversation(title="对话2")
        
        conversations = self.manager.get_all_conversations()
        assert len(conversations) == 2
        
        print(f"\n✓ 获取所有对话成功:")
        print(f"  - 对话数量: {len(conversations)}")

    def test_delete_conversation(self):
        """测试删除对话"""
        conversation = self.manager.create_conversation(title="待删除对话")
        conv_id = conversation.id
        
        assert self.manager.get_conversation(conv_id) is not None
        
        result = self.manager.delete_conversation(conv_id)
        assert result is True
        assert self.manager.get_conversation(conv_id) is None
        
        print(f"\n✓ 对话删除成功:")
        print(f"  - 已删除ID: {conv_id}")

    def test_update_context(self):
        """测试更新上下文"""
        conv_id = self.manager.create_conversation().id
        
        self.manager.update_context(
            conv_id,
            video_path="/path/to/video.mp4",
            text_content="这是测试文本",
            last_action="get_video_info",
        )
        
        conversation = self.manager.get_conversation(conv_id)
        assert conversation.context.video_path == "/path/to/video.mp4"
        assert conversation.context.text_content == "这是测试文本"
        assert conversation.context.last_action == "get_video_info"
        
        print(f"\n✓ 上下文更新成功:")
        print(f"  - 视频路径: {conversation.context.video_path}")
        print(f"  - 文本内容: {conversation.context.text_content}")

    def test_save_and_load_conversation(self):
        """测试保存和加载对话"""
        conversation = self.manager.create_conversation(title="测试保存")
        self.manager.add_user_message(conversation.id, "测试消息1")
        self.manager.add_assistant_message(conversation.id, "测试回复1")
        
        save_path = os.path.join(self.temp_dir, "test_conversation.json")
        self.manager.save_conversation(conversation.id, save_path)
        
        assert os.path.exists(save_path)
        
        self.manager._conversations = {}
        loaded_conv = self.manager.load_conversation(save_path)
        
        assert loaded_conv.id == conversation.id
        assert loaded_conv.title == "测试保存"
        assert len(loaded_conv.messages) == 2
        
        print(f"\n✓ 对话保存和加载成功:")
        print(f"  - 保存路径: {save_path}")
        print(f"  - 消息数量: {len(loaded_conv.messages)}")

    def test_message_to_langchain_conversion(self):
        """测试消息转换为 LangChain 消息"""
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
        
        self.manager.set_system_prompt("系统提示")
        conversation = self.manager.create_conversation()
        conv_id = conversation.id
        
        self.manager.add_user_message(conv_id, "用户消息")
        self.manager.add_assistant_message(conv_id, "助手回复")
        
        langchain_messages = conversation.get_langchain_messages()
        
        assert len(langchain_messages) == 3
        assert isinstance(langchain_messages[0], SystemMessage)
        assert isinstance(langchain_messages[1], HumanMessage)
        assert isinstance(langchain_messages[2], AIMessage)
        
        print(f"\n✓ 消息转换成功:")
        print(f"  - 转换后数量: {len(langchain_messages)}")
        print(f"  - 消息类型: {[type(m).__name__ for m in langchain_messages]}")


class TestLLMService:
    """LLM 服务测试"""

    def test_get_default_config(self):
        """测试获取默认配置"""
        config = get_default_llm_config()
        
        assert config.provider in [LLMProvider.OPENAI, LLMProvider.ANTHROPIC, LLMProvider.MINIMAX]
        assert config.temperature >= 0.0
        assert config.temperature <= 2.0
        assert config.max_tokens > 0
        
        print(f"\n✓ 默认配置获取成功:")
        print(f"  - 提供商: {config.provider.value}")
        print(f"  - 模型: {config.model_name}")
        print(f"  - 温度: {config.temperature}")

    def test_llm_config_creation(self):
        """测试 LLM 配置创建"""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model_name="gpt-4",
            temperature=0.5,
            max_tokens=2048,
            api_key="test_key",
        )
        
        assert config.provider == LLMProvider.OPENAI
        assert config.model_name == "gpt-4"
        assert config.temperature == 0.5
        assert config.max_tokens == 2048
        
        print(f"\n✓ LLM 配置创建成功:")
        print(f"  - 模型: {config.model_name}")

    def test_llm_provider_enum(self):
        """测试 LLM 提供商枚举"""
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.ANTHROPIC.value == "anthropic"
        assert LLMProvider.CUSTOM.value == "custom"
        
        print(f"\n✓ LLM 提供商枚举验证成功:")
        print(f"  - OPENAI: {LLMProvider.OPENAI.value}")
        print(f"  - ANTHROPIC: {LLMProvider.ANTHROPIC.value}")

    def test_llm_response_creation(self):
        """测试 LLM 响应创建"""
        response = LLMResponse(
            content="这是测试回复",
            tool_calls=[
                {
                    "id": "test_123",
                    "name": "get_video_info",
                    "args": {"video_path": "/path/to/video.mp4"}
                }
            ],
            finish_reason="tool_calls",
        )
        
        assert response.content == "这是测试回复"
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["name"] == "get_video_info"
        assert response.finish_reason == "tool_calls"
        
        print(f"\n✓ LLM 响应创建成功:")
        print(f"  - 内容: {response.content}")
        print(f"  - 工具调用数量: {len(response.tool_calls)}")


class TestIntentRouter:
    """意图识别器测试"""

    def test_intent_type_enum(self):
        """测试意图类型枚举"""
        intent_types = [
            IntentType.VIDEO_INFO,
            IntentType.SPLIT_VIDEO,
            IntentType.MERGE_VIDEOS,
            IntentType.GENERATE_TTS,
            IntentType.GENERATE_SUBTITLES,
            IntentType.ADD_BACKGROUND_MUSIC,
            IntentType.ADD_STICKER,
            IntentType.COMPOSE_VIDEO,
            IntentType.AUDIO_INFO,
            IntentType.CONVERSATION,
            IntentType.CLARIFICATION,
            IntentType.UNKNOWN,
        ]
        
        for intent in intent_types:
            assert isinstance(intent.value, str)
        
        print(f"\n✓ 意图类型枚举验证成功:")
        print(f"  - 意图数量: {len(intent_types)}")
        for intent in intent_types:
            print(f"    - {intent.name}: {intent.value}")

    def test_intent_result_creation(self):
        """测试意图结果创建"""
        result = IntentResult(
            intent=IntentType.COMPOSE_VIDEO,
            confidence=0.95,
            parameters={
                "video_path": "/path/to/video.mp4",
                "text_content": "解说文本",
            },
            reasoning="用户想要合成视频，包含TTS语音和背景音乐",
            suggested_actions=["使用 compose_video_tool 一键合成"],
        )
        
        assert result.intent == IntentType.COMPOSE_VIDEO
        assert result.confidence == 0.95
        assert result.parameters["video_path"] == "/path/to/video.mp4"
        assert len(result.suggested_actions) == 1
        
        print(f"\n✓ 意图结果创建成功:")
        print(f"  - 意图类型: {result.intent.value}")
        print(f"  - 置信度: {result.confidence}")
        print(f"  - 推理: {result.reasoning}")

    def test_tool_execution_result_success(self):
        """测试工具执行结果（成功）"""
        result = ToolExecutionResult(
            success=True,
            tool_name="get_video_info_tool",
            result={
                "duration": 60.5,
                "resolution": "1920x1080",
                "fps": 30,
            },
            execution_time=0.15,
        )
        
        assert result.success is True
        assert result.tool_name == "get_video_info_tool"
        assert result.result["duration"] == 60.5
        assert result.execution_time == 0.15
        assert result.error is None
        
        print(f"\n✓ 工具执行结果（成功）创建成功:")
        print(f"  - 工具名称: {result.tool_name}")
        print(f"  - 执行时间: {result.execution_time}s")
        print(f"  - 结果: {result.result}")

    def test_tool_execution_result_error(self):
        """测试工具执行结果（失败）"""
        result = ToolExecutionResult(
            success=False,
            tool_name="split_video_tool",
            result=None,
            error="视频文件不存在: /path/to/nonexistent.mp4",
            execution_time=0.05,
        )
        
        assert result.success is False
        assert result.tool_name == "split_video_tool"
        assert result.result is None
        assert "视频文件不存在" in result.error
        
        print(f"\n✓ 工具执行结果（失败）创建成功:")
        print(f"  - 工具名称: {result.tool_name}")
        print(f"  - 错误信息: {result.error}")


class TestVideoEditorTools:
    """视频编辑工具测试"""

    def test_tools_list(self):
        """测试工具列表"""
        expected_tools = [
            "split_video_tool",
            "get_video_info_tool",
            "generate_tts_tool",
            "generate_subtitles_tool",
            "add_background_music_tool",
            "add_sticker_tool",
            "compose_video_tool",
            "merge_videos_tool",
            "get_audio_info_tool",
        ]
        
        tool_names = [tool.name for tool in tools]
        
        for expected_name in expected_tools:
            assert expected_name in tool_names
        
        print(f"\n✓ 工具列表验证成功:")
        print(f"  - 工具数量: {len(tools)}")
        for tool in tools:
            print(f"    - {tool.name}")

    def test_tool_descriptions(self):
        """测试工具描述"""
        for tool in tools:
            assert tool.description is not None
            assert len(tool.description) > 0
        
        print(f"\n✓ 工具描述验证成功:")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description[:50]}...")


class TestChatResponse:
    """聊天响应测试"""

    def test_chat_response_creation(self):
        """测试聊天响应创建"""
        response = ChatResponse(
            content="这是助手的回复",
            tool_calls=[
                {
                    "name": "get_video_info_tool",
                    "args": {"video_path": "/test.mp4"},
                }
            ],
            tool_results=[
                {
                    "tool_name": "get_video_info_tool",
                    "success": True,
                    "result": {"duration": 60},
                }
            ],
            conversation_id="test_conv_123",
            is_complete=True,
        )
        
        assert response.content == "这是助手的回复"
        assert len(response.tool_calls) == 1
        assert len(response.tool_results) == 1
        assert response.conversation_id == "test_conv_123"
        assert response.is_complete is True
        
        print(f"\n✓ 聊天响应创建成功:")
        print(f"  - 内容: {response.content}")
        print(f"  - 对话ID: {response.conversation_id}")
        print(f"  - 工具调用数: {len(response.tool_calls)}")
        print(f"  - 工具结果数: {len(response.tool_results)}")


if __name__ == "__main__":
    print("=" * 60)
    print("视频剪辑 Agent - 单元测试")
    print("=" * 60)
    
    pytest.main([__file__, "-v", "-s"])
