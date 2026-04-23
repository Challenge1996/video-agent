import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import subprocess

from src_py.config.config import config
from src_py.utils.helpers import helpers
from src_py.modules.video_splitter import VideoSplitter
from src_py.modules.tts_service import TTSService
from src_py.modules.minimax_tts_service import MiniMaxTTSService
from src_py.modules.subtitle_generator import SubtitleGenerator
from src_py.modules.background_music import BackgroundMusicService
from src_py.modules.sticker_service import StickerService


@dataclass
class ComposeResult:
    success: bool
    output_path: str
    filename: str
    original_video: str
    video_info: Dict[str, Any]
    tts_added: bool
    subtitles_added: bool
    background_music_added: bool
    stickers_added: bool


class VideoComposer:
    def __init__(self, options: Optional[Dict[str, Any]] = None):
        options = options or {}
        self.options = {
            'output_dir': options.get('output_dir', config.output_dir),
            'temp_dir': options.get('temp_dir', config.temp_dir),
            'tts_provider': options.get('tts_provider', config.tts['provider']),
            **options,
        }

        self.video_splitter = VideoSplitter({
            'output_dir': self.options['temp_dir'],
            **options.get('video_splitter_options', {}),
        })

        self.tts_service = self._create_tts_service(options)

        self.subtitle_generator = SubtitleGenerator({
            'output_dir': self.options['temp_dir'],
            **options.get('subtitle_options', {}),
        })

        self.background_music_service = BackgroundMusicService({
            'output_dir': self.options['temp_dir'],
            **options.get('background_music_options', {}),
        })

        self.sticker_service = StickerService({
            'output_dir': self.options['temp_dir'],
            **options.get('sticker_options', {}),
        })

        helpers.ensure_directory(self.options['output_dir'])
        helpers.ensure_directory(self.options['temp_dir'])

        self.ffmpeg_path = config.ffmpeg['path']
        self.ffprobe_path = config.ffmpeg['ffprobe_path']

    def _create_tts_service(self, options: Dict[str, Any]):
        provider = options.get('tts_provider', config.tts['provider'])

        if provider == 'minimax':
            return MiniMaxTTSService({
                'output_dir': self.options['temp_dir'],
                **options.get('tts_options', {}),
            })
        elif provider == 'google':
            return TTSService({
                'output_dir': self.options['temp_dir'],
                **options.get('tts_options', {}),
            })
        else:
            print(f'警告: 未知的 TTS 提供商: {provider}，默认使用 MiniMax')
            return MiniMaxTTSService({
                'output_dir': self.options['temp_dir'],
                **options.get('tts_options', {}),
            })

    def compose_video(self, options: Dict[str, Any]) -> ComposeResult:
        video_path = options.get('video_path')
        text_content = options.get('text_content')
        background_music_path = options.get('background_music_path')
        segment_duration = options.get('segment_duration')
        output_file_name = options.get('output_file_name')
        add_subtitles = options.get('add_subtitles', True)
        add_background_music = options.get('add_background_music', True)
        add_tts = options.get('add_tts', True)
        add_stickers = options.get('add_stickers', True)
        stickers = options.get('stickers', [])
        subtitle_options = options.get('subtitle_options', {})
        tts_options = options.get('tts_options', {})
        bgm_options = options.get('bgm_options', {})
        sticker_options = options.get('sticker_options', {})

        if not video_path:
            raise Exception('必须提供视频路径')

        if not os.path.exists(video_path):
            raise Exception(f'视频文件不存在: {video_path}')

        video_info = self.video_splitter.get_video_info(video_path)
        base_output_name = output_file_name or f"composed_{helpers.generate_unique_id()}"
        final_output_path = os.path.join(self.options['output_dir'], f"{base_output_name}.mp4")

        print('正在检测视频原声音量...')
        original_audio_volume = self._detect_original_audio_volume(video_path)

        has_tts = add_tts and text_content
        has_background_music = add_background_music and background_music_path and os.path.exists(background_music_path)

        audio_priority_config = self._calculate_audio_priority(
            has_tts,
            has_background_music,
            original_audio_volume,
            video_info.audio is not None
        )

        print(f'音频优先级配置: {audio_priority_config}')

        current_video_path = video_path
        audio_tracks = []
        subtitle_path = None

        if add_tts and text_content:
            print('正在生成 TTS 语音...')
            tts_results = self._generate_tts(text_content, tts_options)

            if add_subtitles:
                print('正在生成字幕...')
                successful_results = [r for r in tts_results.results if r.success]
                tts_results_dict = [
                    {'text': r.text, 'duration': r.duration, 'audio_path': r.audio_path}
                    for r in successful_results
                ]
                subtitle_data = self.subtitle_generator.generate_srt_from_tts_results(
                    tts_results_dict,
                    subtitle_options
                )
                subtitle_save_result = self.subtitle_generator.save_srt(
                    subtitle_data,
                    os.path.join(self.options['temp_dir'], f"{base_output_name}.srt")
                )
                subtitle_path = subtitle_save_result['path']

            tts_audio_tracks = [
                {
                    'path': r.audio_path,
                    'volume': config.audio['tts_volume'],
                    'delay': getattr(r, 'start_time', 0) or 0,
                    'type': 'tts',
                }
                for r in tts_results.results if r.success
            ]
            audio_tracks.extend(tts_audio_tracks)

        if has_background_music:
            print('正在处理背景音乐...')
            bgm_result = self._process_background_music(
                background_music_path,
                video_info.duration,
                audio_tracks,
                {
                    **bgm_options,
                    'volume': audio_priority_config['background_music_volume'],
                }
            )

            audio_tracks.append({
                'path': bgm_result.output_path,
                'volume': 1.0,
                'delay': 0,
                'type': 'bgm',
            })

        if audio_tracks or audio_priority_config['use_original_audio']:
            print('正在将音频添加到视频...')
            video_with_audio_path = os.path.join(
                self.options['temp_dir'],
                f"video_with_audio_{helpers.generate_unique_id()}.mp4"
            )

            has_tts_audio = has_tts and any(t['type'] == 'tts' for t in audio_tracks)
            has_bgm_audio = has_background_music and any(t['type'] == 'bgm' for t in audio_tracks)

            current_video_path = self._add_multiple_audio_tracks_to_video(
                current_video_path,
                audio_tracks,
                video_with_audio_path,
                audio_priority_config,
                {
                    'has_tts_audio': has_tts_audio,
                    'has_bgm_audio': has_bgm_audio,
                }
            )

        if subtitle_path and os.path.exists(subtitle_path):
            print('正在添加字幕...')
            video_with_subtitles_path = os.path.join(
                self.options['temp_dir'],
                f"video_with_subtitles_{helpers.generate_unique_id()}.mp4"
            )
            current_video_path = self._add_subtitles_to_video(
                current_video_path,
                subtitle_path,
                video_with_subtitles_path,
                subtitle_options
            )

        stickers_added = False
        if add_stickers and stickers:
            print('正在添加贴纸...')
            video_with_stickers_path = os.path.join(
                self.options['temp_dir'],
                f"video_with_stickers_{helpers.generate_unique_id()}.mp4"
            )
            sticker_result = self.sticker_service.add_multiple_stickers(
                current_video_path,
                stickers,
                {
                    'output_dir': self.options['temp_dir'],
                    'output_filename': os.path.basename(video_with_stickers_path),
                    **sticker_options,
                }
            )
            current_video_path = sticker_result.output_path
            stickers_added = True

        if current_video_path != final_output_path:
            shutil.copy2(current_video_path, final_output_path)

        if options.get('cleanup', True):
            self._cleanup_temp_files()

        video_info_dict = {
            'duration': video_info.duration,
            'size': video_info.size,
            'bitrate': video_info.bitrate,
            'video': video_info.video,
            'audio': video_info.audio,
        }

        return ComposeResult(
            success=True,
            output_path=final_output_path,
            filename=os.path.basename(final_output_path),
            original_video=video_path,
            video_info=video_info_dict,
            tts_added=add_tts and bool(text_content),
            subtitles_added=add_subtitles and bool(subtitle_path),
            background_music_added=add_background_music and bool(background_music_path),
            stickers_added=stickers_added
        )

    def compose_from_segments(self, options: Dict[str, Any]) -> ComposeResult:
        video_segments = options.get('video_segments', [])
        text_contents = options.get('text_contents')
        background_music_path = options.get('background_music_path')
        output_file_name = options.get('output_file_name')
        add_subtitles = options.get('add_subtitles', True)
        add_background_music = options.get('add_background_music', True)
        add_tts = options.get('add_tts', True)
        add_stickers = options.get('add_stickers', True)
        stickers = options.get('stickers', [])
        subtitle_options = options.get('subtitle_options', {})
        tts_options = options.get('tts_options', {})
        bgm_options = options.get('bgm_options', {})
        sticker_options = options.get('sticker_options', {})

        if not video_segments:
            raise Exception('必须提供视频片段')

        base_output_name = output_file_name or f"composed_segments_{helpers.generate_unique_id()}"
        final_output_path = os.path.join(self.options['output_dir'], f"{base_output_name}.mp4")

        merged_video_path = video_segments[0]['path']
        if len(video_segments) > 1:
            print('正在合并视频片段...')
            merged_video_path = os.path.join(
                self.options['temp_dir'],
                f"merged_video_{helpers.generate_unique_id()}.mp4"
            )
            self.video_splitter.merge_videos(
                [s['path'] for s in video_segments],
                merged_video_path
            )

        return self.compose_video({
            'video_path': merged_video_path,
            'text_content': text_contents,
            'background_music_path': background_music_path,
            'output_file_name': base_output_name,
            'add_subtitles': add_subtitles,
            'add_background_music': add_background_music,
            'add_tts': add_tts,
            'add_stickers': add_stickers,
            'stickers': stickers,
            'subtitle_options': subtitle_options,
            'tts_options': tts_options,
            'bgm_options': bgm_options,
            'sticker_options': sticker_options,
            'cleanup': True,
        })

    def split_and_compose(self, options: Dict[str, Any]) -> ComposeResult:
        video_path = options.get('video_path')
        segment_duration = options.get('segment_duration')
        text_contents = options.get('text_contents')
        background_music_path = options.get('background_music_path')
        output_file_name = options.get('output_file_name')
        add_subtitles = options.get('add_subtitles', True)
        add_background_music = options.get('add_background_music', True)
        add_tts = options.get('add_tts', True)
        add_stickers = options.get('add_stickers', True)
        stickers = options.get('stickers', [])
        subtitle_options = options.get('subtitle_options', {})
        tts_options = options.get('tts_options', {})
        bgm_options = options.get('bgm_options', {})
        sticker_options = options.get('sticker_options', {})

        if not video_path:
            raise Exception('必须提供视频路径')

        if not os.path.exists(video_path):
            raise Exception(f'视频文件不存在: {video_path}')

        print('正在分割视频...')
        split_result = self.video_splitter.split_video(video_path, {
            'segment_duration': segment_duration,
        })

        segments_with_text = split_result['segments']

        if text_contents and isinstance(text_contents, list):
            segments_with_text = [
                {**vars(segment), 'text': text_contents[i] if i < len(text_contents) else ''}
                for i, segment in enumerate(split_result['segments'])
            ]

        combined_text = ' '.join([getattr(s, 'text', '') or s.get('text', '') for s in segments_with_text])

        return self.compose_video({
            'video_path': video_path,
            'text_content': combined_text,
            'background_music_path': background_music_path,
            'output_file_name': output_file_name,
            'add_subtitles': add_subtitles,
            'add_background_music': add_background_music,
            'add_tts': add_tts,
            'add_stickers': add_stickers,
            'stickers': stickers,
            'subtitle_options': subtitle_options,
            'tts_options': tts_options,
            'bgm_options': bgm_options,
            'sticker_options': sticker_options,
            'cleanup': True,
        })

    def _generate_tts(self, text_content, options: Dict[str, Any]):
        if isinstance(text_content, str):
            texts = helpers.split_text_for_tts(text_content, options.get('max_chars_per_segment', 500), options.get('split_by_sentence', True))
        elif isinstance(text_content, list):
            texts = text_content
        else:
            raise Exception('text_content 必须是字符串或数组')

        return self.tts_service.synthesize_batch(texts, {
            'output_dir': self.options['temp_dir'],
            **options,
        })

    def _process_background_music(self, background_music_path: str, target_duration: float,
                                    voice_segments: List[Dict[str, Any]],
                                    options: Dict[str, Any]):
        volume = options.get('volume', config.audio['background_music_volume'])
        apply_ducking = options.get('apply_ducking', True)
        fade_in = options.get('fade_in', config.audio['fade_duration'])
        fade_out = options.get('fade_out', config.audio['fade_duration'])

        print('正在循环播放背景音乐到目标时长...')
        looped_bgm = self.background_music_service.loop_audio_to_duration(
            background_music_path,
            target_duration,
            {
                'output_dir': self.options['temp_dir'],
                'volume': volume,
                'fade_in': fade_in,
                'fade_out': fade_out,
            }
        )

        if apply_ducking and voice_segments:
            print('正在应用闪避效果...')
            ducked_bgm = self.background_music_service.apply_ducking(
                looped_bgm.output_path,
                [
                    {'start_time': v.get('delay', i * 0.1), 'end_time': v.get('delay', i * 0.1) + 10}
                    for i, v in enumerate(voice_segments)
                ],
                {
                    'output_dir': self.options['temp_dir'],
                    'ducking_amount': config.audio['ducking_amount'],
                }
            )
            return ducked_bgm

        return looped_bgm

    def _add_subtitles_to_video(self, video_path: str, subtitle_path: str,
                                  output_path: str, options: Dict[str, Any]) -> str:
        font_size = options.get('font_size', config.subtitle['font_size'])
        font_color = options.get('font_color', config.subtitle['font_color'])
        background_color = options.get('background_color', config.subtitle['background_color'])
        position = options.get('position', config.subtitle['position'])
        margin_v = options.get('margin_v', config.subtitle['margin_v'])

        subtitle_path_escaped = subtitle_path.replace('\\', '/').replace(':', '\\:')

        vf_filter = (
            f"subtitles='{subtitle_path_escaped}':"
            f"force_style='FontSize={font_size},"
            f"PrimaryColour=&H{self._color_to_hex(font_color)}&,"
            f"BackColour=&H{self._color_to_hex(background_color)}&,"
            f"Alignment={self._position_to_alignment(position)},"
            f"MarginV={margin_v}'"
        )

        cmd = [
            self.ffmpeg_path, '-y',
            '-i', video_path,
            '-vf', vf_filter,
            '-c:a', 'copy',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise Exception(f'添加字幕到视频失败: {result.stderr.decode("utf-8", errors="ignore")}')

        return output_path

    def _color_to_hex(self, color: str) -> str:
        color_map = {
            'white': 'ffffff',
            'black': '000000',
            'red': '0000ff',
            'green': '00ff00',
            'blue': 'ff0000',
            'yellow': '00ffff',
            'cyan': 'ffff00',
            'magenta': 'ff00ff',
        }

        color_lower = color.lower()
        if color_lower in color_map:
            return color_map[color_lower]

        if color.startswith('#'):
            return color[1:].zfill(6)

        alpha_match = None
        import re
        alpha_match = re.match(r'^(\w+)@([\d.]+)$', color)
        if alpha_match:
            base_color = alpha_match.group(1)
            alpha = float(alpha_match.group(2))
            alpha_hex = format(int(alpha * 255), '02x')
            base_hex = color_map.get(base_color.lower(), 'ffffff')
            return alpha_hex + base_hex[2:]

        return 'ffffff'

    def _position_to_alignment(self, position: str) -> int:
        position_map = {
            'top': 8,
            'top-left': 7,
            'top-right': 9,
            'middle': 5,
            'middle-left': 4,
            'middle-right': 6,
            'bottom': 2,
            'bottom-left': 1,
            'bottom-right': 3,
        }
        return position_map.get(position.lower(), 2)

    def _cleanup_temp_files(self):
        try:
            temp_files = os.listdir(self.options['temp_dir'])
            for file in temp_files:
                file_path = os.path.join(self.options['temp_dir'], file)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            print('临时文件已清理')
        except Exception as error:
            print(f'清理临时文件时出错: {str(error)}')

    def _detect_original_audio_volume(self, video_path: str):
        try:
            volume_info = self.video_splitter.get_audio_volume(video_path)
            return volume_info
        except Exception as error:
            print(f'检测视频原声音量失败: {str(error)}')
            return type('AudioVolumeInfo', (), {
                'mean_volume': None,
                'max_volume': None,
                'has_audio': False,
            })()

    def _calculate_audio_priority(self, has_tts: bool, has_background_music: bool,
                                     original_audio_volume, has_original_audio: bool) -> Dict[str, Any]:
        threshold = config.audio['video_original_silence_threshold']
        is_original_audio_silent = (
            not has_original_audio or
            original_audio_volume.mean_volume is None or
            original_audio_volume.mean_volume <= threshold
        )

        use_original_audio = False
        original_audio_volume_factor = 1.0
        background_music_volume_factor = config.audio['background_music_volume']

        if has_tts:
            use_original_audio = False
            original_audio_volume_factor = config.audio['video_original_volume_with_tts']

            if is_original_audio_silent:
                background_music_volume_factor = config.audio['background_music_volume']
            else:
                background_music_volume_factor = config.audio['background_music_volume_with_tts']
        else:
            use_original_audio = has_original_audio and not is_original_audio_silent
            original_audio_volume_factor = 1.0

            if is_original_audio_silent:
                background_music_volume_factor = config.audio['background_music_volume']
            else:
                background_music_volume_factor = config.audio['background_music_volume_without_tts']

        return {
            'has_tts': has_tts,
            'has_background_music': has_background_music,
            'has_original_audio': has_original_audio,
            'is_original_audio_silent': is_original_audio_silent,
            'use_original_audio': use_original_audio,
            'original_audio_volume': original_audio_volume_factor,
            'background_music_volume': background_music_volume_factor,
        }

    def _add_multiple_audio_tracks_to_video(self, video_path: str, audio_tracks: List[Dict[str, Any]],
                                               output_path: str, audio_priority_config: Dict[str, Any],
                                               audio_type_info: Dict[str, bool]) -> str:
        use_original_audio = audio_priority_config['use_original_audio']
        original_audio_volume = audio_priority_config['original_audio_volume']
        has_tts_audio = audio_type_info['has_tts_audio']
        has_bgm_audio = audio_type_info['has_bgm_audio']

        input_args = ['-i', video_path]
        audio_track_index = 1
        audio_metadata_index = 0

        map_args = ['-map', '0:v:0']
        metadata_args = []
        filter_args = []

        if use_original_audio and original_audio_volume > 0:
            map_args.extend(['-map', '0:a:0'])
            metadata_args.extend(['-metadata:s:a:0', 'title=原声'])

            if original_audio_volume != 1.0:
                filter_args.append(f'-filter:a:0 volume={original_audio_volume}')

            audio_metadata_index = 1

        if has_tts_audio:
            tts_tracks = [t for t in audio_tracks if t['type'] == 'tts']

            for track in tts_tracks:
                input_args.extend(['-i', track['path']])
                map_args.extend(['-map', f'{audio_track_index}:a:0'])
                metadata_args.extend([f'-metadata:s:a:{audio_metadata_index}', 'title=配音'])

                audio_track_index += 1
                audio_metadata_index += 1

        if has_bgm_audio:
            bgm_tracks = [t for t in audio_tracks if t['type'] == 'bgm']

            for track in bgm_tracks:
                input_args.extend(['-i', track['path']])
                map_args.extend(['-map', f'{audio_track_index}:a:0'])
                metadata_args.extend([f'-metadata:s:a:{audio_metadata_index}', 'title=背景音乐'])

                audio_track_index += 1
                audio_metadata_index += 1

        cmd = [self.ffmpeg_path, '-y'] + input_args + map_args + filter_args + metadata_args + [
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-shortest',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise Exception(f'添加多音轨到视频失败: {result.stderr.decode("utf-8", errors="ignore")}')

        return output_path
