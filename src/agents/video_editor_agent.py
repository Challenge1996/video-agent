import os
from typing import List, Dict, Any, Optional, TypedDict, Annotated
from dataclasses import dataclass
from pathlib import Path
import operator

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from src.config.config import config
from src.utils.helpers import helpers
from src.modules.video_splitter import VideoSplitter
from src.modules.tts_service import TTSService
from src.modules.minimax_tts_service import MiniMaxTTSService
from src.modules.subtitle_generator import SubtitleGenerator
from src.modules.background_music import BackgroundMusicService
from src.modules.sticker_service import StickerService
from src.modules.video_composer import VideoComposer


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


video_splitter_instance = VideoSplitter()
tts_service_instance = MiniMaxTTSService()
subtitle_generator_instance = SubtitleGenerator()
background_music_service_instance = BackgroundMusicService()
sticker_service_instance = StickerService()
video_composer_instance = VideoComposer()


@tool
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


@tool
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


@tool
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


@tool
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


@tool
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


@tool
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


@tool
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


@tool
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


@tool
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


def create_video_editor_agent():
    """
    创建视频编辑Agent。

    这个Agent可以执行以下操作：
    - 获取视频/音频信息
    - 分割视频
    - 合并视频
    - 生成TTS语音
    - 生成字幕
    - 添加背景音乐
    - 添加贴纸
    - 一键合成视频（包含所有功能）
    """
    from langgraph.graph import StateGraph, START, END
    from langgraph.prebuilt import ToolNode
    from langchain_core.tools import tool

    def should_continue(state: AgentState):
        messages = state['messages']
        last_message = messages[-1] if messages else None

        if last_message and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return 'tools'
        return END

    def call_model(state: AgentState):
        from langchain_core.messages import HumanMessage, SystemMessage

        system_prompt = SystemMessage(content="""你是一个专业的视频编辑Agent。你可以使用以下工具来帮助用户完成视频编辑任务：

1. split_video_tool - 将视频分割成多个片段
2. get_video_info_tool - 获取视频文件的详细信息
3. generate_tts_tool - 使用TTS生成语音文件
4. generate_subtitles_tool - 从文本生成字幕
5. add_background_music_tool - 为视频添加背景音乐
6. add_sticker_tool - 为视频添加贴纸
7. compose_video_tool - 一键合成视频（可同时添加TTS、字幕、背景音乐和贴纸）
8. merge_videos_tool - 合并多个视频
9. get_audio_info_tool - 获取音频文件信息

当用户询问如何编辑视频时，分析用户需求并选择合适的工具。

使用工具时：
- 确保提供的文件路径是正确的
- 对于贴纸位置，可选择：top-left, top, top-right, middle-left, middle, middle-right, bottom-left, bottom, bottom-right
- 对于compose_video_tool，可以一次性完成多项操作，这是最常用的工具

执行完工具后，总结结果给用户。""")

        return {'messages': [system_prompt]}

    workflow = StateGraph(AgentState)

    tool_node = ToolNode(tools)

    workflow.add_node('model', call_model)
    workflow.add_node('tools', tool_node)

    workflow.add_edge(START, 'model')
    workflow.add_conditional_edges('model', should_continue)
    workflow.add_edge('tools', 'model')

    app = workflow.compile()
    return app


class VideoEditorAgent:
    """
    视频编辑Agent类，提供更简单的接口。
    """

    def __init__(self):
        self.app = create_video_editor_agent()
        self.video_splitter = VideoSplitter()
        self.tts_service = MiniMaxTTSService()
        self.subtitle_generator = SubtitleGenerator()
        self.background_music_service = BackgroundMusicService()
        self.sticker_service = StickerService()
        self.video_composer = VideoComposer()

    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """获取视频信息"""
        return get_video_info_tool.invoke({'video_path': video_path})

    def split_video(self, video_path: str, segment_duration: int = 30) -> Dict[str, Any]:
        """分割视频"""
        return split_video_tool.invoke({
            'video_path': video_path,
            'segment_duration': segment_duration
        })

    def generate_tts(self, text: str, voice_id: Optional[str] = None,
                      speed: float = 1.0) -> Dict[str, Any]:
        """生成TTS语音"""
        return generate_tts_tool.invoke({
            'text': text,
            'voice_id': voice_id,
            'speed': speed
        })

    def generate_subtitles(self, text: str, total_duration: Optional[float] = None) -> Dict[str, Any]:
        """生成字幕"""
        return generate_subtitles_tool.invoke({
            'text': text,
            'total_duration': total_duration
        })

    def add_background_music(self, video_path: str, music_path: str,
                               volume: float = 0.3) -> Dict[str, Any]:
        """添加背景音乐"""
        return add_background_music_tool.invoke({
            'video_path': video_path,
            'music_path': music_path,
            'volume': volume
        })

    def add_sticker(self, video_path: str, sticker_path: str,
                     position: str = 'bottom-right', scale: float = 1.0,
                     opacity: float = 1.0) -> Dict[str, Any]:
        """添加贴纸"""
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
        """一键合成视频"""
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
        """合并视频"""
        return merge_videos_tool.invoke({
            'video_paths': video_paths,
            'output_path': output_path
        })

    async def chat(self, user_input: str) -> str:
        """
        与Agent进行对话式交互。

        Args:
            user_input: 用户的自然语言输入

        Returns:
            Agent的响应
        """
        from langchain_core.messages import HumanMessage

        state = {
            'messages': [HumanMessage(content=user_input)],
            'video_path': None,
            'text_content': None,
            'background_music_path': None,
            'stickers': None,
            'actions': [],
            'current_step': None,
            'results': {},
            'errors': []
        }

        result = await self.app.ainvoke(state)

        messages = result.get('messages', [])
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, 'content'):
                return last_message.content

        return "处理完成。"
