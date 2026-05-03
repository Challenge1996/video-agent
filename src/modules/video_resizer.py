import os
import subprocess
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

from src.config.config import config
from src.utils.helpers import helpers


@dataclass
class AspectRatio:
    ratio: str
    width: int
    height: int

    @property
    def value(self) -> float:
        return self.width / self.height


COMMON_ASPECT_RATIOS = {
    '9:16': AspectRatio('9:16', 9, 16),
    '16:9': AspectRatio('16:9', 16, 9),
    '1:1': AspectRatio('1:1', 1, 1),
    '4:3': AspectRatio('4:3', 4, 3),
    '3:4': AspectRatio('3:4', 3, 4),
}

COMMON_RESOLUTIONS = {
    '1080p': (1920, 1080),
    '720p': (1280, 720),
    '480p': (854, 480),
    '360p': (640, 360),
    '4k': (3840, 2160),
    '1080x1920': (1080, 1920),
    '720x1280': (720, 1280),
}


@dataclass
class VideoResizeResult:
    success: bool
    output_path: str
    original_width: int
    original_height: int
    output_width: int
    output_height: int
    original_aspect_ratio: str
    output_aspect_ratio: str
    operation: str
    error: Optional[str] = None


@dataclass
class VideoCropResult:
    success: bool
    output_path: str
    original_width: int
    original_height: int
    crop_x: int
    crop_y: int
    crop_width: int
    crop_height: int
    error: Optional[str] = None


@dataclass
class AspectRatioResult:
    success: bool
    output_path: str
    original_width: int
    original_height: int
    original_aspect_ratio: str
    target_aspect_ratio: str
    output_width: int
    output_height: int
    method: str
    error: Optional[str] = None


