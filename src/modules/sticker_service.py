import os
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from src.config.config import config
from src.utils.helpers import helpers


@dataclass
class ImageInfo:
    width: int
    height: int
    duration: Optional[float]
    is_animated: bool
    format: str


@dataclass
class StickerResult:
    success: bool
    original_video: str
    output_path: str
    filename: str
    sticker: Dict[str, Any]


@dataclass
class MultiStickerResult:
    success: bool
    original_video: str
    output_path: str
    filename: str
    stickers: List[Dict[str, Any]]
    stickers_count: int


@dataclass
class StaticStickerResult:
    success: bool
    original_gif: str
    output_path: str
    filename: str
    frame_index: int


@dataclass
class ValidationResult:
    valid: bool
    type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    is_animated: Optional[bool] = None
    format: Optional[str] = None
    error: Optional[str] = None


class StickerService:
    def __init__(self, options: Optional[Dict[str, Any]] = None):
        options = options or {}
        self.options = {
            'output_dir': options.get('output_dir', config.temp_dir),
            'default_opacity': options.get('default_opacity', config.sticker['default_opacity']),
            'default_scale': options.get('default_scale', config.sticker['default_scale']),
            'default_position': options.get('default_position', config.sticker['default_position']),
            **options,
        }
        self.ffmpeg_path = config.ffmpeg['path']
        self.ffprobe_path = config.ffmpeg['ffprobe_path']

    def get_image_info(self, image_path: str) -> ImageInfo:
        if not os.path.exists(image_path):
            raise Exception(f'图片文件不存在: {image_path}')

        cmd = [
            self.ffprobe_path,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            image_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f'无法获取图片信息: {result.stderr}')

        metadata = json.loads(result.stdout)
        format_info = metadata.get('format', {})
        streams = metadata.get('streams', [])
        video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)

        duration = None
        if format_info.get('duration'):
            duration = float(format_info['duration'])

        is_animated = duration is not None and duration > 0

        return ImageInfo(
            width=video_stream.get('width', 0) if video_stream else 0,
            height=video_stream.get('height', 0) if video_stream else 0,
            duration=duration,
            is_animated=is_animated,
            format=format_info.get('format_name', '')
        )

    def _validate_sticker_options(self, sticker: Dict[str, Any], video_info: Dict[str, Any]) -> Dict[str, Any]:
        sticker_path = sticker.get('path')
        sticker_type = sticker.get('type', 'static')
        position = sticker.get('position', self.options['default_position'])
        scale = sticker.get('scale', self.options['default_scale'])
        opacity = sticker.get('opacity', self.options['default_opacity'])
        start_seconds = sticker.get('start_seconds', 0)
        duration = sticker.get('duration')
        x = sticker.get('x')
        y = sticker.get('y')

        if not sticker_path:
            raise Exception('贴纸路径不能为空')

        if not os.path.exists(sticker_path):
            raise Exception(f'贴纸文件不存在: {sticker_path}')

        if scale <= 0:
            raise Exception('缩放比例必须大于0')

        if opacity < 0 or opacity > 1:
            raise Exception('透明度必须在0到1之间')

        if start_seconds < 0:
            raise Exception('开始时间不能为负数')

        if duration is not None and duration <= 0:
            raise Exception('持续时间必须大于0')

        valid_types = ['static', 'gif']
        if sticker_type not in valid_types:
            raise Exception(f'不支持的贴纸类型: {sticker_type}，支持的类型: {", ".join(valid_types)}')

        return {
            'path': sticker_path,
            'type': sticker_type,
            'position': position,
            'scale': scale,
            'opacity': opacity,
            'start_seconds': start_seconds,
            'duration': duration,
            'x': x,
            'y': y,
        }

    def _calculate_position(self, position: str, video_width: int, video_height: int,
                             sticker_width: int, sticker_height: int,
                             x: Optional[float] = None, y: Optional[float] = None) -> Tuple[float, float]:
        if x is not None and y is not None:
            return (x, y)

        x_center = (video_width - sticker_width) / 2
        y_center = (video_height - sticker_height) / 2

        margin = min(video_width, video_height) * 0.05

        positions = {
            'top-left': (margin, margin),
            'top': (x_center, margin),
            'top-right': (video_width - sticker_width - margin, margin),
            'middle-left': (margin, y_center),
            'middle': (x_center, y_center),
            'middle-right': (video_width - sticker_width - margin, y_center),
            'bottom-left': (margin, video_height - sticker_height - margin),
            'bottom': (x_center, video_height - sticker_height - margin),
            'bottom-right': (video_width - sticker_width - margin, video_height - sticker_height - margin),
        }

        return positions.get(position.lower(), positions['top-left'])

    def add_single_sticker(self, video_path: str, sticker: Dict[str, Any],
                             options: Optional[Dict[str, Any]] = None) -> StickerResult:
        options = options or {}
        output_dir = options.get('output_dir', self.options['output_dir'])
        output_filename = options.get('output_filename', f"video_with_sticker_{helpers.generate_unique_id()}.mp4")
        output_path = os.path.join(output_dir, output_filename)

        helpers.ensure_directory(output_dir)

        video_info = self._get_video_info_for_sticker(video_path)

        validated_sticker = self._validate_sticker_options(sticker, video_info)
        sticker_info = self.get_image_info(validated_sticker['path'])

        scaled_width = round(sticker_info.width * validated_sticker['scale'])
        scaled_height = round(sticker_info.height * validated_sticker['scale'])

        x, y = self._calculate_position(
            validated_sticker['position'],
            video_info['width'],
            video_info['height'],
            scaled_width,
            scaled_height,
            validated_sticker['x'],
            validated_sticker['y']
        )

        end_time = validated_sticker['start_seconds'] + validated_sticker['duration'] \
            if validated_sticker['duration'] else video_info['duration']

        gif_loop_count = 1
        gif_actual_duration = sticker_info.duration or 0
        if validated_sticker['type'] == 'gif' and sticker_info.is_animated and gif_actual_duration > 0:
            display_duration = end_time - validated_sticker['start_seconds']
            gif_loop_count = int(display_duration / gif_actual_duration) + 1

        input_args = ['-i', video_path]
        input_options = []

        if validated_sticker['type'] == 'gif' and sticker_info.is_animated:
            input_options.extend(['-ignore_loop', '0'])

        input_args.extend(input_options)
        input_args.extend(['-i', validated_sticker['path']])

        filter_complex = []

        scale_filter = f'[1:v]scale={scaled_width}:{scaled_height}[scaled_sticker]'
        filter_complex.append(scale_filter)

        sticker_input = 'scaled_sticker'

        if validated_sticker['opacity'] < 1:
            alpha = validated_sticker['opacity']
            opacity_filter = f'[scaled_sticker]colorchannelmixer=aa={alpha}[transparent_sticker]'
            filter_complex.append(opacity_filter)
            sticker_input = 'transparent_sticker'

        enable_option = ''
        if validated_sticker['start_seconds'] > 0 or validated_sticker['duration'] is not None:
            start = validated_sticker['start_seconds']
            end = end_time
            enable_option = f":enable='between(t,{start},{end})'"

        overlay_filter = f"[0:v][{sticker_input}]overlay=x={x}:y={y}{enable_option}[out]"
        filter_complex.append(overlay_filter)

        cmd = [self.ffmpeg_path, '-y'] + input_args + [
            '-filter_complex', ';'.join(filter_complex),
            '-map', '[out]',
            '-map', '0:a?',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'copy',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise Exception(f'添加贴纸失败: {result.stderr.decode("utf-8", errors="ignore")}')

        sticker_result = {
            **validated_sticker,
            'scaled_width': scaled_width,
            'scaled_height': scaled_height,
            'x': x,
            'y': y,
            'width': sticker_info.width,
            'height': sticker_info.height,
            'gif_duration': gif_actual_duration,
            'gif_loop_count': gif_loop_count,
        }

        return StickerResult(
            success=True,
            original_video=video_path,
            output_path=output_path,
            filename=output_filename,
            sticker=sticker_result
        )

    def add_multiple_stickers(self, video_path: str, stickers: List[Dict[str, Any]],
                                options: Optional[Dict[str, Any]] = None) -> MultiStickerResult:
        if not stickers:
            raise Exception('没有提供贴纸')

        options = options or {}
        output_dir = options.get('output_dir', self.options['output_dir'])
        output_filename = options.get('output_filename', f"video_with_stickers_{helpers.generate_unique_id()}.mp4")
        output_path = os.path.join(output_dir, output_filename)

        helpers.ensure_directory(output_dir)

        video_info = self._get_video_info_for_sticker(video_path)

        validated_stickers = []
        stickers_info = []
        has_gif_stickers = []

        for sticker in stickers:
            validated = self._validate_sticker_options(sticker, video_info)
            info = self.get_image_info(validated['path'])
            validated_stickers.append(validated)
            stickers_info.append(info)
            has_gif_stickers.append(validated['type'] == 'gif' and info.is_animated)

        has_any_gif = any(has_gif_stickers)

        input_args = ['-i', video_path]
        input_options = []

        if has_any_gif:
            input_options.extend(['-ignore_loop', '0'])

        input_args.extend(input_options)

        for sticker in validated_stickers:
            input_args.extend(['-i', sticker['path']])

        filter_complex = []
        current_video = '0:v'

        for i, sticker in enumerate(validated_stickers):
            sticker_info = stickers_info[i]
            input_index = i + 1

            scaled_width = round(sticker_info.width * sticker['scale'])
            scaled_height = round(sticker_info.height * sticker['scale'])

            x, y = self._calculate_position(
                sticker['position'],
                video_info['width'],
                video_info['height'],
                scaled_width,
                scaled_height,
                sticker['x'],
                sticker['y']
            )

            end_time = sticker['start_seconds'] + sticker['duration'] \
                if sticker['duration'] else video_info['duration']

            gif_loop_count = 1
            gif_actual_duration = sticker_info.duration or 0
            if sticker['type'] == 'gif' and sticker_info.is_animated and gif_actual_duration > 0:
                display_duration = end_time - sticker['start_seconds']
                gif_loop_count = int(display_duration / gif_actual_duration) + 1

            scaled_label = f'scaled_{i}'
            scale_filter = f'[{input_index}:v]scale={scaled_width}:{scaled_height}[{scaled_label}]'
            filter_complex.append(scale_filter)

            sticker_label = scaled_label

            if sticker['opacity'] < 1:
                alpha = sticker['opacity']
                transparent_label = f'transparent_{i}'
                opacity_filter = f'[{scaled_label}]colorchannelmixer=aa={alpha}[{transparent_label}]'
                filter_complex.append(opacity_filter)
                sticker_label = transparent_label

            enable_option = ''
            if sticker['start_seconds'] > 0 or sticker['duration'] is not None:
                start = sticker['start_seconds']
                end = end_time
                enable_option = f":enable='between(t,{start},{end})'"

            output_label = f'layer_{i}'
            overlay_filter = f"[{current_video}][{sticker_label}]overlay=x={x}:y={y}{enable_option}[{output_label}]"
            filter_complex.append(overlay_filter)

            current_video = output_label

            validated_stickers[i] = {
                **sticker,
                'scaled_width': scaled_width,
                'scaled_height': scaled_height,
                'x': x,
                'y': y,
                'width': sticker_info.width,
                'height': sticker_info.height,
                'gif_duration': gif_actual_duration,
                'gif_loop_count': gif_loop_count,
            }

        cmd = [self.ffmpeg_path, '-y'] + input_args + [
            '-filter_complex', ';'.join(filter_complex),
            '-map', f'[{current_video}]',
            '-map', '0:a?',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'copy',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise Exception(f'添加多个贴纸失败: {result.stderr.decode("utf-8", errors="ignore")}')

        return MultiStickerResult(
            success=True,
            original_video=video_path,
            output_path=output_path,
            filename=output_filename,
            stickers=validated_stickers,
            stickers_count=len(validated_stickers)
        )

    def _get_video_info_for_sticker(self, video_path: str) -> Dict[str, Any]:
        cmd = [
            self.ffprobe_path,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f'无法获取视频信息: {result.stderr}')

        metadata = json.loads(result.stdout)
        format_info = metadata.get('format', {})
        streams = metadata.get('streams', [])
        video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)

        return {
            'width': video_stream.get('width', 1920) if video_stream else 1920,
            'height': video_stream.get('height', 1080) if video_stream else 1080,
            'duration': float(format_info.get('duration', 0)),
        }

    def create_static_sticker_from_gif(self, gif_path: str, frame_index: int = 0,
                                         options: Optional[Dict[str, Any]] = None) -> StaticStickerResult:
        options = options or {}
        output_dir = options.get('output_dir', self.options['output_dir'])
        output_filename = options.get('output_filename', f"static_from_gif_{helpers.generate_unique_id()}.png")
        output_path = os.path.join(output_dir, output_filename)

        helpers.ensure_directory(output_dir)

        if not os.path.exists(gif_path):
            raise Exception(f'GIF文件不存在: {gif_path}')

        gif_info = self.get_image_info(gif_path)
        if not gif_info.is_animated:
            raise Exception('文件不是动画GIF')

        cmd = [
            self.ffmpeg_path, '-y',
            '-i', gif_path,
            '-vf', f'select=eq(n\\,{frame_index})',
            '-vframes', '1',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise Exception(f'从GIF创建静态贴纸失败: {result.stderr.decode("utf-8", errors="ignore")}')

        return StaticStickerResult(
            success=True,
            original_gif=gif_path,
            output_path=output_path,
            filename=output_filename,
            frame_index=frame_index
        )

    def validate_sticker_file(self, sticker_path: str) -> ValidationResult:
        if not os.path.exists(sticker_path):
            return ValidationResult(
                valid=False,
                error=f'文件不存在: {sticker_path}'
            )

        try:
            info = self.get_image_info(sticker_path)

            valid_formats = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp']
            format_valid = info.format and any(f in info.format.lower() for f in valid_formats)

            return ValidationResult(
                valid=format_valid,
                type='gif' if info.is_animated else 'static',
                width=info.width,
                height=info.height,
                is_animated=info.is_animated,
                format=info.format
            )
        except Exception as error:
            return ValidationResult(
                valid=False,
                error=f'无法读取文件: {str(error)}'
            )
