import os
import json
import asyncio
import httpx
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.config.config import config
from src.utils.helpers import helpers


@dataclass
class TTSResult:
    success: bool
    text: str
    audio_path: str
    filename: str
    duration: float
    format: str
    error: Optional[str] = None


@dataclass
class TTSBatchResult:
    success: bool
    results: List[TTSResult]
    successful_count: int
    failed_count: int


@dataclass
class VoiceInfo:
    name: str
    language_codes: List[str]
    ssml_gender: str
    natural_sample_rate_hertz: int


class TTSService:
    def __init__(self, options: Optional[Dict[str, Any]] = None):
        options = options or {}
        self.options = {
            'credentials': options.get('credentials', config.google['credentials']),
            'language_code': options.get('language_code', config.google['tts']['language_code']),
            'voice_name': options.get('voice_name', config.google['tts']['voice_name']),
            'speaking_rate': options.get('speaking_rate', config.google['tts']['speaking_rate']),
            'pitch': options.get('pitch', config.google['tts']['pitch']),
            'output_dir': options.get('output_dir', config.temp_dir),
            **options,
        }
        self.client = None
        self._init_client()

    def _init_client(self):
        try:
            credentials_path = self.options['credentials']
            if os.path.exists(credentials_path):
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path

            try:
                from google.cloud import texttospeech
                self.client = texttospeech.TextToSpeechClient()
            except ImportError:
                print('警告: google-cloud-text-to-speech 未安装，Google TTS 功能将不可用')
                self.client = None
        except Exception as error:
            print(f'Google TTS 客户端初始化警告: {str(error)}')
            print('请确保 GOOGLE_APPLICATION_CREDENTIALS 环境变量已正确设置，或配置文件中包含有效的凭证路径')
            self.client = None

    def synthesize_speech(self, text: str, options: Optional[Dict[str, Any]] = None) -> TTSResult:
        if not self.client:
            raise Exception('Google TTS 客户端未初始化，请检查凭证配置')

        options = options or {}
        output_dir = options.get('output_dir', self.options['output_dir'])
        output_filename = options.get('output_filename', f"tts_{helpers.generate_unique_id()}.mp3")
        output_path = os.path.join(output_dir, output_filename)

        helpers.ensure_directory(output_dir)

        from google.cloud import texttospeech

        synthesis_input = texttospeech.SynthesisInput(text=text)

        voice = texttospeech.VoiceSelectionParams(
            language_code=options.get('language_code', self.options['language_code']),
            name=options.get('voice_name', self.options['voice_name']),
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=options.get('speaking_rate', self.options['speaking_rate']),
            pitch=options.get('pitch', self.options['pitch']),
            volume_gain_db=options.get('volume_gain_db', 0),
            sample_rate_hertz=options.get('sample_rate_hertz', 24000),
        )

        try:
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )

            with open(output_path, 'wb') as f:
                f.write(response.audio_content)

            audio_info = self._get_audio_info(output_path)

            return TTSResult(
                success=True,
                text=text,
                audio_path=output_path,
                filename=output_filename,
                duration=audio_info['duration'],
                format='mp3'
            )
        except Exception as error:
            raise Exception(f'TTS 合成失败: {str(error)}')

    def synthesize_speech_with_ssml(self, ssml: str, options: Optional[Dict[str, Any]] = None) -> TTSResult:
        if not self.client:
            raise Exception('Google TTS 客户端未初始化，请检查凭证配置')

        options = options or {}
        output_dir = options.get('output_dir', self.options['output_dir'])
        output_filename = options.get('output_filename', f"tts_{helpers.generate_unique_id()}.mp3")
        output_path = os.path.join(output_dir, output_filename)

        helpers.ensure_directory(output_dir)

        from google.cloud import texttospeech

        synthesis_input = texttospeech.SynthesisInput(ssml=ssml)

        voice = texttospeech.VoiceSelectionParams(
            language_code=options.get('language_code', self.options['language_code']),
            name=options.get('voice_name', self.options['voice_name']),
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=options.get('speaking_rate', self.options['speaking_rate']),
            pitch=options.get('pitch', self.options['pitch']),
            volume_gain_db=options.get('volume_gain_db', 0),
            sample_rate_hertz=options.get('sample_rate_hertz', 24000),
        )

        try:
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )

            with open(output_path, 'wb') as f:
                f.write(response.audio_content)

            audio_info = self._get_audio_info(output_path)

            return TTSResult(
                success=True,
                text=ssml,
                audio_path=output_path,
                filename=output_filename,
                duration=audio_info['duration'],
                format='mp3'
            )
        except Exception as error:
            raise Exception(f'TTS 合成失败: {str(error)}')

    def synthesize_batch(self, texts: List[str], options: Optional[Dict[str, Any]] = None) -> TTSBatchResult:
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
                results.append(TTSResult(
                    success=True,
                    text=text,
                    audio_path=result.audio_path,
                    filename=result.filename,
                    duration=result.duration,
                    format=result.format
                ))
            except Exception as error:
                results.append(TTSResult(
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

        return TTSBatchResult(
            success=all(r.success for r in results),
            results=results,
            successful_count=successful_count,
            failed_count=failed_count
        )

    def list_voices(self, language_code: Optional[str] = None) -> Dict[str, List[VoiceInfo]]:
        if not self.client:
            raise Exception('Google TTS 客户端未初始化，请检查凭证配置')

        try:
            response = self.client.list_voices(
                language_code=language_code or self.options['language_code']
            )

            voices = []
            for voice in response.voices:
                voices.append(VoiceInfo(
                    name=voice.name,
                    language_codes=list(voice.language_codes),
                    ssml_gender=voice.ssml_gender.name,
                    natural_sample_rate_hertz=voice.natural_sample_rate_hertz
                ))

            return {'voices': voices}
        except Exception as error:
            raise Exception(f'获取语音列表失败: {str(error)}')

    def _get_audio_info(self, audio_path: str) -> Dict[str, Any]:
        import subprocess
        import json

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

    def create_ssml(self, text: str, options: Optional[Dict[str, Any]] = None) -> str:
        options = options or {}
        speaking_rate = options.get('speaking_rate', self.options['speaking_rate'])
        pitch = options.get('pitch', self.options['pitch'])
        volume = options.get('volume', 'default')
        break_times = options.get('break_times', [])

        ssml = '<speak>'

        if speaking_rate != 1.0 or pitch != 0.0 or volume != 'default':
            prosody_attrs = []
            if speaking_rate != 1.0:
                prosody_attrs.append(f'rate="{speaking_rate}"')
            if pitch != 0.0:
                pitch_str = f"+{pitch}st" if pitch > 0 else f"{pitch}st"
                prosody_attrs.append(f'pitch="{pitch_str}"')
            if volume != 'default':
                prosody_attrs.append(f'volume="{volume}"')
            ssml += f"<prosody {' '.join(prosody_attrs)}>"

        processed_text = text
        for index, break_time in enumerate(break_times):
            placeholder = f"__BREAK_{index}__"
            if placeholder in processed_text:
                break_tag = f'<break time="{break_time}"/>'
                processed_text = processed_text.replace(placeholder, break_tag)

        ssml += processed_text

        if speaking_rate != 1.0 or pitch != 0.0 or volume != 'default':
            ssml += '</prosody>'

        ssml += '</speak>'

        return ssml
