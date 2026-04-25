import os
import json
import asyncio
from typing import List, Dict, Any, Optional, TypedDict, Annotated
from dataclasses import dataclass, asdict
from pathlib import Path
import operator

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool as langchain_tool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage

from src.config.config import config
from src.utils.helpers import helpers
from src.modules.video_splitter import VideoSplitter
from src.modules.tts_service import TTSService
from src.modules.minimax_tts_service import MiniMaxTTSService
from src.modules.subtitle_generator import SubtitleGenerator
from src.modules.background_music import BackgroundMusicService
from src.modules.sticker_service import StickerService
from src.modules.video_composer import VideoComposer

from src.agents.llm_service import (
    LLMService,
    get_llm_service,
    LLMResponse,
)
from src.agents.conversation_manager import (
    ConversationManager,
    get_conversation_manager,
    Conversation,
    MessageRole,
)
from src.agents.intent_router import (
    IntentRouter,
    get_intent_router,
    ToolExecutor,
    get_tool_executor,
    IntentResult,
    IntentType,
    ToolExecutionResult,
)


VIDEO_EDITOR_SYSTEM_PROMPT = """你是一个专业的视频编辑助手，可以帮助用户完成各种视频编辑任务。

你拥有以下能力：
1. **获取视频信息** - 查看视频的时长、分辨率、帧率等信息
2. **分割视频** - 将长视频分割成多个片段
3. **合并视频** - 将多个视频片段合并成一个
4. **生成语音（TTS）** - 将文本转换为语音
5. **生成字幕** - 从文本生成 SRT 格式字幕
6. **添加背景音乐** - 为视频添加背景音乐
7. **添加贴纸** - 为视频添加静态或动态贴纸
8. **一键合成视频** - 同时添加 TTS 语音、字幕、背景音乐和贴纸（推荐使用）

**工作流程：**
1. 分析用户的需求
2. 如果需要更多信息，向用户询问
3. 选择合适的工具来执行任务
4. 执行工具并向用户报告结果

**注意事项：**
- 对于视频路径，确保用户提供的是正确的绝对路径或相对路径
- 对于 compose_video_tool，这是最强大的工具，可以一次性完成多项操作，优先推荐使用
- 如果用户的需求涉及多个步骤，可以建议使用 compose_video_tool

**贴纸位置选项：**
top-left, top, top-right, middle-left, middle, middle-right, bottom-left, bottom, bottom-right

请用友好、专业的中文回答用户的问题。"""


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    video_path: Optional[str]
    text_content: Optional[str]
    background_music_path: Optional[str]
    stickers: Optional[List[Dict[str, Any]]]
    actions: Annotated[List[str], operator.add]
    current_step: Optional[str]
    results: Dict[str, Any]
    errors: Annotated[List[str], operator.add]
    conversation_id: Optional[str]


video_splitter_instance = VideoSplitter()
tts_service_instance = MiniMaxTTSService()
subtitle_generator_instance = SubtitleGenerator()
background_music_service_instance = BackgroundMusicService()
sticker_service_instance = StickerService()
video_composer_instance = VideoComposer()


