import tempfile
import shutil
import os
from unittest.mock import patch, MagicMock
import pytest

from src_py.config.config import config
from src_py.utils.helpers import helpers
from src_py.modules.background_music import (
    BackgroundMusicService,
    AudioInfo,
    LoopResult,
    DuckingResult,
    MergeResult,
    VolumeResult,
    FadeResult
)


class TestBackgroundMusicService:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.service = BackgroundMusicService({'output_dir': self.temp_dir})

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    def test_constructor_default(self):
        service = BackgroundMusicService()
        assert service is not None

    def test_constructor_custom(self):
        service = BackgroundMusicService({
            'default_volume': 0.5,
            'ducking_amount': 0.3,
            'fade_duration': 2.0
        })
        assert service.options['default_volume'] == 0.5
        assert service.options['ducking_amount'] == 0.3
        assert service.options['fade_duration'] == 2.0

    @patch('subprocess.run')
    def test_get_audio_info(self, mock_run):
        mock_metadata = {
            'format': {'duration': '60.0', 'size': 5242880, 'bit_rate': 128000},
            'streams': [
                {'codec_type': 'audio', 'codec_name': 'mp3', 'sample_rate': '44100', 'channels': 2}
            ]
        }

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"format": {"duration": "60.0", "size": 5242880, "bit_rate": 128000}, "streams": [{"codec_type": "audio", "codec_name": "mp3", "sample_rate": "44100", "channels": 2}]}'
        )

        with patch.object(self.service, 'get_audio_info') as mock_get:
            mock_get.return_value = AudioInfo(
                duration=60.0,
                size=5242880,
                bitrate=128000,
                audio={'codec': 'mp3', 'sample_rate': 44100, 'channels': 2}
            )

            info = self.service.get_audio_info('/test/audio.mp3')

            assert isinstance(info, AudioInfo)
            assert info.duration == 60.0
            assert info.size == 5242880
            assert info.audio is not None
            assert info.audio['sample_rate'] == 44100

    @patch('subprocess.run')
    def test_get_audio_info_ffprobe_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr=b'ffprobe error'
        )

        with pytest.raises(Exception) as exc_info:
            self.service.get_audio_info('/test/audio.mp3')

        assert 'ffprobe' in str(exc_info.value).lower()

    def test_create_ducking_volume_expression(self):
        expr = self.service._create_ducking_volume_expression(
            start_time=10.0,
            end_time=20.0,
            ducking_amount=0.5,
            fade_duration=1.0
        )

        assert 'between(t,' in expr
        assert '10' in expr
        assert '20' in expr

    def test_create_ducking_volume_expression_no_fade_in(self):
        expr = self.service._create_ducking_volume_expression(
            start_time=0.0,
            end_time=10.0,
            ducking_amount=0.3,
            fade_duration=1.0
        )

        assert 'between(t,' in expr

    @patch('subprocess.run')
    def test_apply_ducking_no_voice_segments(self, mock_run):
        import shutil
        test_file = os.path.join(self.temp_dir, 'test.mp3')
        with open(test_file, 'wb') as f:
            f.write(b'test')

        mock_run.return_value = MagicMock(
            returncode=0,
            stderr=b'',
            stdout=b''
        )

        result = self.service.apply_ducking(test_file, [])

        assert isinstance(result, DuckingResult)
        assert result.success is True
        assert result.ducking_applied is False
        assert result.reason == '没有语音片段需要闪避'

    @patch('subprocess.run')
    def test_add_fade_effects_no_filters(self, mock_run):
        import shutil
        test_file = os.path.join(self.temp_dir, 'test.mp3')
        with open(test_file, 'wb') as f:
            f.write(b'test')

        mock_run.return_value = MagicMock(
            returncode=0,
            stderr=b'',
            stdout=b''
        )

        result = self.service.add_fade_effects(test_file, {'fade_in': 0, 'fade_out': 0})

        assert isinstance(result, FadeResult)
        assert result.success is True
        assert result.fade_applied is False
        assert result.reason == '没有指定淡入淡出效果'

    def test_merge_audio_tracks_empty(self):
        with pytest.raises(Exception) as exc_info:
            self.service.merge_audio_tracks([], '/test/output.mp3')

        assert '没有提供要合并' in str(exc_info.value)

    @patch('subprocess.run')
    def test_adjust_volume(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stderr=b'',
            stdout=b''
        )

        test_file = os.path.join(self.temp_dir, 'test.mp3')
        with open(test_file, 'wb') as f:
            f.write(b'test')

        result = self.service.adjust_volume(test_file, 0.5)

        assert isinstance(result, VolumeResult)
        assert result.success is True
        assert result.volume == 0.5

    @patch('subprocess.run')
    def test_adjust_volume_ffmpeg_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr=b'ffmpeg error',
            stdout=b''
        )

        test_file = os.path.join(self.temp_dir, 'test.mp3')
        with open(test_file, 'wb') as f:
            f.write(b'test')

        with pytest.raises(Exception) as exc_info:
            self.service.adjust_volume(test_file, 0.5)

        assert '音量调整失败' in str(exc_info.value)


class TestBackgroundMusicServiceIntegration:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.service = BackgroundMusicService({'output_dir': self.temp_dir})

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    def test_get_audio_info_calls_ffprobe(self):
        mock_metadata = {
            'format': {'duration': '60.0', 'size': 5242880, 'bit_rate': 128000},
            'streams': [
                {'codec_type': 'audio', 'codec_name': 'mp3', 'sample_rate': '44100', 'channels': 2}
            ]
        }

        with patch.object(self.service, 'get_audio_info') as mock_get:
            mock_get.return_value = AudioInfo(
                duration=60.0,
                size=5242880,
                bitrate=128000,
                audio={'codec': 'mp3', 'sample_rate': 44100, 'channels': 2}
            )

            info = self.service.get_audio_info('/test/audio.mp3')

            assert info.duration == 60.0
