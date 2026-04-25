import os
import sys
import asyncio
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.llm_service import (
    LLMProvider,
    LLMResponse,
    LLMConfig,
    LLMServiceFactory,
    OpenAIService,
    MiniMaxAnthropicService,
    get_default_llm_config,
    get_llm_service,
)

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
)


class TestMiniMaxLLMProvider:
    """MiniMax LLM 提供商测试"""

    def setup_method(self):
        LLMServiceFactory.clear_cache()

    def teardown_method(self):
        LLMServiceFactory.clear_cache()

    def test_llm_provider_enum_includes_minimax(self):
        """测试 LLMProvider 枚举包含 MINIMAX"""
        assert hasattr(LLMProvider, 'MINIMAX')
        assert LLMProvider.MINIMAX.value == "minimax"
        
        print(f"\n✓ LLMProvider 枚举包含 MINIMAX: {LLMProvider.MINIMAX.value}")

    def test_llm_config_has_group_id(self):
        """测试 LLMConfig 包含 group_id 字段"""
        config = LLMConfig(
            provider=LLMProvider.MINIMAX,
            model_name="MiniMax-M2.7",
            api_key="test_key",
            group_id="test_group",
            base_url="https://api.minimax.chat/v1",
        )
        
        assert config.group_id == "test_group"
        assert config.provider == LLMProvider.MINIMAX
        assert config.model_name == "MiniMax-M2.7"
        
        print(f"\n✓ LLMConfig 包含 group_id 字段: {config.group_id}")

    def test_default_llm_config_uses_minimax(self):
        """测试默认配置使用 MiniMax"""
        original_provider = os.environ.get('LLM_PROVIDER')
        
        try:
            os.environ['LLM_PROVIDER'] = 'minimax'
            
            config = get_default_llm_config()
            
            assert config.provider == LLMProvider.MINIMAX
            assert config.model_name == "MiniMax-M2.7"
            assert config.api_key == os.getenv("MINIMAX_API_KEY")
            assert config.group_id == os.getenv("MINIMAX_GROUP_ID")
            
            print(f"\n✓ 默认配置使用 MiniMax:")
            print(f"  - Provider: {config.provider.value}")
            print(f"  - Model: {config.model_name}")
            
        finally:
            if original_provider:
                os.environ['LLM_PROVIDER'] = original_provider
            else:
                os.environ.pop('LLM_PROVIDER', None)

    def test_llm_service_factory_creates_minimax_service(self):
        """测试 LLMServiceFactory 创建 MiniMax 服务"""
        config = LLMConfig(
            provider=LLMProvider.MINIMAX,
            model_name="MiniMax-M2.7",
            api_key="test_api_key",
            group_id="test_group_id",
        )
        
        service = LLMServiceFactory.create(config)
        
        assert isinstance(service, MiniMaxAnthropicService)
        assert service.config.provider == LLMProvider.MINIMAX
        
        print(f"\n✓ LLMServiceFactory 创建 MiniMax 服务成功")
        print(f"  - 服务类型: {type(service).__name__}")