@langchain_tool
def split_video_tool(video_path: str, segment_duration: int = 30) -> Dict[str, Any]:
    """
    将视频分割成多个片段。

    Args:
        video_path: 输入视频文件的完整路径
        segment_duration: 每个片段的时长（秒），默认30秒

    Returns:
        包含分割结果的字典，包括原始视频信息和所有片段列表
    """
    try:
        result = video_splitter_instance.split_video(
            video_path,
            {'segment_duration': segment_duration}
        )
        segments_info = [
            {
                'index': s.index,
                'start_time': s.start_time,
                'end_time': s.end_time,
                'duration': s.duration,
                'path': s.path,
                'filename': s.filename
            }
            for s in result['segments']
        ]
        return {
            'success': True,
            'original_video': result['original_video'],
            'segment_count': result['segment_count'],
            'segments': segments_info,
            'original_duration': result['original_info'].duration
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


@langchain_tool
def get_video_info_tool(video_path: str) -> Dict[str, Any]:
    """
    获取视频文件的详细信息。

    Args:
        video_path: 视频文件的完整路径

    Returns:
        包含视频信息的字典，包括时长、分辨率、帧率、音频信息等
    """
    try:
        info = video_splitter_instance.get_video_info(video_path)
        return {
            'success': True,
            'duration': info.duration,
            'size_mb': round(info.size / (1024 * 1024), 2),
            'bitrate_kbps': round(info.bitrate / 1000, 2),
            'video_codec': info.video.get('codec'),
            'resolution': f"{info.video.get('width')}x{info.video.get('height')}",
            'fps': info.video.get('fps'),
            'has_audio': info.audio is not None,
            'audio_codec': info.audio.get('codec') if info.audio else None,
            'audio_sample_rate': info.audio.get('sample_rate') if info.audio else None,
            'audio_channels': info.audio.get('channels') if info.audio else None,
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


@langchain_tool
def generate_tts_tool(text: str, output_path: Optional[str] = None,
                       voice_id: Optional[str] = None, speed: float = 1.0) -> Dict[str, Any]:
    """
    使用TTS（文本转语音）生成语音文件。

    Args:
        text: 要转换为语音的文本内容
        output_path: 输出音频文件的路径（可选）
        voice_id: 语音ID（可选，默认使用配置中的语音）
        speed: 语速，1.0为正常速度

    Returns:
        包含TTS生成结果的字典，包括音频文件路径和时长
    """
    try:
        options = {}
        if voice_id:
            options['voice_id'] = voice_id
        if speed != 1.0:
            options['speed'] = speed

        result = tts_service_instance.synthesize_speech(text, options)
        return {
            'success': True,
            'text': result.text,
            'audio_path': result.audio_path,
            'filename': result.filename,
            'duration_seconds': round(result.duration, 2),
            'format': result.format
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


@langchain_tool
def generate_subtitles_tool(text: str, output_path: Optional[str] = None,
                             total_duration: Optional[float] = None) -> Dict[str, Any]:
    """
    从文本生成SRT格式字幕。

    Args:
        text: 要转换为字幕的文本内容
        output_path: 输出SRT文件的路径（可选）
        total_duration: 字幕总时长（秒，可选，用于计算时间轴）

    Returns:
        包含字幕生成结果的字典，包括SRT内容和字幕片段列表
    """
    try:
        options = {}
        if total_duration:
            options['total_duration'] = total_duration

        result = subtitle_generator_instance.generate_srt_from_text(text, options)

        if output_path:
            save_result = subtitle_generator_instance.save_srt(result, output_path)
            output_file = save_result['path']
        else:
            output_file = None

        segments_info = [
            {
                'index': s.index,
                'start_time': s.start_time,
                'end_time': s.end_time,
                'duration': s.duration,
                'text': s.text
            }
            for s in result.segments
        ]

        return {
            'success': True,
            'subtitle_count': result.count,
            'total_duration_seconds': round(result.total_duration, 2) if result.total_duration else None,
            'srt_content': result.srt_content,
            'segments': segments_info,
            'output_file': output_file
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


@langchain_tool
def add_background_music_tool(video_path: str, music_path: str,
                                volume: float = 0.3, output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    为视频添加背景音乐。

    Args:
        video_path: 输入视频文件的路径
        music_path: 背景音乐文件的路径
        volume: 背景音乐音量（0.0-1.0，默认0.3）
        output_path: 输出视频文件的路径（可选）

    Returns:
        包含处理结果的字典，包括输出文件路径
    """
    try:
        from src.modules.video_composer import VideoComposer
        composer = VideoComposer()

        video_info = video_splitter_instance.get_video_info(video_path)

        bgm_result = background_music_service_instance.loop_audio_to_duration(
            music_path,
            video_info.duration,
            {'volume': volume}
        )

        if not output_path:
            base_name = helpers.get_file_name_without_extension(video_path)
            output_path = os.path.join(config.output_dir, f"{base_name}_with_bgm.mp4")

        cmd = [
            config.ffmpeg['path'], '-y',
            '-i', video_path,
            '-i', bgm_result.output_path,
            '-map', '0:v:0',
            '-map', '0:a:0?',
            '-map', '1:a:0',
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-shortest',
            output_path
        ]

        import subprocess
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise Exception(f'FFmpeg执行失败: {result.stderr.decode("utf-8", errors="ignore")}')

        return {
            'success': True,
            'original_video': video_path,
            'background_music': music_path,
            'output_path': output_path,
            'music_volume': volume,
            'video_duration_seconds': round(video_info.duration, 2)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


@langchain_tool
def add_sticker_tool(video_path: str, sticker_path: str,
                      position: str = 'bottom-right', scale: float = 1.0,
                      opacity: float = 1.0, start_seconds: float = 0.0,
                      duration: Optional[float] = None,
                      output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    为视频添加静态或动态贴纸。

    Args:
        video_path: 输入视频文件的路径
        sticker_path: 贴纸图片文件的路径（支持PNG、JPG、GIF等）
        position: 贴纸位置，可选值：top-left, top, top-right, middle-left, middle,
                  middle-right, bottom-left, bottom, bottom-right
        scale: 贴纸缩放比例，1.0为原始大小
        opacity: 贴纸透明度，0.0-1.0
        start_seconds: 贴纸开始显示的时间（秒）
        duration: 贴纸显示的持续时间（秒，可选，默认整个视频）
        output_path: 输出视频文件的路径（可选）

    Returns:
        包含处理结果的字典，包括输出文件路径和贴纸信息
    """
    try:
        sticker = {
            'path': sticker_path,
            'type': 'gif' if sticker_path.lower().endswith('.gif') else 'static',
            'position': position,
            'scale': scale,
            'opacity': opacity,
            'start_seconds': start_seconds
        }
        if duration:
            sticker['duration'] = duration

        options = {}
        if output_path:
            options['output_filename'] = os.path.basename(output_path)
            options['output_dir'] = os.path.dirname(output_path)

        result = sticker_service_instance.add_single_sticker(video_path, sticker, options)

        return {
            'success': True,
            'original_video': video_path,
            'output_path': result.output_path,
            'sticker_info': {
                'path': result.sticker['path'],
                'type': result.sticker['type'],
                'position': result.sticker['position'],
                'scale': result.sticker['scale'],
                'opacity': result.sticker['opacity'],
                'scaled_width': result.sticker['scaled_width'],
                'scaled_height': result.sticker['scaled_height'],
                'x': result.sticker['x'],
                'y': result.sticker['y']
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


@langchain_tool
def compose_video_tool(video_path: str,
                        text_content: Optional[str] = None,
                        background_music_path: Optional[str] = None,
                        stickers: Optional[List[Dict[str, Any]]] = None,
                        add_tts: bool = True,
                        add_subtitles: bool = True,
                        add_background_music: bool = True,
                        add_stickers: bool = True,
                        output_file_name: Optional[str] = None) -> Dict[str, Any]:
    """
    综合视频编辑功能，一键完成视频合成。
    可同时添加TTS语音、字幕、背景音乐和贴纸。

    Args:
        video_path: 输入视频文件的路径
        text_content: TTS语音和字幕的文本内容（可选）
        background_music_path: 背景音乐文件路径（可选）
        stickers: 贴纸列表，每个贴纸为字典，包含path, position, scale等（可选）
        add_tts: 是否添加TTS语音（默认True）
        add_subtitles: 是否添加字幕（默认True）
        add_background_music: 是否添加背景音乐（默认True）
        add_stickers: 是否添加贴纸（默认True）
        output_file_name: 输出文件名（可选，不含扩展名）

    Returns:
        包含合成结果的字典，包括输出文件路径和应用的效果列表
    """
    try:
        composer = VideoComposer()

        options = {
            'video_path': video_path,
            'text_content': text_content,
            'background_music_path': background_music_path,
            'output_file_name': output_file_name,
            'add_tts': add_tts and bool(text_content),
            'add_subtitles': add_subtitles,
            'add_background_music': add_background_music and bool(background_music_path),
            'add_stickers': add_stickers and bool(stickers),
            'stickers': stickers or [],
            'cleanup': False
        }

        result = composer.compose_video(options)

        return {
            'success': True,
            'output_path': result.output_path,
            'filename': result.filename,
            'original_video': result.original_video,
            'effects_applied': {
                'tts': result.tts_added,
                'subtitles': result.subtitles_added,
                'background_music': result.background_music_added,
                'stickers': result.stickers_added
            },
            'video_info': {
                'duration_seconds': round(result.video_info.get('duration', 0), 2),
                'resolution': f"{result.video_info.get('video', {}).get('width')}x{result.video_info.get('video', {}).get('height')}"
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


@langchain_tool
def merge_videos_tool(video_paths: List[str], output_path: str) -> Dict[str, Any]:
    """
    合并多个视频文件。

    Args:
        video_paths: 要合并的视频文件路径列表
        output_path: 输出视频文件的路径

    Returns:
        包含合并结果的字典
    """
    try:
        result = video_splitter_instance.merge_videos(video_paths, output_path)
        return {
            'success': True,
            'output_path': result,
            'merged_count': len(video_paths)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


@langchain_tool
def get_audio_info_tool(audio_path: str) -> Dict[str, Any]:
    """
    获取音频文件的详细信息。

    Args:
        audio_path: 音频文件的路径

    Returns:
        包含音频信息的字典
    """
    try:
        info = background_music_service_instance.get_audio_info(audio_path)
        return {
            'success': True,
            'duration_seconds': round(info.duration, 2),
            'size_mb': round(info.size / (1024 * 1024), 2),
            'bitrate_kbps': round(info.bitrate / 1000, 2) if info.bitrate else None,
            'codec': info.audio.get('codec') if info.audio else None,
            'sample_rate_hz': info.audio.get('sample_rate') if info.audio else None,
            'channels': info.audio.get('channels') if info.audio else None
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


tools = [
    split_video_tool,
    get_video_info_tool,
    generate_tts_tool,
    generate_subtitles_tool,
    add_background_music_tool,
    add_sticker_tool,
    compose_video_tool,
    merge_videos_tool,
    get_audio_info_tool
]


@dataclass
class ChatResponse:
    content: str
    tool_calls: List[Dict[str, Any]] = None
    tool_results: List[Dict[str, Any]] = None
    conversation_id: str = None
    is_complete: bool = True


class SmartVideoEditorAgent:
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        conversation_manager: Optional[ConversationManager] = None,
        intent_router: Optional[IntentRouter] = None,
        tool_executor: Optional[ToolExecutor] = None,
    ):
        self.llm_service = llm_service or get_llm_service()
        self.conversation_manager = conversation_manager or get_conversation_manager()
        self.intent_router = intent_router or get_intent_router()
        self.tool_executor = tool_executor or get_tool_executor()
        
        self.conversation_manager.set_system_prompt(VIDEO_EDITOR_SYSTEM_PROMPT)
        
        for tool in tools:
            self.intent_router.register_tool(tool.name, tool)
            self.tool_executor.register_tool(tool.name, tool)
        
        self.video_splitter = video_splitter_instance
        self.tts_service = tts_service_instance
        self.subtitle_generator = subtitle_generator_instance
        self.background_music_service = background_music_service_instance
        self.sticker_service = sticker_service_instance
        self.video_composer = video_composer_instance

    def create_conversation(self, title: str = "新对话") -> str:
        conversation = self.conversation_manager.create_conversation(title=title)
        return conversation.id

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        return self.conversation_manager.get_conversation(conversation_id)

    def get_all_conversations(self) -> List[Conversation]:
        return self.conversation_manager.get_all_conversations()

    def delete_conversation(self, conversation_id: str) -> bool:
        return self.conversation_manager.delete_conversation(conversation_id)

    async def chat(
        self,
        user_input: str,
        conversation_id: Optional[str] = None,
        auto_execute_tools: bool = True,
    ) -> ChatResponse:
        if conversation_id:
            conversation = self.conversation_manager.get_conversation(conversation_id)
            if not conversation:
                conversation = self.conversation_manager.create_conversation()
                conversation_id = conversation.id
        else:
            conversation = self.conversation_manager.create_conversation()
            conversation_id = conversation.id

        self.conversation_manager.add_user_message(
            conversation_id,
            user_input,
        )

        intent_result = await self.intent_router.recognize_intent(
            user_input,
            conversation,
        )

        if intent_result.intent == IntentType.CLARIFICATION:
            response = ChatResponse(
                content=intent_result.reasoning or "我需要更多信息来帮您完成这个任务。",
                conversation_id=conversation_id,
                is_complete=True,
            )
            self.conversation_manager.add_assistant_message(
                conversation_id,
                response.content,
            )
            return response

        if intent_result.intent == IntentType.CONVERSATION:
            messages = conversation.get_langchain_messages()
            llm_response = await self.llm_service.chat(messages)
            
            response = ChatResponse(
                content=llm_response.content,
                conversation_id=conversation_id,
                is_complete=True,
            )
            self.conversation_manager.add_assistant_message(
                conversation_id,
                response.content,
            )
            return response

        messages = conversation.get_langchain_messages()
        llm_response = await self.llm_service.chat(
            messages,
            tools=tools,
        )

        tool_calls = llm_response.tool_calls or []
        tool_results = []

        if tool_calls and auto_execute_tools:
            for tool_call in tool_calls:
                tool_name = tool_call['name']
                tool_params = tool_call['args']
                tool_call_id = tool_call['id']

                execution_result = await self.tool_executor.execute_tool(
                    tool_name,
                    tool_params,
                )

                result_content = json.dumps(
                    execution_result.result if execution_result.success else {'error': execution_result.error},
                    ensure_ascii=False,
                )

                self.conversation_manager.add_tool_message(
                    conversation_id,
                    content=result_content,
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                )

                tool_results.append({
                    'tool_name': tool_name,
                    'success': execution_result.success,
                    'result': execution_result.result,
                    'error': execution_result.error,
                })

            updated_messages = conversation.get_langchain_messages()
            final_response = await self.llm_service.chat(updated_messages)

            response = ChatResponse(
                content=final_response.content,
                tool_calls=tool_calls,
                tool_results=tool_results,
                conversation_id=conversation_id,
                is_complete=True,
            )

            self.conversation_manager.add_assistant_message(
                conversation_id,
                response.content,
            )

            self._update_context_from_results(conversation_id, tool_results)

            return response

        response = ChatResponse(
            content=llm_response.content,
            tool_calls=tool_calls,
            conversation_id=conversation_id,
            is_complete=not tool_calls,
        )

        if llm_response.content:
            self.conversation_manager.add_assistant_message(
                conversation_id,
                llm_response.content,
                tool_calls=tool_calls,
            )

        return response

    def _update_context_from_results(
        self,
        conversation_id: str,
        tool_results: List[Dict[str, Any]],
    ):
        for result in tool_results:
            if not result['success']:
                continue
            
            tool_name = result['tool_name']
            data = result['result']
            
            if tool_name == 'compose_video_tool':
                if data.get('output_path'):
                    self.conversation_manager.update_context(
                        conversation_id,
                        output_path=data['output_path'],
                        last_action='compose_video',
                    )
            elif tool_name == 'get_video_info_tool':
                if data.get('success'):
                    self.conversation_manager.update_context(
                        conversation_id,
                        last_action='get_video_info',
                    )
            elif tool_name == 'generate_tts_tool':
                if data.get('success'):
                    self.conversation_manager.update_context(
                        conversation_id,
                        last_action='generate_tts',
                    )

    async def execute_tool_direct(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        conversation_id: Optional[str] = None,
    ) -> ToolExecutionResult:
        result = await self.tool_executor.execute_tool(tool_name, parameters)
        
        if conversation_id:
            conversation = self.conversation_manager.get_conversation(conversation_id)
            if conversation:
                self.conversation_manager.update_context(
                    conversation_id,
                    last_action=tool_name,
                )
        
        return result

    def get_tool_info(self) -> List[Dict[str, Any]]:
        tool_info_list = []
        for tool in tools:
            tool_info_list.append({
                'name': tool.name,
                'description': tool.description,
                'args_schema': tool.args_schema.schema() if tool.args_schema else None,
            })
        return tool_info_list


_smart_agent: Optional[SmartVideoEditorAgent] = None


def get_smart_agent() -> SmartVideoEditorAgent:
    global _smart_agent
    if _smart_agent is None:
        _smart_agent = SmartVideoEditorAgent()
    return _smart_agent


def create_video_editor_agent():
    return get_smart_agent()


class VideoEditorAgent:
    def __init__(self):
        self._smart_agent = get_smart_agent()
        self.video_splitter = video_splitter_instance
        self.tts_service = tts_service_instance
        self.subtitle_generator = subtitle_generator_instance
        self.background_music_service = background_music_service_instance
        self.sticker_service = sticker_service_instance
        self.video_composer = video_composer_instance

    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        return get_video_info_tool.invoke({'video_path': video_path})

    def split_video(self, video_path: str, segment_duration: int = 30) -> Dict[str, Any]:
        return split_video_tool.invoke({
            'video_path': video_path,
            'segment_duration': segment_duration
        })

    def generate_tts(self, text: str, voice_id: Optional[str] = None,
                      speed: float = 1.0) -> Dict[str, Any]:
        return generate_tts_tool.invoke({
            'text': text,
            'voice_id': voice_id,
            'speed': speed
        })

    def generate_subtitles(self, text: str, total_duration: Optional[float] = None) -> Dict[str, Any]:
        return generate_subtitles_tool.invoke({
            'text': text,
            'total_duration': total_duration
        })

    def add_background_music(self, video_path: str, music_path: str,
                               volume: float = 0.3) -> Dict[str, Any]:
        return add_background_music_tool.invoke({
            'video_path': video_path,
            'music_path': music_path,
            'volume': volume
        })

    def add_sticker(self, video_path: str, sticker_path: str,
                     position: str = 'bottom-right', scale: float = 1.0,
                     opacity: float = 1.0) -> Dict[str, Any]:
        return add_sticker_tool.invoke({
            'video_path': video_path,
            'sticker_path': sticker_path,
            'position': position,
            'scale': scale,
            'opacity': opacity
        })

    def compose_video(self, video_path: str,
                       text_content: Optional[str] = None,
                       background_music_path: Optional[str] = None,
                       stickers: Optional[List[Dict[str, Any]]] = None,
                       add_tts: bool = True,
                       add_subtitles: bool = True,
                       add_background_music: bool = True,
                       add_stickers: bool = True) -> Dict[str, Any]:
        return compose_video_tool.invoke({
            'video_path': video_path,
            'text_content': text_content,
            'background_music_path': background_music_path,
            'stickers': stickers,
            'add_tts': add_tts,
            'add_subtitles': add_subtitles,
            'add_background_music': add_background_music,
            'add_stickers': add_stickers
        })

    def merge_videos(self, video_paths: List[str], output_path: str) -> Dict[str, Any]:
        return merge_videos_tool.invoke({
            'video_paths': video_paths,
            'output_path': output_path
        })

    async def chat(self, user_input: str) -> str:
        response = await self._smart_agent.chat(user_input)
        return response.content