class VideoResizer:
    def __init__(self, options: Optional[Dict[str, Any]] = None):
        options = options or {}
        self.options = {
            'output_dir': options.get('output_dir', config.output_dir),
            'temp_dir': options.get('temp_dir', config.temp_dir),
            **options,
        }
        self.ffmpeg_path = config.ffmpeg['path']
        self.ffprobe_path = config.ffmpeg['ffprobe_path']
        helpers.ensure_directory(self.options['output_dir'])
        helpers.ensure_directory(self.options['temp_dir'])

    def _get_video_dimensions(self, video_path: str) -> Tuple[int, int]:
        from src.modules.video_splitter import VideoSplitter
        splitter = VideoSplitter()
        info = splitter.get_video_info(video_path)
        width = info.video.get('width', 0)
        height = info.video.get('height', 0)
        return width, height

    def _calculate_aspect_ratio(self, width: int, height: int) -> str:
        def gcd(a: int, b: int) -> int:
            while b:
                a, b = b, a % b
            return a
        
        g = gcd(width, height)
        ratio_w = width // g
        ratio_h = height // g
        
        for name, ar in COMMON_ASPECT_RATIOS.items():
            if (ratio_w == ar.width and ratio_h == ar.height) or \
               (abs(ratio_w / ratio_h - ar.width / ar.height) < 0.01):
                return name
        
        simplified_gcd = gcd(ratio_w, ratio_h)
        return f"{ratio_w // simplified_gcd}:{ratio_h // simplified_gcd}"

    def _generate_output_path(self, input_path: str, suffix: str, 
                               output_dir: Optional[str] = None) -> str:
        base_name = helpers.get_file_name_without_extension(input_path)
        ext = os.path.splitext(input_path)[1] or '.mp4'
        output_name = f"{base_name}_{suffix}{ext}"
        output_directory = output_dir or self.options['output_dir']
        return os.path.join(output_directory, output_name)

    def resize_video(self, video_path: str, 
                     target_width: Optional[int] = None,
                     target_height: Optional[int] = None,
                     resolution: Optional[str] = None,
                     options: Optional[Dict[str, Any]] = None) -> VideoResizeResult:
        options = options or {}
        
        if not os.path.exists(video_path):
            raise Exception(f'视频文件不存在: {video_path}')
        
        original_width, original_height = self._get_video_dimensions(video_path)
        original_aspect = self._calculate_aspect_ratio(original_width, original_height)
        
        if resolution:
            resolution = resolution.lower()
            if resolution in COMMON_RESOLUTIONS:
                target_width, target_height = COMMON_RESOLUTIONS[resolution]
            else:
                parts = resolution.lower().split('x')
                if len(parts) == 2:
                    try:
                        target_width = int(parts[0])
                        target_height = int(parts[1])
                    except ValueError:
                        raise Exception(f'无效的分辨率格式: {resolution}')
        
        if target_width is None and target_height is None:
            raise Exception('必须指定目标宽度或高度')
        
        if target_width and target_height:
            output_width = target_width
            output_height = target_height
        elif target_width:
            aspect_ratio = original_width / original_height
            output_width = target_width
            output_height = int(target_width / aspect_ratio)
        else:
            aspect_ratio = original_width / original_height
            output_height = target_height
            output_width = int(target_height * aspect_ratio)
        
        if output_width % 2 != 0:
            output_width -= 1
        if output_height % 2 != 0:
            output_height -= 1
        
        output_aspect = self._calculate_aspect_ratio(output_width, output_height)
        output_path = self._generate_output_path(
            video_path, 
            f"{output_width}x{output_height}",
            options.get('output_dir')
        )
        
        vf_filter = f"scale={output_width}:{output_height}:flags=lanczos"
        
        cmd = [
            self.ffmpeg_path, '-y',
            '-i', video_path,
            '-vf', vf_filter,
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-preset', options.get('preset', 'medium'),
            '-crf', str(options.get('crf', 23)),
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            error_msg = result.stderr.decode('utf-8', errors='ignore')
            return VideoResizeResult(
                success=False,
                output_path=output_path,
                original_width=original_width,
                original_height=original_height,
                output_width=output_width,
                output_height=output_height,
                original_aspect_ratio=original_aspect,
                output_aspect_ratio=output_aspect,
                operation='resize',
                error=error_msg
            )
        
        return VideoResizeResult(
            success=True,
            output_path=output_path,
            original_width=original_width,
            original_height=original_height,
            output_width=output_width,
            output_height=output_height,
            original_aspect_ratio=original_aspect,
            output_aspect_ratio=output_aspect,
            operation='resize'
        )

    def crop_video(self, video_path: str,
                   crop_width: Optional[int] = None,
                   crop_height: Optional[int] = None,
                   crop_x: Optional[int] = None,
                   crop_y: Optional[int] = None,
                   aspect_ratio: Optional[str] = None,
                   options: Optional[Dict[str, Any]] = None) -> VideoCropResult:
        options = options or {}
        
        if not os.path.exists(video_path):
            raise Exception(f'视频文件不存在: {video_path}')
        
        original_width, original_height = self._get_video_dimensions(video_path)
        
        if aspect_ratio:
            if aspect_ratio not in COMMON_ASPECT_RATIOS:
                raise Exception(f'不支持的画幅比: {aspect_ratio}。支持: {list(COMMON_ASPECT_RATIOS.keys())}')
            
            target_ar = COMMON_ASPECT_RATIOS[aspect_ratio]
            target_ratio = target_ar.width / target_ar.height
            current_ratio = original_width / original_height
            
            if abs(current_ratio - target_ratio) < 0.01:
                return VideoCropResult(
                    success=True,
                    output_path=video_path,
                    original_width=original_width,
                    original_height=original_height,
                    crop_x=0,
                    crop_y=0,
                    crop_width=original_width,
                    crop_height=original_height
                )
            
            if current_ratio > target_ratio:
                new_width = int(original_height * target_ratio)
                new_height = original_height
                new_x = (original_width - new_width) // 2
                new_y = 0
            else:
                new_height = int(original_width / target_ratio)
                new_width = original_width
                new_x = 0
                new_y = (original_height - new_height) // 2
            
            crop_width = new_width
            crop_height = new_height
            crop_x = new_x
            crop_y = new_y
        
        if crop_width is None or crop_height is None:
            raise Exception('必须指定裁剪宽高或画幅比')
        
        if crop_x is None:
            crop_x = (original_width - crop_width) // 2
        if crop_y is None:
            crop_y = (original_height - crop_height) // 2
        
        if crop_x < 0 or crop_y < 0:
            raise Exception('裁剪位置不能为负数')
        if crop_x + crop_width > original_width:
            raise Exception(f'裁剪宽度超出视频范围: 视频宽度 {original_width}, 裁剪宽度 {crop_width} at x={crop_x}')
        if crop_y + crop_height > original_height:
            raise Exception(f'裁剪高度超出视频范围: 视频高度 {original_height}, 裁剪高度 {crop_height} at y={crop_y}')
        
        output_path = self._generate_output_path(
            video_path, 
            f"cropped_{crop_width}x{crop_height}",
            options.get('output_dir')
        )
        
        vf_filter = f"crop={crop_width}:{crop_height}:{crop_x}:{crop_y}"
        
        cmd = [
            self.ffmpeg_path, '-y',
            '-i', video_path,
            '-vf', vf_filter,
            '-c:a', 'copy',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            error_msg = result.stderr.decode('utf-8', errors='ignore')
            return VideoCropResult(
                success=False,
                output_path=output_path,
                original_width=original_width,
                original_height=original_height,
                crop_x=crop_x,
                crop_y=crop_y,
                crop_width=crop_width,
                crop_height=crop_height,
                error=error_msg
            )
        
        return VideoCropResult(
            success=True,
            output_path=output_path,
            original_width=original_width,
            original_height=original_height,
            crop_x=crop_x,
            crop_y=crop_y,
            crop_width=crop_width,
            crop_height=crop_height
        )

    def convert_aspect_ratio(self, video_path: str,
                              target_aspect: str,
                              method: str = 'crop',
                              target_resolution: Optional[str] = None,
                              pad_color: str = 'black',
                              options: Optional[Dict[str, Any]] = None) -> AspectRatioResult:
        options = options or {}
        
        if not os.path.exists(video_path):
            raise Exception(f'视频文件不存在: {video_path}')
        
        if target_aspect not in COMMON_ASPECT_RATIOS:
            raise Exception(f'不支持的画幅比: {target_aspect}。支持: {list(COMMON_ASPECT_RATIOS.keys())}')
        
        if method not in ['crop', 'pad']:
            raise Exception("方法必须是 'crop' (中心裁剪) 或 'pad' (加黑边)")
        
        original_width, original_height = self._get_video_dimensions(video_path)
        original_aspect = self._calculate_aspect_ratio(original_width, original_height)
        
        target_ar = COMMON_ASPECT_RATIOS[target_aspect]
        target_ratio = target_ar.width / target_ar.height
        current_ratio = original_width / original_height
        
        if abs(current_ratio - target_ratio) < 0.01:
            return AspectRatioResult(
                success=True,
                output_path=video_path,
                original_width=original_width,
                original_height=original_height,
                original_aspect_ratio=original_aspect,
                target_aspect_ratio=target_aspect,
                output_width=original_width,
                output_height=original_height,
                method='none'
            )
        
        if target_resolution:
            if target_resolution in COMMON_RESOLUTIONS:
                output_width, output_height = COMMON_RESOLUTIONS[target_resolution]
            else:
                parts = target_resolution.lower().split('x')
                if len(parts) == 2:
                    output_width = int(parts[0])
                    output_height = int(parts[1])
                else:
                    raise Exception(f'无效的分辨率格式: {target_resolution}')
            
            output_ratio = output_width / output_height
            if abs(output_ratio - target_ratio) > 0.01:
                raise Exception(f"目标分辨率 {target_resolution} 的画幅比 ({output_ratio:.2f}) 与目标画幅比 {target_aspect} ({target_ratio:.2f}) 不匹配")
        else:
            if method == 'crop':
                if current_ratio > target_ratio:
                    output_height = original_height
                    output_width = int(original_height * target_ratio)
                else:
                    output_width = original_width
                    output_height = int(original_width / target_ratio)
            else:
                if current_ratio > target_ratio:
                    output_width = original_width
                    output_height = int(original_width / target_ratio)
                else:
                    output_height = original_height
                    output_width = int(original_height * target_ratio)
        
        if output_width % 2 != 0:
            output_width -= 1
        if output_height % 2 != 0:
            output_height -= 1
        
        output_path = self._generate_output_path(
            video_path, 
            f"aspect_{target_aspect.replace(':', '_')}_{method}",
            options.get('output_dir')
        )
        
        if method == 'crop':
            if current_ratio > target_ratio:
                crop_width = output_width
                crop_height = original_height
                crop_x = (original_width - crop_width) // 2
                crop_y = 0
            else:
                crop_width = original_width
                crop_height = output_height
                crop_x = 0
                crop_y = (original_height - crop_height) // 2
            
            vf_filter = f"crop={crop_width}:{crop_height}:{crop_x}:{crop_y}"
            
            if (crop_width != output_width or crop_height != output_height) and target_resolution:
                vf_filter += f",scale={output_width}:{output_height}:flags=lanczos"
        else:
            if current_ratio > target_ratio:
                scale_width = output_width
                scale_height = int(output_width * (original_height / original_width))
                pad_x = 0
                pad_y = (output_height - scale_height) // 2
            else:
                scale_height = output_height
                scale_width = int(output_height * (original_width / original_height))
                pad_x = (output_width - scale_width) // 2
                pad_y = 0
            
            if scale_width % 2 != 0:
                scale_width -= 1
            if scale_height % 2 != 0:
                scale_height -= 1
            
            color_hex = {
                'black': '#000000',
                'white': '#FFFFFF',
                'gray': '#808080',
                'transparent': '#000000@0',
            }.get(pad_color.lower(), pad_color)
            
            vf_filter = f"scale={scale_width}:{scale_height}:flags=lanczos,pad={output_width}:{output_height}:{pad_x}:{pad_y}:color={color_hex}"
        
        cmd = [
            self.ffmpeg_path, '-y',
            '-i', video_path,
            '-vf', vf_filter,
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-preset', options.get('preset', 'medium'),
            '-crf', str(options.get('crf', 23)),
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            error_msg = result.stderr.decode('utf-8', errors='ignore')
            return AspectRatioResult(
                success=False,
                output_path=output_path,
                original_width=original_width,
                original_height=original_height,
                original_aspect_ratio=original_aspect,
                target_aspect_ratio=target_aspect,
                output_width=output_width,
                output_height=output_height,
                method=method,
                error=error_msg
            )
        
        return AspectRatioResult(
            success=True,
            output_path=output_path,
            original_width=original_width,
            original_height=original_height,
            original_aspect_ratio=original_aspect,
            target_aspect_ratio=target_aspect,
            output_width=output_width,
            output_height=output_height,
            method=method
        )

    def convert_to_douyin_format(self, video_path: str,
                                  method: str = 'crop',
                                  target_resolution: str = '720x1280',
                                  options: Optional[Dict[str, Any]] = None) -> AspectRatioResult:
        return self.convert_aspect_ratio(
            video_path=video_path,
            target_aspect='9:16',
            method=method,
            target_resolution=target_resolution,
            options=options
        )

    def get_video_resolution_info(self, video_path: str) -> Dict[str, Any]:
        width, height = self._get_video_dimensions(video_path)
        aspect_ratio = self._calculate_aspect_ratio(width, height)
        
        return {
            'width': width,
            'height': height,
            'aspect_ratio': aspect_ratio,
            'resolution': f"{width}x{height}",
            'orientation': 'landscape' if width > height else ('portrait' if height > width else 'square')
        }
