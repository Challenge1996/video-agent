import os
import json
import base64
import httpx
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.config.config import config
from src.utils.helpers import helpers


@dataclass
class MiniMaxTTSResult:
    success: bool
    text: str
    audio_path: str
    filename: str
    duration: float
    format: str
    sample_rate: int = 0
    word_count: int = 0
    error: Optional[str] = None


@dataclass
class MiniMaxTTSBatchResult:
    success: bool
    results: List[MiniMaxTTSResult]
    successful_count: int
    failed_count: int


class MiniMaxTTSService:
    def __init__(self, options: Optional[Dict[str, Any]] = None):
        options = options or {}
        self.options = {
            'api_key': options.get('api_key', config.minimax['api_key']),
            'group_id': options.get('group_id', config.minimax['group_id']),
            'base_url': options.get('base_url', config.minimax['base_url']),
            'model': options.get('model', config.minimax['model']),
            'voice_id': options.get('voice_id', config.minimax['tts']['voice_id']),
            'speed': int(options.get('speed', config.minimax['tts']['speed'])),
            'vol': int(options.get('vol', config.minimax['tts']['vol'])),
            'pitch': int(options.get('pitch', config.minimax['tts']['pitch'])),
            'emotion': options.get('emotion', config.minimax['tts']['emotion']),
            'sample_rate': int(options.get('sample_rate', config.minimax['tts']['sample_rate'])),
            'bitrate': int(options.get('bitrate', config.minimax['tts']['bitrate'])),
            'format': options.get('format', config.minimax['tts']['format']),
            'channel': int(options.get('channel', config.minimax['tts']['channel'])),
            'output_dir': options.get('output_dir', config.temp_dir),
            **options,
        }

    def _get_base_url(self) -> str:
        return self.options['base_url']

    def _build_request_body(self, text: str, options: Dict[str, Any]) -> Dict[str, Any]:
        request_body = {
            'model': options.get('model', self.options['model']),
            'text': text,
            'stream': False,
            'voice_setting': {
                'voice_id': options.get('voice_id', self.options['voice_id']),
                'speed': int(options.get('speed', self.options['speed'])),
                'vol': int(options.get('vol', self.options['vol'])),
                'pitch': int(options.get('pitch', self.options['pitch'])),
                'emotion': options.get('emotion', self.options['emotion']),
            },
            'audio_setting': {
                'sample_rate': int(options.get('sample_rate', self.options['sample_rate'])),
                'bitrate': int(options.get('bitrate', self.options['bitrate'])),
                'format': options.get('format', self.options['format']),
                'channel': int(options.get('channel', self.options['channel'])),
            },
            'subtitle_enable': False,
        }

        if options.get('pronunciation_dict'):
            request_body['pronunciation_dict'] = options['pronunciation_dict']

        return request_body

    def synthesize_speech(self, text: str, options: Optional[Dict[str, Any]] = None) -> MiniMaxTTSResult:
        options = options or {}
        output_dir = options.get('output_dir', self.options['output_dir'])
        output_filename = options.get('output_filename', f"tts_{helpers.generate_unique_id()}.mp3")
        output_path = os.path.join(output_dir, output_filename)

        helpers.ensure_directory(output_dir)

        request_body = self._build_request_body(text, options)

        try:
            base_url = self._get_base_url()
            headers = {
                'Authorization': f'Bearer {self.options["api_key"]}',
                'Content-Type': 'application/json',
            }

            with httpx.Client(timeout=60.0) as client:
                response = client.post(base_url, headers=headers, json=request_body)

                if not response.is_success:
                    error_text = response.text
                    raise Exception(f'MiniMax API 请求失败: {response.status_code} - {error_text}')

                data = response.json()

                if data.get('base_resp', {}).get('status_code', 0) != 0:
                    error_msg = data.get('base_resp', {}).get('status_msg', '未知错误')
                    raise Exception(f'MiniMax TTS 合成失败: {error_msg}')

                audio_content = data.get('data', {}).get('audio')
                if not audio_content:
                    raise Exception('MiniMax API 未返回音频数据')

                if audio_content.startswith('http://') or audio_content.startswith('https://'):
                    self._download_audio_from_url(audio_content, output_path)
                else:
                    audio_buffer = base64.b64decode(audio_content)
                    with open(output_path, 'wb') as f:
                        f.write(audio_buffer)

                sample_rate = int(options.get('sample_rate', self.options['sample_rate']))
                duration = 0.0
                word_count = 0

                extra_info = data.get('extra_info', {})
                if extra_info and extra_info.get('audio_length'):
                    audio_length = int(extra_info['audio_length'])
                    if sample_rate > 0:
                        duration = audio_length / sample_rate
                    word_count = extra_info.get('word_count', 0)
                else:
                    audio_info = self._get_audio_info(output_path)
                    duration = audio_info['duration']

                return MiniMaxTTSResult(
                    success=True,
                    text=text,
                    audio_path=output_path,
                    filename=output_filename,
                    duration=round(duration, 2),
                    format=self.options['format'],
                    sample_rate=sample_rate,
                    word_count=word_count
                )
        except Exception as error:
            raise Exception(f'MiniMax TTS 合成失败: {str(error)}')

    def synthesize_batch(self, texts: List[str], options: Optional[Dict[str, Any]] = None) -> MiniMaxTTSBatchResult:
        results = []
        output_dir = options.get('output_dir', self.options['output_dir']) if options else self.options['output_dir']

        for i, text_item in enumerate(texts):
            text = text_item if isinstance(text_item, str) else text_item.get('text', '')
            item_options = {**text_item, **options} if isinstance(text_item, dict) else (options or {})
            output_filename = item_options.get('output_filename', f"tts_{str(i).zfill(3)}_{helpers.generate_unique_id()}.mp3")

            try:
                result = self.synthesize_speech(text, {
                    **item_options,
                    'output_dir': output_dir,
                    'output_filename': output_filename,
                })
                results.append(MiniMaxTTSResult(
                    success=True,
                    text=text,
                    audio_path=result.audio_path,
                    filename=result.filename,
                    duration=result.duration,
                    format=result.format,
                    sample_rate=result.sample_rate,
                    word_count=result.word_count
                ))
            except Exception as error:
                results.append(MiniMaxTTSResult(
                    success=False,
                    text=text,
                    audio_path='',
                    filename=output_filename,
                    duration=0,
                    format='mp3',
                    error=str(error)
                ))

        successful_count = sum(1 for r in results if r.success)
        failed_count = len(results) - successful_count

        return MiniMaxTTSBatchResult(
            success=all(r.success for r in results),
            results=results,
            successful_count=successful_count,
            failed_count=failed_count
        )

    def _download_audio_from_url(self, url: str, output_path: str):
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.get(url)
                if not response.is_success:
                    raise Exception(f'下载音频失败: {response.status_code}')
                with open(output_path, 'wb') as f:
                    f.write(response.content)
        except Exception as error:
            raise Exception(f'从 URL 下载音频失败: {str(error)}')

    def _get_audio_info(self, audio_path: str) -> Dict[str, Any]:
        ffprobe_path = config.ffmpeg['ffprobe_path']
        cmd = [
            ffprobe_path,
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

        return {
            'duration': float(format_info.get('duration', 0)),
            'size': int(format_info.get('size', 0)),
            'bitrate': int(format_info.get('bit_rate', 0)),
            'audio': audio_info
        }