class TestMiniMaxMessageConversion:
    """MiniMax 消息转换测试"""

    def setup_method(self):
        self.service = MiniMaxAnthropicService(
            LLMConfig(
                provider=LLMProvider.MINIMAX,
                model_name="MiniMax-M2.7",
                api_key="test_key",
            )
        )

    def test_convert_human_message(self):
        """测试转换用户消息"""
        messages = [
            HumanMessage(content="你好，这是测试消息")
        ]
        
        system_prompt, chat_messages = self.service._convert_messages_to_anthropic(messages)
        
        assert system_prompt is None
        assert len(chat_messages) == 1
        assert chat_messages[0]["role"] == "user"
        assert chat_messages[0]["content"][0]["type"] == "text"
        assert chat_messages[0]["content"][0]["text"] == "你好，这是测试消息"
        
        print(f"\n✓ 用户消息转换成功:")
        print(f"  - 角色: {chat_messages[0]['role']}")
        print(f"  - 内容: {chat_messages[0]['content'][0]['text']}")

    def test_convert_system_message(self):
        """测试转换系统消息"""
        messages = [
            SystemMessage(content="你是一个测试助手"),
            HumanMessage(content="你好"),
        ]
        
        system_prompt, chat_messages = self.service._convert_messages_to_anthropic(messages)
        
        assert system_prompt == "你是一个测试助手"
        assert len(chat_messages) == 1
        assert chat_messages[0]["role"] == "user"
        
        print(f"\n✓ 系统消息转换成功:")
        print(f"  - 系统提示: {system_prompt}")

    def test_convert_multiple_system_messages(self):
        """测试转换多个系统消息"""
        messages = [
            SystemMessage(content="第一个系统提示"),
            SystemMessage(content="第二个系统提示"),
            HumanMessage(content="用户消息"),
        ]
        
        system_prompt, chat_messages = self.service._convert_messages_to_anthropic(messages)
        
        assert "第一个系统提示" in system_prompt
        assert "第二个系统提示" in system_prompt
        assert len(chat_messages) == 1
        
        print(f"\n✓ 多个系统消息合并成功:")
        print(f"  - 合并后的提示: {system_prompt}")

    def test_convert_assistant_message(self):
        """测试转换助手消息"""
        messages = [
            HumanMessage(content="你好"),
            AIMessage(content="你好！我是测试助手"),
        ]
        
        system_prompt, chat_messages = self.service._convert_messages_to_anthropic(messages)
        
        assert len(chat_messages) == 2
        assert chat_messages[0]["role"] == "user"
        assert chat_messages[1]["role"] == "assistant"
        assert chat_messages[1]["content"][0]["text"] == "你好！我是测试助手"
        
        print(f"\n✓ 助手消息转换成功:")
        print(f"  - 消息数: {len(chat_messages)}")
        print(f"  - 助手内容: {chat_messages[1]['content'][0]['text']}")

    def test_convert_full_conversation(self):
        """测试转换完整对话"""
        messages = [
            SystemMessage(content="你是一个视频编辑助手"),
            HumanMessage(content="帮我查看视频信息"),
            AIMessage(content="好的，请提供视频路径"),
            HumanMessage(content="/path/to/video.mp4"),
        ]
        
        system_prompt, chat_messages = self.service._convert_messages_to_anthropic(messages)
        
        assert system_prompt == "你是一个视频编辑助手"
        assert len(chat_messages) == 3
        assert chat_messages[0]["role"] == "user"
        assert chat_messages[1]["role"] == "assistant"
        assert chat_messages[2]["role"] == "user"
        
        print(f"\n✓ 完整对话转换成功:")
        print(f"  - 系统提示: {system_prompt}")
        print(f"  - 消息数: {len(chat_messages)}")
        for i, msg in enumerate(chat_messages):
            print(f"  - 消息 {i+1}: {msg['role']} - {msg['content'][0]['text'][:30]}...")


class TestMiniMaxResponseParsing:
    """MiniMax 响应解析测试"""

    def setup_method(self):
        self.service = MiniMaxAnthropicService(
            LLMConfig(
                provider=LLMProvider.MINIMAX,
                model_name="MiniMax-M2.7",
                api_key="test_key",
            )
        )

    def test_parse_simple_text_response(self):
        """测试解析简单文本响应"""
        mock_response = Mock()
        mock_response.content = [
            Mock(type="text", text="这是测试回复内容")
        ]
        mock_response.stop_reason = "end_turn"
        
        llm_response = self.service._parse_anthropic_response(mock_response)
        
        assert llm_response.content == "这是测试回复内容"
        assert llm_response.finish_reason == "end_turn"
        assert llm_response.thinking is None
        
        print(f"\n✓ 简单文本响应解析成功:")
        print(f"  - 内容: {llm_response.content}")
        print(f"  - 完成原因: {llm_response.finish_reason}")

    def test_parse_thinking_response(self):
        """测试解析包含 thinking 的响应"""
        mock_response = Mock()
        mock_response.content = [
            Mock(type="thinking", thinking="我需要分析用户的问题..."),
            Mock(type="text", text="这是最终回复")
        ]
        mock_response.stop_reason = "end_turn"
        
        llm_response = self.service._parse_anthropic_response(mock_response)
        
        assert llm_response.thinking == "我需要分析用户的问题..."
        assert llm_response.content == "这是最终回复"
        
        print(f"\n✓ Thinking 响应解析成功:")
        print(f"  - Thinking: {llm_response.thinking}")
        print(f"  - 内容: {llm_response.content}")

    def test_parse_response_with_fallback(self):
        """测试解析备用属性的响应"""
        mock_response = Mock()
        mock_response.content = []
        mock_response.text = "备用文本内容"
        mock_response.thinking = "备用思考内容"
        mock_response.stop_reason = None
        
        llm_response = self.service._parse_anthropic_response(mock_response)
        
        assert llm_response.content == "备用文本内容"
        assert llm_response.thinking == "备用思考内容"
        
        print(f"\n✓ 备用属性响应解析成功:")
        print(f"  - 内容: {llm_response.content}")
        print(f"  - Thinking: {llm_response.thinking}")


