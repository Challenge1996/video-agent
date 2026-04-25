import os
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config.config import config


class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"


@dataclass
class LLMResponse:
    content: str
    raw_response: Any = None
    tool_calls: List[Dict[str, Any]] = None
    finish_reason: str = None


@dataclass
class LLMConfig:
    provider: LLMProvider = LLMProvider.OPENAI
    model_name: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 4096
    api_key: Optional[str] = None
    base_url: Optional[str] = None


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
    def get_model(self) -> BaseChatModel:
        pass


BaseLLMService = LLMService


class OpenAIService(BaseLLMService):
    def __init__(self, config: LLMConfig):
        self.config = config
        self._model: Optional[ChatOpenAI] = None

    def get_model(self) -> ChatOpenAI:
        if self._model is None:
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


class LLMServiceFactory:
    _instances: Dict[str, BaseLLMService] = {}

    @classmethod
    def create(cls, config: LLMConfig) -> BaseLLMService:
        key = f"{config.provider.value}_{config.model_name}"
        
        if key not in cls._instances:
            if config.provider == LLMProvider.OPENAI:
                cls._instances[key] = OpenAIService(config)
            else:
                raise ValueError(f"不支持的 LLM 提供商: {config.provider}")
        
        return cls._instances[key]


def get_default_llm_config() -> LLMConfig:
    provider_str = os.getenv("LLM_PROVIDER", "openai").lower()
    
    if provider_str == "openai":
        provider = LLMProvider.OPENAI
    elif provider_str == "anthropic":
        provider = LLMProvider.ANTHROPIC
    else:
        provider = LLMProvider.OPENAI
    
    return LLMConfig(
        provider=provider,
        model_name=os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
    )


def get_llm_service() -> BaseLLMService:
    config = get_default_llm_config()
    return LLMServiceFactory.create(config)
