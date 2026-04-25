import os
import json
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from src.config.config import config


class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MINIMAX = "minimax"
    CUSTOM = "custom"


@dataclass
class LLMResponse:
    content: str
    raw_response: Any = None
    tool_calls: List[Dict[str, Any]] = None
    finish_reason: str = None
    thinking: Optional[str] = None


@dataclass
class LLMConfig:
    provider: LLMProvider = LLMProvider.OPENAI
    model_name: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 4096
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    group_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class LLMService(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: List[BaseMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        pass

    @abstractmethod
    def get_model(self) -> Any:
        pass


BaseLLMService = LLMService


class OpenAIService(BaseLLMService):
    def __init__(self, config: LLMConfig):
        self.config = config
        self._model: Optional[BaseChatModel] = None

    def get_model(self) -> BaseChatModel:
        if self._model is None:
            from langchain_openai import ChatOpenAI
            
            api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY 环境变量未设置")
            
            self._model = ChatOpenAI(
                model=self.config.model_name,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                api_key=api_key,
                base_url=self.config.base_url or os.getenv("OPENAI_BASE_URL"),
            )
        return self._model

    async def chat(
        self,
        messages: List[BaseMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        model = self.get_model()
        
        if tools:
            model_with_tools = model.bind_tools(tools)
            response = await model_with_tools.ainvoke(messages)
        else:
            response = await model.ainvoke(messages)
        
        tool_calls = []
        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_calls = response.tool_calls
        
        finish_reason = None
        if hasattr(response, 'response_metadata'):
            finish_reason = response.response_metadata.get('finish_reason')
        
        return LLMResponse(
            content=response.content,
            raw_response=response,
            tool_calls=tool_calls,
            finish_reason=finish_reason
        )


class MiniMaxAnthropicService(BaseLLMService):
    """
    MiniMax LLM 服务，使用 Anthropic 兼容 API。
    
    MiniMax 提供了兼容 Anthropic 的 API 接口，支持 thinking 思考模式。
    """
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._client: Optional[Any] = None
        self._anthropic = None

    def _get_anthropic(self):
        if self._anthropic is None:
            try:
                import anthropic
                self._anthropic = anthropic
            except ImportError:
                raise ImportError(
                    "请安装 anthropic 库: pip install anthropic"
                )
        return self._anthropic

    def get_model(self) -> Any:
        if self._client is None:
            anthropic = self._get_anthropic()
            
            api_key = self.config.api_key or os.getenv("MINIMAX_API_KEY")
            if not api_key:
                raise ValueError("MINIMAX_API_KEY 环境变量未设置")
            
            base_url = self.config.base_url or os.getenv(
                "MINIMAX_LLM_BASE_URL", 
                "https://api.minimaxi.com/anthropic"
            )
            
            group_id = self.config.group_id or os.getenv("MINIMAX_GROUP_ID")
            
            if group_id and "minimax.chat" in base_url:
                if '?' in base_url:
                    base_url = f"{base_url}&GroupId={group_id}"
                else:
                    base_url = f"{base_url}?GroupId={group_id}"
            
            self._client = anthropic.Anthropic(
                api_key=api_key,
                base_url=base_url,
            )
        
        return self._client

    def _convert_messages_to_anthropic(
        self,
        messages: List[BaseMessage]
    ) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """
        将 LangChain 消息转换为 Anthropic 格式。
        
        Anthropic API 的格式要求：
        1. system 消息通过单独的 system 参数传递
        2. 用户和助手消息交替出现
        3. 必须以用户消息开头
        """
        system_prompt = None
        chat_messages: List[Dict[str, Any]] = []
        
        for msg in messages:
            if isinstance(msg, SystemMessage):
                if system_prompt is None:
                    system_prompt = msg.content
                else:
                    system_prompt += "\n\n" + msg.content
            elif isinstance(msg, HumanMessage):
                chat_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": msg.content
                        }
                    ]
                })
            elif isinstance(msg, AIMessage):
                content = msg.content
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    pass
                
                chat_messages.append({
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": content
                        }
                    ]
                })
            else:
                chat_messages.append({
                    "role": "user" if msg.type == "human" else "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": msg.content
                        }
                    ]
                })
        
        return system_prompt, chat_messages

    def _parse_anthropic_response(self, response: Any) -> LLMResponse:
        """
        解析 Anthropic 响应，支持 thinking 模式。
        
        响应格式示例：
        {
            "thinking": "思考过程...",
            "text": "最终文本..."
        }
        """
        thinking: Optional[str] = None
        content = ""
        
        if hasattr(response, 'content') and response.content:
            for block in response.content:
                if hasattr(block, 'type'):
                    block_type = block.type
                    if block_type == "thinking":
                        thinking_value = getattr(block, 'thinking', None)
                        if thinking_value and isinstance(thinking_value, str):
                            thinking = thinking_value
                    elif block_type == "text":
                        text_value = getattr(block, 'text', "")
                        if text_value and isinstance(text_value, str):
                            content += text_value
        
        if not content:
            text_attr = getattr(response, 'text', None)
            if text_attr and isinstance(text_attr, str):
                content = text_attr
        
        if not thinking:
            thinking_attr = getattr(response, 'thinking', None)
            if thinking_attr and isinstance(thinking_attr, str):
                thinking = thinking_attr
        
        finish_reason = None
        stop_reason = getattr(response, 'stop_reason', None)
        if stop_reason and isinstance(stop_reason, str):
            finish_reason = stop_reason
        
        return LLMResponse(
            content=content,
            raw_response=response,
            finish_reason=finish_reason,
            thinking=thinking,
            tool_calls=[],
        )

    async def chat(
        self,
        messages: List[BaseMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        client = self.get_model()
        
        system_prompt, chat_messages = self._convert_messages_to_anthropic(messages)
        
        create_kwargs = {
            "model": self.config.model_name,
            "max_tokens": self.config.max_tokens,
            "messages": chat_messages,
        }
        
        if system_prompt:
            create_kwargs["system"] = system_prompt
        
        if hasattr(self.config, 'temperature') and self.config.temperature is not None:
            create_kwargs["temperature"] = self.config.temperature
        
        if tools:
            pass
        
        try:
            response = client.messages.create(**create_kwargs)
            return self._parse_anthropic_response(response)
        except Exception as e:
            raise Exception(f"MiniMax API 调用失败: {str(e)}")


class LLMServiceFactory:
    _instances: Dict[str, BaseLLMService] = {}

    @classmethod
    def create(cls, config: LLMConfig) -> BaseLLMService:
        key = f"{config.provider.value}_{config.model_name}"
        
        if key not in cls._instances:
            if config.provider == LLMProvider.OPENAI:
                cls._instances[key] = OpenAIService(config)
            elif config.provider == LLMProvider.MINIMAX:
                cls._instances[key] = MiniMaxAnthropicService(config)
            elif config.provider == LLMProvider.ANTHROPIC:
                cls._instances[key] = MiniMaxAnthropicService(config)
            else:
                raise ValueError(f"不支持的 LLM 提供商: {config.provider}")
        
        return cls._instances[key]

    @classmethod
    def clear_cache(cls):
        cls._instances.clear()


def get_default_llm_config() -> LLMConfig:
    provider_str = os.getenv("LLM_PROVIDER", "minimax").lower()
    
    if provider_str == "openai":
        provider = LLMProvider.OPENAI
    elif provider_str == "anthropic":
        provider = LLMProvider.ANTHROPIC
    elif provider_str == "minimax":
        provider = LLMProvider.MINIMAX
    else:
        provider = LLMProvider.MINIMAX
    
    if provider == LLMProvider.MINIMAX:
        return LLMConfig(
            provider=provider,
            model_name=os.getenv("LLM_MODEL", "MiniMax-M2.7"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            api_key=os.getenv("MINIMAX_API_KEY"),
            base_url=os.getenv("MINIMAX_LLM_BASE_URL"),
            group_id=os.getenv("MINIMAX_GROUP_ID"),
        )
    else:
        return LLMConfig(
            provider=provider,
            model_name=os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
        )


def get_llm_service() -> BaseLLMService:
    config = get_default_llm_config()
    return LLMServiceFactory.create(config)
