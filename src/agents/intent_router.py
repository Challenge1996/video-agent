import os
import json
import asyncio
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool as langchain_tool

from src.agents.llm_service import (
    LLMService,
    get_llm_service,
    LLMResponse,
)
from src.agents.conversation_manager import (
    ConversationManager,
    get_conversation_manager,
    Conversation,
)
from src.config.config import config


class IntentType(Enum):
    VIDEO_INFO = "video_info"
    SPLIT_VIDEO = "split_video"
    MERGE_VIDEOS = "merge_videos"
    GENERATE_TTS = "generate_tts"
    GENERATE_SUBTITLES = "generate_subtitles"
    ADD_BACKGROUND_MUSIC = "add_background_music"
    ADD_STICKER = "add_sticker"
    COMPOSE_VIDEO = "compose_video"
    AUDIO_INFO = "audio_info"
    CONVERSATION = "conversation"
    CLARIFICATION = "clarification"
    UNKNOWN = "unknown"


@dataclass
class IntentResult:
    intent: IntentType
    confidence: float
    parameters: Dict[str, Any]
    reasoning: str
    suggested_actions: List[str]


@dataclass
class ToolExecutionResult:
    success: bool
    tool_name: str
    result: Any
    error: Optional[str] = None
    execution_time: Optional[float] = None


class IntentRouter:
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        conversation_manager: Optional[ConversationManager] = None,
    ):
        self.llm_service = llm_service or get_llm_service()
        self.conversation_manager = conversation_manager or get_conversation_manager()
        self._registered_tools: Dict[str, Callable] = {}

    def register_tool(self, name: str, tool_func: Callable):
        self._registered_tools[name] = tool_func

    def get_registered_tools(self) -> Dict[str, Callable]:
        return self._registered_tools.copy()

    async def recognize_intent(
        self,
        user_input: str,
        conversation: Optional[Conversation] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> IntentResult:
        context_info = self._build_context_info(context, conversation)
        
        system_prompt = f"""你是一个专业的视频编辑助手。你的任务是分析用户的输入，识别用户的意图，并提取必要的参数。

可用的意图类型：
- video_info: 获取视频信息
- split_video: 分割视频
- merge_videos: 合并视频
- generate_tts: 生成语音（TTS）
- generate_subtitles: 生成字幕
- add_background_music: 添加背景音乐
- add_sticker: 添加贴纸
- compose_video: 一键合成视频（推荐，可同时添加TTS、字幕、背景音乐、贴纸）
- audio_info: 获取音频信息
- conversation: 一般性对话，不需要执行操作
- clarification: 需要用户澄清更多信息
- unknown: 无法识别的意图

当前上下文信息：
{context_info}

请分析用户输入，并以 JSON 格式返回结果，格式如下：
{{
    "intent": "意图类型",
    "confidence": 0.0-1.0,
    "parameters": {{"key": "value"}},
    "reasoning": "简要说明识别理由",
    "suggested_actions": ["建议的操作步骤"]
}}

注意：
1. compose_video 是最强大的工具，可以一次性完成多项操作，优先考虑
2. 如果用户意图不明确或缺少必要参数，返回 clarification 意图
3. 如果是一般性问候或聊天，返回 conversation 意图
4. confidence 表示对识别结果的信心程度，0.9 表示非常确定，0.5 表示不确定"""

        messages = [
            HumanMessage(content=system_prompt),
            HumanMessage(content=f"用户输入：{user_input}")
        ]
        
        if conversation:
            messages = conversation.get_langchain_messages() + [
                HumanMessage(content=f"用户输入：{user_input}")
            ]
        
        response = await self.llm_service.chat(messages)
        
        try:
            json_start = response.content.find('{')
            json_end = response.content.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response.content[json_start:json_end]
                result = json.loads(json_str)
                
                intent_str = result.get('intent', 'unknown')
                try:
                    intent = IntentType(intent_str)
                except ValueError:
                    intent = IntentType.UNKNOWN
                
                return IntentResult(
                    intent=intent,
                    confidence=float(result.get('confidence', 0.5)),
                    parameters=result.get('parameters', {}),
                    reasoning=result.get('reasoning', ''),
                    suggested_actions=result.get('suggested_actions', []),
                )
        except json.JSONDecodeError:
            pass
        
        return IntentResult(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            parameters={},
            reasoning="无法解析 LLM 响应",
            suggested_actions=[],
        )

    def _build_context_info(
        self,
        context: Optional[Dict[str, Any]] = None,
        conversation: Optional[Conversation] = None,
    ) -> str:
        info_parts = []
        
        if conversation and conversation.context:
            ctx = conversation.context
            if ctx.video_path:
                info_parts.append(f"- 当前视频: {ctx.video_path}")
            if ctx.text_content:
                info_parts.append(f"- 文本内容: {ctx.text_content[:100]}...")
            if ctx.background_music_path:
                info_parts.append(f"- 背景音乐: {ctx.background_music_path}")
            if ctx.output_path:
                info_parts.append(f"- 输出路径: {ctx.output_path}")
            if ctx.last_action:
                info_parts.append(f"- 上次操作: {ctx.last_action}")
        
        if context:
            for key, value in context.items():
                info_parts.append(f"- {key}: {value}")
        
        if info_parts:
            return "\n".join(info_parts)
        return "无可用上下文"


class ToolExecutor:
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
    ):
        self.llm_service = llm_service or get_llm_service()
        self._registered_tools: Dict[str, Callable] = {}

    def register_tool(self, name: str, tool_func: Callable):
        self._registered_tools[name] = tool_func

    def get_registered_tools(self) -> Dict[str, Callable]:
        return self._registered_tools.copy()

    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
    ) -> ToolExecutionResult:
        import time
        
        if tool_name not in self._registered_tools:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                result=None,
                error=f"工具 '{tool_name}' 未注册",
            )
        
        tool_func = self._registered_tools[tool_name]
        start_time = time.time()
        
        try:
            if hasattr(tool_func, 'ainvoke'):
                result = await tool_func.ainvoke(parameters)
            elif hasattr(tool_func, 'invoke'):
                result = tool_func.invoke(parameters)
            elif asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**parameters)
            else:
                result = tool_func(**parameters)
            
            execution_time = time.time() - start_time
            
            return ToolExecutionResult(
                success=True,
                tool_name=tool_name,
                result=result,
                execution_time=execution_time,
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                result=None,
                error=str(e),
                execution_time=execution_time,
            )

    async def execute_tools_sequence(
        self,
        tools_sequence: List[Dict[str, Any]],
    ) -> List[ToolExecutionResult]:
        results = []
        for tool_info in tools_sequence:
            result = await self.execute_tool(
                tool_name=tool_info['name'],
                parameters=tool_info.get('parameters', {}),
            )
            results.append(result)
            
            if not result.success and tool_info.get('stop_on_error', True):
                break
        
        return results


_intent_router: Optional[IntentRouter] = None
_tool_executor: Optional[ToolExecutor] = None


def get_intent_router() -> IntentRouter:
    global _intent_router
    if _intent_router is None:
        _intent_router = IntentRouter()
    return _intent_router


def get_tool_executor() -> ToolExecutor:
    global _tool_executor
    if _tool_executor is None:
        _tool_executor = ToolExecutor()
    return _tool_executor
