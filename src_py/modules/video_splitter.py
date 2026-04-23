import os
import json
import subprocess
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from src_py.config.config import config
from src_py.utils.helpers import helpers


@dataclass
class VideoInfo:
    duration: float
    size: int
    bitrate: int
    video: Dict[str, Any]
    audio: Optional[Dict[str, Any]] = None


@dataclass
class AudioVolumeInfo:
    mean_volume: Optional[float]
    max_volume: Optional[float]
    has_audio: bool


@dataclass
class VideoSegment:
    index: int
    start_time: float
    end_time: float
    duration: float
    path: str
    filename: str


class VideoSplitter:
    def __init__(self, options: Optional[Dict[str, Any]] = None):
        options = options or {}
        self.options = {
            'segment_duration': options.get('segment_duration', config.video['default_segment_duration']),
            'output_dir': options.get('output_dir', config.temp_dir),
            **options,
        }
        self.ffmpeg_path = config.ffmpeg['path']
        self.ffprobe_path = config.ffmpeg['ffprobe_path']

    def _run_ffprobe(self, file_path: str) -> Dict[str, Any]:
        cmd = [
            self.ffprobe_path,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f'ffprobe failed: {result.stderr}')
        return json.loads(result.stdout)

    def get_video_info(self, video_path: str) -> VideoInfo:
        if not os.path.exists(video_path):
            raise Exception(f'视频文件不存在: {video_path}')

        metadata = self._run_ffprobe(video_path)
        format_info = metadata.get('format', {})
        streams = metadata.get('streams', [])

        video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
        audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)

        duration = float(format_info.get('duration', 0))
        size = int(format_info.get('size', 0))
        bitrate = int(format_info.get('bit_rate', 0))

        video_info = {
            'codec': video_stream.get('codec_name') if video_stream else None,
            'width': video_stream.get('width') if video_stream else None,
            'height': video_stream.get('height') if video_stream else None,
            'fps': self._parse_frame_rate(video_stream.get('avg_frame_rate')) if video_stream else config.video['default_fps'],
        }

        audio_info = None
        if audio_stream:
            audio_info = {
                'codec': audio_stream.get('codec_name'),
                'sample_rate': int(audio_stream.get('sample_rate', 0)) if audio_stream.get('sample_rate') else None,
                'channels': audio_stream.get('channels'),
            }

        return VideoInfo(
            duration=duration,
            size=size,
            bitrate=bitrate,
            video=video_info,
            audio=audio_info
        )

    def _parse_frame_rate(self, frame_rate_str: str) -> float:
        if not frame_rate_str or frame_rate_str == '0/0':
            return config.video['default_fps']
        parts = frame_rate_str.split('/')
        if len(parts) == 2:
            return float(parts[0]) / float(parts[1])
        return float(frame_rate_str)

    def split_video(self, video_path: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        options = options or {}
        video_info = self.get_video_info(video_path)
        segment_duration = options.get('segment_duration', self.options['segment_duration'])
        output_dir = options.get('output_dir', self.options['output_dir'])
        base_name = helpers.get_file_name_without_extension(video_path)

        helpers.ensure_directory(output_dir)

        segments = helpers.calculate_video_segments(video_info.duration, segment_duration)
        output_files = []

        for segment in segments:
            output_filename = f"{base_name}_segment_{str(segment['index']).zfill(3)}.mp4"
            output_path = os.path.join(output_dir, output_filename)

            self._extract_segment(video_path, output_path, segment['start_time'], segment['duration'])

            output_files.append(VideoSegment(
                index=segment['index'],
                start_time=segment['start_time'],
                end_time=segment['end_time'],
                duration=segment['duration'],
                path=output_path,
                filename=output_filename
            ))

        return {
            'original_video': video_path,
            'original_info': video_info,
            'segments': output_files,
            'segment_count': len(output_files),
        }

    def _extract_segment(self, input_path: str, output_path: str, start_time: float, duration: float):
        cmd = [
            self.ffmpeg_path,
            '-y',
            '-i', input_path,
            '-ss', str(start_time),
            '-t', str(duration),
            '-c:v', 'copy',
            '-c:a', 'copy',
            '-avoid_negative_ts', 'make_zero',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise Exception(f'视频分割失败: {result.stderr.decode("utf-8", errors="ignore")}')

    def split_by_custom_intervals(self, video_path: str, intervals: List[Dict[str, float]], 
                                    output_dir: Optional[str] = None) -> Dict[str, Any]:
        video_info = self.get_video_info(video_path)
        output_directory = output_dir or self.options['output_dir']
        base_name = helpers.get_file_name_without_extension(video_path)

        helpers.ensure_directory(output_directory)

        output_files = []

        for i, interval in enumerate(intervals):
            start_time = interval['start_time']
            duration = interval['end_time'] - interval['start_time']

            output_filename = f"{base_name}_segment_{str(i).zfill(3)}.mp4"
            output_path = os.path.join(output_directory, output_filename)

            if start_time < 0 or start_time + duration > video_info.duration:
                raise Exception(
                    f'时间区间超出视频范围: 开始 {start_time}, 时长 {duration}, 视频总长 {video_info.duration}'
                )

            self._extract_segment(video_path, output_path, start_time, duration)

            output_files.append(VideoSegment(
                index=i,
                start_time=start_time,
                end_time=interval['end_time'],
                duration=duration,
                path=output_path,
                filename=output_filename
            ))

        return {
            'original_video': video_path,
            'original_info': video_info,
            'segments': output_files,
            'segment_count': len(output_files),
        }

    def merge_videos(self, video_paths: List[str], output_path: str, options: Optional[Dict[str, Any]] = None) -> str:
        if not video_paths:
            raise Exception('没有提供要合并的视频文件')

        options = options or {}
        concat_file = self._create_concat_file(video_paths)

        cmd = [
            self.ffmpeg_path,
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c:v', 'copy',
            '-c:a', 'copy',
            output_path
        ]

        if options.get('video_codec') and options['video_codec'] != 'copy':
            cmd[cmd.index('-c:v') + 1] = options['video_codec']
        if options.get('audio_codec') and options['audio_codec'] != 'copy':
            cmd[cmd.index('-c:a') + 1] = options['audio_codec']

        try:
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode != 0:
                raise Exception(f'视频合并失败: {result.stderr.decode("utf-8", errors="ignore")}')
        finally:
            if os.path.exists(concat_file):
                os.unlink(concat_file)

        return output_path

    def _escape_path_for_ffmpeg(self, path: str) -> str:
        return path.replace("'", "'\\''")

    def _create_concat_file(self, video_paths: List[str]) -> str:
        temp_dir = config.temp_dir
        helpers.ensure_directory(temp_dir)

        concat_file_path = os.path.join(temp_dir, f"concat_{helpers.generate_unique_id()}.txt")
        content = '\n'.join([f"file '{self._escape_path_for_ffmpeg(path)}'" for path in video_paths])

        with open(concat_file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return concat_file_path

    def get_audio_volume(self, video_path: str) -> AudioVolumeInfo:
        cmd = [
            self.ffmpeg_path,
            '-i', video_path,
            '-af', 'volumedetect',
            '-f', 'null',
            '-vn',
            '-'
        ]

        result = subprocess.run(cmd, capture_output=True)
        stderr_output = result.stderr.decode('utf-8', errors='ignore')

        mean_volume_match = re.search(r'mean_volume:\s*(-?[\d.]+)', stderr_output)
        max_volume_match = re.search(r'max_volume:\s*(-?[\d.]+)', stderr_output)

        mean_volume = float(mean_volume_match.group(1)) if mean_volume_match else None
        max_volume = float(max_volume_match.group(1)) if max_volume_match else None

        return AudioVolumeInfo(
            mean_volume=mean_volume,
            max_volume=max_volume,
            has_audio=mean_volume is not None
        )