class TestMiniMaxLiveAPI:
    """MiniMax 实时 API 测试（需要有效配置）"""

    @pytest.mark.asyncio
    async def test_live_api_call(self):
        """测试真实 MiniMax API 调用"""
        api_key = os.getenv("MINIMAX_API_KEY")
        group_id = os.getenv("MINIMAX_GROUP_ID")
        
        if not api_key or api_key == "your_minimax_api_key":
            pytest.skip("MINIMAX_API_KEY 未配置，跳过实时测试")
        
        print(f"\n" + "=" * 60)
        print("MiniMax 实时 API 测试")
        print("=" * 60)
        print(f"API Key: {api_key[:10]}...")
        print(f"Group ID: {group_id}")
        print(f"Model: {os.getenv('LLM_MODEL', 'MiniMax-M2.7')}")
        print("=" * 60)
        
        config = LLMConfig(
            provider=LLMProvider.MINIMAX,
            model_name=os.getenv("LLM_MODEL", "MiniMax-M2.7"),
            api_key=api_key,
            group_id=group_id,
            base_url=os.getenv("MINIMAX_LLM_BASE_URL", "https://api.minimax.chat/v1"),
            max_tokens=1000,
            temperature=0.7,
        )
        
        service = MiniMaxAnthropicService(config)
        
        messages = [
            SystemMessage(content="你是一个友好的助手，请用中文回答问题。"),
            HumanMessage(content="你好，请简单介绍一下你自己。"),
        ]
        
        print(f"\n发送消息: {messages[-1].content}")
        print("\n等待响应...\n")
        
        try:
            response = await service.chat(messages)
            
            print("=" * 60)
            print("API 响应结果:")
            print("=" * 60)
            
            if response.thinking:
                print(f"\nThinking:")
                print(f"{response.thinking}")
            
            print(f"\nResponse:")
            print(f"{response.content}")
            print(f"\nFinish Reason: {response.finish_reason}")
            print("=" * 60)
            
            assert response.content is not None
            assert len(response.content) > 0
            
            print("\n✓ MiniMax 实时 API 调用成功！")
            
        except Exception as e:
            print(f"\n✗ MiniMax API 调用失败: {str(e)}")
            raise


def run_manual_test():
    """手动运行测试"""
    print("\n" + "=" * 60)
    print("MiniMax LLM 集成测试")
    print("=" * 60)
    
    api_key = os.getenv("MINIMAX_API_KEY")
    group_id = os.getenv("MINIMAX_GROUP_ID")
    
    print(f"\n当前配置:")
    print(f"  - LLM_PROVIDER: {os.getenv('LLM_PROVIDER', 'minimax')}")
    print(f"  - LLM_MODEL: {os.getenv('LLM_MODEL', 'MiniMax-M2.7')}")
    print(f"  - MINIMAX_API_KEY: {'已配置' if api_key and api_key != 'your_minimax_api_key' else '未配置'}")
    print(f"  - MINIMAX_GROUP_ID: {group_id}")
    
    if not api_key or api_key == "your_minimax_api_key":
        print(f"\n⚠️  提示: 请配置 .env 文件中的 MINIMAX_API_KEY 和 MINIMAX_GROUP_ID")
        print(f"   配置后可以运行实时 API 测试。")
        return
    
    print(f"\n" + "=" * 60)
    print("运行单元测试...")
    print("=" * 60)
    
    pytest.main([
        __file__,
        "-v",
        "-s",
        "-k", "not test_live_api"
    ])
    
    print(f"\n" + "=" * 60)
    print("运行实时 API 测试...")
    print("=" * 60)
    
    async def run_async_test():
        config = LLMConfig(
            provider=LLMProvider.MINIMAX,
            model_name=os.getenv("LLM_MODEL", "MiniMax-M2.7"),
            api_key=api_key,
            group_id=group_id,
            base_url=os.getenv("MINIMAX_LLM_BASE_URL", "https://api.minimax.chat/v1"),
            max_tokens=1000,
            temperature=0.7,
        )
        
        service = MiniMaxAnthropicService(config)
        
        messages = [
            SystemMessage(content="你是一个视频编辑助手，擅长帮助用户完成视频剪辑任务。请用中文回答。"),
            HumanMessage(content="你好，请简单介绍一下你能帮我做什么。"),
        ]
        
        print(f"\n发送消息: {messages[-1].content}")
        print("\n等待响应...\n")
        
        try:
            response = await service.chat(messages)
            
            print("=" * 60)
            print("API 响应结果:")
            print("=" * 60)
            
            if response.thinking:
                print(f"\nThinking:")
                print(f"{response.thinking}")
            
            print(f"\nResponse:")
            print(f"{response.content}")
            print("=" * 60)
            
            print("\n✓ MiniMax 实时 API 调用成功！")
            
        except Exception as e:
            print(f"\n✗ MiniMax API 调用失败: {str(e)}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(run_async_test())


if __name__ == "__main__":
    run_manual_test()
