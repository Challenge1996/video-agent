import os
import json
import asyncio
from typing import List, Dict, Any, Optional, TypedDict, Annotated, Callable
from dataclasses import dataclass, asdict, field
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
from src.modules.video_resizer import VideoResizer, COMMON_ASPECT_RATIOS, COMMON_RESOLUTIONS

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
from src.agents.task_progress_manager import (
    TaskProgressManager,
    TaskProgress,
    TodoItem,
    TodoStatus,
    ProgressCallback,
    get_task_progress_manager,
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
9. **调整分辨率** - 改变视频尺寸，如 1080p → 720p
10. **裁剪视频画面** - 裁剪视频画面，可以指定精确的裁剪区域或按画幅比居中裁剪
11. **切换画幅比** - 转换视频画幅比并调整到目标分辨率，支持横屏16:9/正方形1:1 → 竖屏9:16（抖音格式）
12. **抖音竖屏转换** - 一键转换为抖音竖屏格式（9:16）

**重要：工具选择指南**

当用户说以下内容时，使用 **switch_aspect_ratio_tool**（切换画幅比）：
- "转换为9:16"、"改为竖屏"、"切换画幅比"
- "调整为抖音格式"、"抖音尺寸"、"9:16比例"
- 这个工具会同时调整分辨率（如 720x1280）和画幅比

当用户说以下内容时，使用 **crop_video_tool**（裁剪视频画面）：
- "裁剪画面"、"剪掉边缘"、"裁掉多余部分"
- "按比例裁剪" 但不涉及具体目标分辨率

**重要：工具执行结果使用**
- 工具执行后会返回 `output_path` 字段，这是实际生成的文件路径
- 工具执行后会返回 `output_filename` 字段，这是生成的文件名
- **不要猜测文件名**，始终使用工具返回的 `output_path` 来获取结果
- 如果工具返回 `success: false`，则表示执行失败，请检查错误信息

**工作流程：**
1. 分析用户的需求
2. 如果需要更多信息，向用户询问
3. 选择合适的工具来执行任务
4. 执行工具并向用户报告结果
5. 使用工具返回的 `output_path` 来查看结果文件

**注意事项：**
- 对于视频路径，确保用户提供的是正确的绝对路径或相对路径
- 对于 compose_video_tool，这是最强大的工具，可以一次性完成多项操作，优先推荐使用
- 如果用户的需求涉及多个步骤，可以建议使用 compose_video_tool

**贴纸位置选项：**
top-left, top, top-right, middle-left, middle, middle-right, bottom-left, bottom, bottom-right

**支持的画幅比：**
9:16 (抖音竖屏), 16:9 (横屏), 1:1 (正方形), 4:3, 3:4

**支持的分辨率预设：**
1080p (1920x1080), 720p (1280x720), 480p, 360p, 4k, 1080x1920 (竖屏), 720x1280 (竖屏)

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
video_resizer_instance = VideoResizer()


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


@langchain_tool
def resize_video_tool(video_path: str,
                      target_width: Optional[int] = None,
                      target_height: Optional[int] = None,
                      resolution: Optional[str] = None) -> Dict[str, Any]:
    """
    调整视频分辨率。可以指定目标宽度/高度，或使用预设分辨率（如 '720p', '1080x1920'）。

    Args:
        video_path: 输入视频文件的路径
        target_width: 目标宽度（可选，若只指定宽度则保持宽高比）
        target_height: 目标高度（可选，若只指定高度则保持宽高比）
        resolution: 预设分辨率，如 '720p', '1080p', '1080x1920', '720x1280'（可选）

    Returns:
        包含调整结果的字典，包括输出文件路径和新的分辨率
    """
    try:
        result = video_resizer_instance.resize_video(
            video_path=video_path,
            target_width=target_width,
            target_height=target_height,
            resolution=resolution
        )
        
        if not result.success:
            return {'success': False, 'error': result.error}
        
        return {
            'success': True,
            'original_resolution': f"{result.original_width}x{result.original_height}",
            'original_aspect_ratio': result.original_aspect_ratio,
            'output_resolution': f"{result.output_width}x{result.output_height}",
            'output_aspect_ratio': result.output_aspect_ratio,
            'output_path': result.output_path,
            'operation': 'resize'
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


@langchain_tool
def crop_video_tool(video_path: str,
                    crop_width: Optional[int] = None,
                    crop_height: Optional[int] = None,
                    crop_x: Optional[int] = None,
                    crop_y: Optional[int] = None,
                    aspect_ratio: Optional[str] = None) -> Dict[str, Any]:
    """
    裁剪视频画面。可以指定精确的裁剪区域，或按画幅比自动居中裁剪。

    Args:
        video_path: 输入视频文件的路径
        crop_width: 裁剪宽度（可选，若使用 aspect_ratio 则不需要）
        crop_height: 裁剪高度（可选，若使用 aspect_ratio 则不需要）
        crop_x: 裁剪起始 X 坐标（可选，默认居中）
        crop_y: 裁剪起始 Y 坐标（可选，默认居中）
        aspect_ratio: 按画幅比裁剪，如 '9:16', '16:9', '1:1'（可选，推荐使用）

    Returns:
        包含裁剪结果的字典
    """
    try:
        result = video_resizer_instance.crop_video(
            video_path=video_path,
            crop_width=crop_width,
            crop_height=crop_height,
            crop_x=crop_x,
            crop_y=crop_y,
            aspect_ratio=aspect_ratio
        )
        
        if not result.success:
            return {'success': False, 'error': result.error}
        
        return {
            'success': True,
            'original_resolution': f"{result.original_width}x{result.original_height}",
            'crop_region': {
                'x': result.crop_x,
                'y': result.crop_y,
                'width': result.crop_width,
                'height': result.crop_height
            },
            'output_path': result.output_path
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


@langchain_tool
def convert_aspect_ratio_tool(video_path: str,
                               target_aspect: str = '9:16',
                               method: str = 'crop',
                               target_resolution: Optional[str] = None) -> Dict[str, Any]:
    """
    转换视频画幅比。支持从横屏16:9/正方形1:1等转换为竖屏9:16（抖音格式）。

    Args:
        video_path: 输入视频文件的路径
        target_aspect: 目标画幅比，支持 '9:16'（抖音竖屏）、'16:9'（横屏）、'1:1'（正方形）、'4:3'、'3:4'
        method: 转换方式，'crop' = 中心裁剪（保留中间部分），'pad' = 加黑边填充（保留全部内容）
        target_resolution: 目标分辨率，如 '720x1280'（可选）

    Returns:
        包含转换结果的字典
    """
    try:
        result = video_resizer_instance.convert_aspect_ratio(
            video_path=video_path,
            target_aspect=target_aspect,
            method=method,
            target_resolution=target_resolution
        )
        
        if not result.success:
            return {'success': False, 'error': result.error}
        
        return {
            'success': True,
            'original_resolution': f"{result.original_width}x{result.original_height}",
            'original_aspect_ratio': result.original_aspect_ratio,
            'target_aspect_ratio': result.target_aspect_ratio,
            'output_resolution': f"{result.output_width}x{result.output_height}",
            'method': result.method,
            'method_description': '中心裁剪' if result.method == 'crop' else '加黑边填充' if result.method == 'pad' else '无需转换',
            'output_path': result.output_path
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


@langchain_tool
def convert_to_douyin_format_tool(video_path: str,
                                   method: str = 'crop',
                                   target_resolution: str = '720x1280') -> Dict[str, Any]:
    """
    一键转换为抖音竖屏格式（9:16）。这是转换抖音视频的首选工具。

    Args:
        video_path: 输入视频文件的路径
        method: 转换方式，'crop' = 中心裁剪（推荐，保留中间部分），'pad' = 加黑边填充（保留全部内容）
        target_resolution: 目标分辨率，默认 '720x1280'

    Returns:
        包含转换结果的字典
    """
    try:
        result = video_resizer_instance.convert_to_douyin_format(
            video_path=video_path,
            method=method,
            target_resolution=target_resolution
        )
        
        if not result.success:
            return {'success': False, 'error': result.error}
        
        return {
            'success': True,
            'original_resolution': f"{result.original_width}x{result.original_height}",
            'original_aspect_ratio': result.original_aspect_ratio,
            'target_aspect_ratio': result.target_aspect_ratio,
            'output_resolution': f"{result.output_width}x{result.output_height}",
            'method': result.method,
            'method_description': '中心裁剪' if result.method == 'crop' else '加黑边填充' if result.method == 'pad' else '无需转换',
            'output_path': result.output_path,
            'note': '已转换为抖音竖屏格式 9:16'
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


@langchain_tool
def switch_aspect_ratio_tool(video_path: str,
                              aspect_ratio: str = '9:16',
                              method: str = 'crop',
                              target_resolution: Optional[str] = '720x1280') -> Dict[str, Any]:
    """
    切换视频画幅比。这是转换视频画幅比的主要工具，推荐使用。
    支持从横屏16:9/正方形1:1等转换为竖屏9:16（抖音格式）。

    当用户说"转换为9:16"、"改为竖屏"、"切换画幅比"、"调整为抖音格式"时，使用此工具。

    Args:
        video_path: 输入视频文件的路径
        aspect_ratio: 目标画幅比，支持 '9:16'（抖音竖屏）、'16:9'（横屏）、'1:1'（正方形）、'4:3'、'3:4'
        method: 转换方式，'crop' = 中心裁剪（推荐，保留中间部分，无黑边），'pad' = 加黑边填充（保留全部内容）
        target_resolution: 目标分辨率，默认 '720x1280'（抖音标准）

    Returns:
        包含转换结果的字典
    """
    try:
        result = video_resizer_instance.convert_aspect_ratio(
            video_path=video_path,
            target_aspect=aspect_ratio,
            method=method,
            target_resolution=target_resolution
        )
        
        if not result.success:
            return {'success': False, 'error': result.error}
        
        return {
            'success': True,
            'original_resolution': f"{result.original_width}x{result.original_height}",
            'original_aspect_ratio': result.original_aspect_ratio,
            'target_aspect_ratio': result.target_aspect_ratio,
            'output_resolution': f"{result.output_width}x{result.output_height}",
            'method': result.method,
            'method_description': '中心裁剪' if result.method == 'crop' else '加黑边填充' if result.method == 'pad' else '无需转换',
            'output_path': result.output_path,
            'output_filename': os.path.basename(result.output_path)
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
    get_audio_info_tool,
    resize_video_tool,
    crop_video_tool,
    convert_aspect_ratio_tool,
    convert_to_douyin_format_tool,
    switch_aspect_ratio_tool
]


@dataclass
class ChatResponse:
    content: str
    tool_calls: List[Dict[str, Any]] = None
    tool_results: List[Dict[str, Any]] = None
    todo_list: List[Dict[str, Any]] = None
    conversation_id: str = None
    task_id: str = None
    is_complete: bool = True


class SmartVideoEditorAgent:
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        conversation_manager: Optional[ConversationManager] = None,
        intent_router: Optional[IntentRouter] = None,
        tool_executor: Optional[ToolExecutor] = None,
        task_progress_manager: Optional[TaskProgressManager] = None,
    ):
        self.llm_service = llm_service or get_llm_service()
        self.conversation_manager = conversation_manager or get_conversation_manager()
        self.intent_router = intent_router or get_intent_router()
        self.tool_executor = tool_executor or get_tool_executor()
        self.task_progress_manager = task_progress_manager or get_task_progress_manager()
        
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
        self.video_resizer = video_resizer_instance
        
        self._current_task: Optional[TaskProgress] = None

    def create_conversation(self, title: str = "新对话") -> str:
        conversation = self.conversation_manager.create_conversation(title=title)
        return conversation.id

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        return self.conversation_manager.get_conversation(conversation_id)

    def get_all_conversations(self) -> List[Conversation]:
        return self.conversation_manager.get_all_conversations()

    def delete_conversation(self, conversation_id: str) -> bool:
        return self.conversation_manager.delete_conversation(conversation_id)

    def _get_tool_display_name(self, tool_name: str) -> str:
        tool_names = {
            'split_video_tool': '分割视频',
            'get_video_info_tool': '获取视频信息',
            'generate_tts_tool': '生成语音(TTS)',
            'generate_subtitles_tool': '生成字幕',
            'add_background_music_tool': '添加背景音乐',
            'add_sticker_tool': '添加贴纸',
            'compose_video_tool': '合成视频',
            'merge_videos_tool': '合并视频',
            'get_audio_info_tool': '获取音频信息',
            'resize_video_tool': '调整分辨率',
            'crop_video_tool': '裁剪视频',
            'convert_aspect_ratio_tool': '切换画幅比',
            'convert_to_douyin_format_tool': '抖音格式转换',
            'switch_aspect_ratio_tool': '切换画幅比',
        }
        return tool_names.get(tool_name, tool_name)

    def _generate_task_from_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        conversation_id: str,
        message_id: Optional[str] = None,
    ) -> TaskProgress:
        task = self.task_progress_manager.create_task(
            title="视频编辑任务",
            conversation_id=conversation_id,
            message_id=message_id,
        )
        
        for tool_call in tool_calls:
            tool_name = tool_call.get('name', '')
            tool_params = tool_call.get('args', {})
            display_name = self._get_tool_display_name(tool_name)
            
            todo_title = display_name
            if tool_params.get('video_path'):
                todo_title += f" - {os.path.basename(tool_params['video_path'])}"
            elif tool_params.get('text'):
                text_preview = tool_params['text'][:30] + ('...' if len(tool_params['text']) > 30 else '')
                todo_title += f" - \"{text_preview}\""
            
            self.task_progress_manager.add_todo(
                task_id=task.task_id,
                title=todo_title,
                status=TodoStatus.PENDING,
                metadata={
                    'tool_name': tool_name,
                    'tool_params': tool_params,
                    'tool_call_id': tool_call.get('id'),
                }
            )
        
        return task

    async def chat(
        self,
        user_input: str,
        conversation_id: Optional[str] = None,
        auto_execute_tools: bool = True,
        message_id: Optional[str] = None,
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
        task: Optional[TaskProgress] = None

        if tool_calls:
            task = self._generate_task_from_tool_calls(
                tool_calls=tool_calls,
                conversation_id=conversation_id,
                message_id=message_id,
            )
            self._current_task = task

        if tool_calls and auto_execute_tools:
            for idx, tool_call in enumerate(tool_calls):
                tool_name = tool_call['name']
                tool_params = tool_call['args']
                tool_call_id = tool_call['id']
                
                todo_item = task.todos[idx] if task and idx < len(task.todos) else None
                
                if todo_item:
                    self.task_progress_manager.start_todo(
                        task_id=task.task_id,
                        todo_id=todo_item.id,
                    )

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

                if todo_item:
                    if execution_result.success:
                        self.task_progress_manager.complete_todo(
                            task_id=task.task_id,
                            todo_id=todo_item.id,
                            result=execution_result.result,
                        )
                    else:
                        self.task_progress_manager.fail_todo(
                            task_id=task.task_id,
                            todo_id=todo_item.id,
                            error=execution_result.error or "未知错误",
                        )

            updated_messages = conversation.get_langchain_messages()
            final_response = await self.llm_service.chat(updated_messages)

            todo_list = None
            if task:
                todo_list = [todo.to_dict() for todo in task.todos]

            response = ChatResponse(
                content=final_response.content,
                tool_calls=tool_calls,
                tool_results=tool_results,
                todo_list=todo_list,
                task_id=task.task_id if task else None,
                conversation_id=conversation_id,
                is_complete=True,
            )

            self.conversation_manager.add_assistant_message(
                conversation_id,
                response.content,
                todo_list=todo_list,
            )

            self._update_context_from_results(conversation_id, tool_results)

            return response

        todo_list = None
        if task:
            todo_list = [todo.to_dict() for todo in task.todos]

        response = ChatResponse(
            content=llm_response.content,
            tool_calls=tool_calls,
            todo_list=todo_list,
            task_id=task.task_id if task else None,
            conversation_id=conversation_id,
            is_complete=not tool_calls,
        )

        if llm_response.content:
            self.conversation_manager.add_assistant_message(
                conversation_id,
                llm_response.content,
                tool_calls=tool_calls,
                todo_list=todo_list,
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
        self.video_resizer = video_resizer_instance

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

    def resize_video(self, video_path: str,
                     target_width: Optional[int] = None,
                     target_height: Optional[int] = None,
                     resolution: Optional[str] = None) -> Dict[str, Any]:
        return resize_video_tool.invoke({
            'video_path': video_path,
            'target_width': target_width,
            'target_height': target_height,
            'resolution': resolution
        })

    def crop_video(self, video_path: str,
                   crop_width: Optional[int] = None,
                   crop_height: Optional[int] = None,
                   crop_x: Optional[int] = None,
                   crop_y: Optional[int] = None,
                   aspect_ratio: Optional[str] = None) -> Dict[str, Any]:
        return crop_video_tool.invoke({
            'video_path': video_path,
            'crop_width': crop_width,
            'crop_height': crop_height,
            'crop_x': crop_x,
            'crop_y': crop_y,
            'aspect_ratio': aspect_ratio
        })

    def convert_aspect_ratio(self, video_path: str,
                              target_aspect: str = '9:16',
                              method: str = 'crop',
                              target_resolution: Optional[str] = None) -> Dict[str, Any]:
        return convert_aspect_ratio_tool.invoke({
            'video_path': video_path,
            'target_aspect': target_aspect,
            'method': method,
            'target_resolution': target_resolution
        })

    def convert_to_douyin_format(self, video_path: str,
                                  method: str = 'crop',
                                  target_resolution: str = '720x1280') -> Dict[str, Any]:
        return convert_to_douyin_format_tool.invoke({
            'video_path': video_path,
            'method': method,
            'target_resolution': target_resolution
        })

    def switch_aspect_ratio(self, video_path: str,
                            aspect_ratio: str = '9:16',
                            method: str = 'crop',
                            target_resolution: str = '720x1280') -> Dict[str, Any]:
        return switch_aspect_ratio_tool.invoke({
            'video_path': video_path,
            'aspect_ratio': aspect_ratio,
            'method': method,
            'target_resolution': target_resolution
        })

    async def chat(self, user_input: str) -> str:
        response = await self._smart_agent.chat(user_input)
        return response.content
