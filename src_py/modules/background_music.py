import os
import json
import subprocess
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src_py.config.config import config
from src_py.utils.helpers import helpers


@dataclass
class AudioInfo:
    duration: float
    size: int
    bitrate: int
    audio: Optional[Dict[str, Any]] = None


@dataclass
class LoopResult:
    success: bool
    original_path: str
    output_path: str
    filename: str
    target_duration: float
    actual_duration: float
    volume: float


@dataclass
class DuckingResult:
    success: bool
    original_path: str
    output_path: str
    filename: str
    ducking_applied: bool
    ducked_segments: int = 0
    ducking_amount: float = 0.0
    reason: Optional[str] = None


@dataclass
class MergeResult:
    success: bool
    output_path: str
    tracks_merged: int


@dataclass
class VolumeResult:
    success: bool
    original_path: str
    output_path: str
    filename: str
    volume: float


@dataclass
class FadeResult:
    success: bool
    original_path: str
    output_path: str
    filename: str
    fade_applied: bool
    fade_in: float = 0.0
    fade_out: float = 0.0
    reason: Optional[str] = None


class BackgroundMusicService:
    def __init__(self, options: Optional[Dict[str, Any]] = None):
        options = options or {}
        self.options = {
            'output_dir': options.get('output_dir', config.temp_dir),
            'default_volume': options.get('default_volume', config.audio['background_music_volume']),
            'ducking_amount': options.get('ducking_amount', config.audio['ducking_amount']),
            'fade_duration': options.get('fade_duration', config.audio['fade_duration']),
            **options,
        }
        self.ffmpeg_path = config.ffmpeg['path']
        self.ffprobe_path = config.ffmpeg['ffprobe_path']

    def get_audio_info(self, audio_path: str) -> AudioInfo:
        if not os.path.exists(audio_path):
            raise Exception(f'音频文件不存在: {audio_path}')

        cmd = [
            self.ffprobe_path,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            audio_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f'无法获取音频信息: {result.stderr}')

        metadata = json.loads(result.stdout)
        format_info = metadata.get('format', {})
        streams = metadata.get('streams', [])
        audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)

        audio_info = None
        if audio_stream:
            audio_info = {
                'codec': audio_stream.get('codec_name'),
                'sample_rate': int(audio_stream.get('sample_rate', 0)) if audio_stream.get('sample_rate') else None,
                'channels': audio_stream.get('channels'),
            }

        return AudioInfo(
            duration=float(format_info.get('duration', 0)),
            size=int(format_info.get('size', 0)),
            bitrate=int(format_info.get('bit_rate', 0)),
            audio=audio_info
        )

    def loop_audio_to_duration(self, audio_path: str, target_duration: float, 
                                 options: Optional[Dict[str, Any]] = None) -> LoopResult:
        audio_info = self.get_audio_info(audio_path)
        options = options or {}
        output_dir = options.get('output_dir', self.options['output_dir'])
        output_filename = options.get('output_filename', f"bgm_looped_{helpers.generate_unique_id()}.mp3")
        output_path = os.path.join(output_dir, output_filename)
        volume = options.get('volume', self.options['default_volume'])
        fade_in = options.get('fade_in', self.options['fade_duration'])
        fade_out = options.get('fade_out', self.options['fade_duration'])

        helpers.ensure_directory(output_dir)

        if audio_info.duration < target_duration:
            loop_count = int(target_duration / audio_info.duration) + 1

            input_args = []
            for _ in range(loop_count):
                input_args.extend(['-i', audio_path])

            filter_complex = []
            input_streams = []
            for i in range(loop_count):
                input_streams.append(f'[{i}:a]')
            filter_complex.append(f"{''.join(input_streams)}concat=n={loop_count}:v=0:a=1[concatenated]")

            filter_complex.append(f'[concatenated]volume={volume}[volumed]')
            filter_complex.append(f'[volumed]atrim=0:{target_duration}[trimmed]')

            fade_filters = []
            if fade_in > 0:
                fade_filters.append(f'afade=t=in:ss=0:d={fade_in}')
            if fade_out > 0:
                fade_filters.append(f'afade=t=out:st={target_duration - fade_out}:d={fade_out}')

            if fade_filters:
                filter_complex.append(f"[trimmed]{','.join(fade_filters)}[final]")
                output_label = 'final'
            else:
                output_label = 'trimmed'

            cmd = [self.ffmpeg_path, '-y'] + input_args + [
                '-filter_complex', ';'.join(filter_complex),
                '-map', f'[{output_label}]',
                '-c:a', 'libmp3lame',
                '-q:a', '2',
                output_path
            ]
        else:
            filter_complex = []
            filter_complex.append(f'[0:a]volume={volume},atrim=0:{target_duration}[trimmed]')

            fade_filters = []
            if fade_in > 0:
                fade_filters.append(f'afade=t=in:ss=0:d={fade_in}')
            if fade_out > 0:
                fade_filters.append(f'afade=t=out:st={target_duration - fade_out}:d={fade_out}')

            if fade_filters:
                filter_complex.append(f"[trimmed]{','.join(fade_filters)}[final]")
                output_label = 'final'
            else:
                output_label = 'trimmed'

            cmd = [
                self.ffmpeg_path, '-y',
                '-i', audio_path,
                '-filter_complex', ';'.join(filter_complex),
                '-map', f'[{output_label}]',
                '-c:a', 'libmp3lame',
                '-q:a', '2',
                output_path
            ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise Exception(f'音频循环处理失败: {result.stderr.decode("utf-8", errors="ignore")}')

        return LoopResult(
            success=True,
            original_path=audio_path,
            output_path=output_path,
            filename=output_filename,
            target_duration=target_duration,
            actual_duration=target_duration,
            volume=volume
        )

    def apply_ducking(self, background_audio_path: str, voice_segments: List[Dict[str, float]],
                        options: Optional[Dict[str, Any]] = None) -> DuckingResult:
        bgm_info = self.get_audio_info(background_audio_path)
        options = options or {}
        output_dir = options.get('output_dir', self.options['output_dir'])
        output_filename = options.get('output_filename', f"bgm_ducked_{helpers.generate_unique_id()}.mp3")
        output_path = os.path.join(output_dir, output_filename)
        ducking_amount = options.get('ducking_amount', self.options['ducking_amount'])
        fade_duration = options.get('fade_duration', 0.5)

        helpers.ensure_directory(output_dir)

        if not voice_segments:
            import shutil
            shutil.copy2(background_audio_path, output_path)
            return DuckingResult(
                success=True,
                original_path=background_audio_path,
                output_path=output_path,
                filename=output_filename,
                ducking_applied=False,
                reason='没有语音片段需要闪避'
            )

        filter_complex = []
        current_stream = '0:a'

        for i, segment in enumerate(voice_segments):
            start_time = segment['start_time']
            end_time = segment['end_time']
            duration = end_time - start_time

            duck_start_time = max(0.0, start_time - fade_duration)
            duck_end_time = end_time + fade_duration
            duck_duration = duck_end_time - duck_start_time

            filter_name = f'duck_{i}'
            volume_expression = self._create_ducking_volume_expression(
                start_time,
                end_time,
                ducking_amount,
                fade_duration
            )

            escaped_expression = volume_expression.replace(',', '\\,')
            filter_complex.append(f'[{current_stream}]volume=eval=frame:volume={escaped_expression}[{filter_name}]')
            current_stream = filter_name

        cmd = [
            self.ffmpeg_path, '-y',
            '-i', background_audio_path,
            '-filter_complex', ';'.join(filter_complex),
            '-map', f'[{current_stream}]',
            '-c:a', 'libmp3lame',
            '-q:a', '2',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise Exception(f'闪避效果处理失败: {result.stderr.decode("utf-8", errors="ignore")}')

        return DuckingResult(
            success=True,
            original_path=background_audio_path,
            output_path=output_path,
            filename=output_filename,
            ducking_applied=True,
            ducked_segments=len(voice_segments),
            ducking_amount=ducking_amount
        )

    def _create_ducking_volume_expression(self, start_time: float, end_time: float, 
                                             ducking_amount: float, fade_duration: float) -> str:
        fade_in_start = max(0.0, start_time - fade_duration)
        fade_in_end = start_time
        fade_out_start = end_time
        fade_out_end = end_time + fade_duration

        volume_reduction = 1 - ducking_amount

        actual_fade_in_duration = fade_in_end - fade_in_start

        fade_out_expr = f'(1-{volume_reduction})*({fade_out_end}-t)/{fade_duration}+{volume_reduction}'

        if actual_fade_in_duration <= 0:
            return (
                f'if(between(t, {fade_in_end}, {fade_out_start}),'
                f'{volume_reduction},'
                f'if(between(t, {fade_out_start}, {fade_out_end}),'
                f'{fade_out_expr},'
                f'1))'
            )

        fade_in_expr = f'(1-{volume_reduction})*(t-{fade_in_start})/{actual_fade_in_duration}+{volume_reduction}'

        return (
            f'if(between(t, {fade_in_start}, {fade_in_end}),'
            f'{fade_in_expr},'
            f'if(between(t, {fade_in_end}, {fade_out_start}),'
            f'{volume_reduction},'
            f'if(between(t, {fade_out_start}, {fade_out_end}),'
            f'{fade_out_expr},'
            f'1)))'
        )

    def merge_audio_tracks(self, audio_tracks: List[Dict[str, Any]], 
                             output_path: str, options: Optional[Dict[str, Any]] = None) -> MergeResult:
        if not audio_tracks:
            raise Exception('没有提供要合并的音频轨道')

        output_dir = os.path.dirname(output_path) or self.options['output_dir']
        helpers.ensure_directory(output_dir)

        input_args = []
        for track in audio_tracks:
            input_args.extend(['-i', track['path']])

        filter_complex = []
        amix_inputs = []

        for i, track in enumerate(audio_tracks):
            volume = track.get('volume', 1.0)
            delay = track.get('delay', 0.0)

            if volume != 1.0 or delay > 0:
                filters = []
                if volume != 1.0:
                    filters.append(f'volume={volume}')
                if delay > 0:
                    filters.append(f'adelay={int(delay * 1000)}|{int(delay * 1000)}')

                filter_name = f'track_{i}'
                filter_complex.append(f"[{i}:a]{','.join(filters)}[{filter_name}]")
                amix_inputs.append(f'[{filter_name}]')
            else:
                amix_inputs.append(f'[{i}:a]')

        mix_filter = f"{''.join(amix_inputs)}amix=inputs={len(audio_tracks)}:duration=longest[out]"
        filter_complex.append(mix_filter)

        cmd = [self.ffmpeg_path, '-y'] + input_args + [
            '-filter_complex', ';'.join(filter_complex),
            '-map', '[out]',
            '-c:a', 'libmp3lame',
            '-q:a', '2',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise Exception(f'音频合并失败: {result.stderr.decode("utf-8", errors="ignore")}')

        return MergeResult(
            success=True,
            output_path=output_path,
            tracks_merged=len(audio_tracks)
        )

    def adjust_volume(self, audio_path: str, volume: float, 
                       options: Optional[Dict[str, Any]] = None) -> VolumeResult:
        options = options or {}
        output_dir = options.get('output_dir', self.options['output_dir'])
        output_filename = options.get('output_filename', f"audio_vol_{helpers.generate_unique_id()}.mp3")
        output_path = os.path.join(output_dir, output_filename)

        helpers.ensure_directory(output_dir)

        cmd = [
            self.ffmpeg_path, '-y',
            '-i', audio_path,
            '-af', f'volume={volume}',
            '-c:a', 'libmp3lame',
            '-q:a', '2',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise Exception(f'音量调整失败: {result.stderr.decode("utf-8", errors="ignore")}')

        return VolumeResult(
            success=True,
            original_path=audio_path,
            output_path=output_path,
            filename=output_filename,
            volume=volume
        )

    def add_fade_effects(self, audio_path: str, options: Optional[Dict[str, Any]] = None) -> FadeResult:
        audio_info = self.get_audio_info(audio_path)
        options = options or {}
        output_dir = options.get('output_dir', self.options['output_dir'])
        output_filename = options.get('output_filename', f"audio_fade_{helpers.generate_unique_id()}.mp3")
        output_path = os.path.join(output_dir, output_filename)
        fade_in = options.get('fade_in', self.options['fade_duration'])
        fade_out = options.get('fade_out', self.options['fade_duration'])

        helpers.ensure_directory(output_dir)

        filters = []

        if fade_in > 0:
            filters.append(f'afade=t=in:ss=0:d={fade_in}')

        if fade_out > 0:
            fade_out_start = audio_info.duration - fade_out
            if fade_out_start > 0:
                filters.append(f'afade=t=out:st={fade_out_start}:d={fade_out}')

        if not filters:
            import shutil
            shutil.copy2(audio_path, output_path)
            return FadeResult(
                success=True,
                original_path=audio_path,
                output_path=output_path,
                filename=output_filename,
                fade_applied=False,
                reason='没有指定淡入淡出效果'
            )

        cmd = [
            self.ffmpeg_path, '-y',
            '-i', audio_path,
            '-af', ','.join(filters),
            '-c:a', 'libmp3lame',
            '-q:a', '2',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise Exception(f'淡入淡出效果处理失败: {result.stderr.decode("utf-8", errors="ignore")}')

        return FadeResult(
            success=True,
            original_path=audio_path,
            output_path=output_path,
            filename=output_filename,
            fade_applied=True,
            fade_in=fade_in,
            fade_out=fade_out
        )
