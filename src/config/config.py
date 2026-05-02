import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional

load_dotenv()


class Config:
    _instance: Optional['Config'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._load_config()

    def _load_config(self):
        self.tts = {
            'provider': os.getenv('TTS_PROVIDER', 'minimax'),
        }

        self.google = {
            'credentials': os.getenv('GOOGLE_APPLICATION_CREDENTIALS', './credentials/google-cloud-key.json'),
            'tts': {
                'language_code': os.getenv('GOOGLE_TTS_LANGUAGE_CODE', 'zh-CN'),
                'voice_name': os.getenv('GOOGLE_TTS_VOICE_NAME', 'zh-CN-Wavenet-A'),
                'speaking_rate': float(os.getenv('GOOGLE_TTS_SPEAKING_RATE', '1.0')),
                'pitch': float(os.getenv('GOOGLE_TTS_PITCH', '0.0')),
            },
        }

        self.minimax = {
            'api_key': os.getenv('MINIMAX_API_KEY', ''),
            'group_id': os.getenv('MINIMAX_GROUP_ID', ''),
            'base_url': os.getenv('MINIMAX_BASE_URL', 'https://api.minimax.chat/v1/t2a_v2'),
            'model': os.getenv('MINIMAX_MODEL', 'speech-2.8-hd'),
            'tts': {
                'voice_id': os.getenv('MINIMAX_VOICE_ID', 'male-qn-qingse'),
                'speed': float(os.getenv('MINIMAX_SPEED', '1.0')),
                'vol': float(os.getenv('MINIMAX_VOL', '1.0')),
                'pitch': float(os.getenv('MINIMAX_PITCH', '0.0')),
                'emotion': os.getenv('MINIMAX_EMOTION', 'happy'),
                'sample_rate': int(os.getenv('MINIMAX_SAMPLE_RATE', '32000')),
                'bitrate': int(os.getenv('MINIMAX_BITRATE', '128000')),
                'format': os.getenv('MINIMAX_FORMAT', 'mp3'),
                'channel': int(os.getenv('MINIMAX_CHANNEL', '1')),
            },
        }

        self.ffmpeg = {
            'path': os.getenv('FFMPEG_PATH', 'ffmpeg'),
            'ffprobe_path': os.getenv('FFPROBE_PATH', 'ffprobe'),
        }

        self.directories = {
            'output': os.getenv('OUTPUT_DIR', './output'),
            'temp': os.getenv('TEMP_DIR', './temp'),
        }

        self.video = {
            'default_segment_duration': 30,
            'default_resolution': '1920x1080',
            'default_fps': 30,
            'douyin_aspect_ratio': '9:16',
            'douyin_default_resolution': '720x1280',
            'default_crf': 23,
            'default_preset': 'medium',
        }

        self.audio = {
            'background_music_volume': 0.3,
            'tts_volume': 1.0,
            'ducking_amount': 0.15,
            'fade_duration': 1.0,
            'video_original_volume_with_tts': 0.0,
            'background_music_volume_with_tts': 0.15,
            'background_music_volume_without_tts': 0.2,
            'video_original_silence_threshold': -50,
        }

        self.subtitle = {
            'font_size': 24,
            'font_color': 'white',
            'background_color': 'black@0.5',
            'position': 'bottom',
            'margin_v': 40,
        }

        self.sticker = {
            'default_opacity': 1.0,
            'default_scale': 1.0,
            'default_position': 'top-left',
        }

    @property
    def output_dir(self) -> str:
        return self.directories['output']

    @property
    def temp_dir(self) -> str:
        return self.directories['temp']

    def ensure_directories(self):
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)


config = Config()
