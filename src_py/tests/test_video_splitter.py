import tempfile
import shutil
import os
from unittest.mock import patch, MagicMock, call
import subprocess
import pytest

from src_py.config.config import config
from src_py.utils.helpers import helpers
from src_py.modules.video_splitter import VideoSplitter, VideoInfo, VideoSegment, AudioVolumeInfo


class TestVideoSplitter:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.splitter = VideoSplitter({'output_dir': self.temp_dir, 'segment_duration': 30})

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    def test_constructor_default(self):
        splitter = VideoSplitter()
        assert splitter is not None

    def test_constructor_custom(self):
        splitter = VideoSplitter({'segment_duration': 60, 'output_dir': '/custom/path'})
        assert splitter.options['segment_duration'] == 60
        assert splitter.options['output_dir'] == '/custom/path'

    @patch('subprocess.run')
    def test_get_video_info(self, mock_run):
        mock_metadata = {
            'format': {'duration': '120.5', 'size': 104857600, 'bit_rate': 5000000},
            'streams': [
                {'codec_type': 'video', 'codec_name': 'h264', 'width': 1920, 'height': 1080, 'avg_frame_rate': '30/1'},
                {'codec_type': 'audio', 'codec_name': 'aac', 'sample_rate': '48000', 'channels': 2}
            ]
        }

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"format": {"duration": "120.5", "size": 104857600, "bit_rate": 5000000}, "streams": [{"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "avg_frame_rate": "30/1"}, {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2}]}'
        )

        with patch.object(self.splitter, '_run_ffprobe', return_value=mock_metadata):
            info = self.splitter.get_video_info('/test/video.mp4')

            assert isinstance(info, VideoInfo)
            assert info.duration == 120.5
            assert info.size == 104857600
            assert info.bitrate == 5000000
            assert info.video['width'] == 1920
            assert info.video['height'] == 1080
            assert info.video['fps'] == 30.0
            assert info.audio is not None
            assert info.audio['sample_rate'] == 48000

    @patch('subprocess.run')
    def test_get_video_info_ffprobe_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr=b'ffprobe error'
        )

        with pytest.raises(Exception) as exc_info:
            self.splitter.get_video_info('/test/video.mp4')

        assert 'ffprobe' in str(exc_info.value).lower()

    def test_parse_frame_rate(self):
        assert self.splitter._parse_frame_rate('30/1') == 30.0
        assert self.splitter._parse_frame_rate('60/1') == 60.0
        assert self.splitter._parse_frame_rate('0/0') == 30.0
        assert self.splitter._parse_frame_rate('') == 30.0

    @patch('subprocess.run')
    def test_split_video_segment_calculation(self, mock_run):
        mock_metadata = {
            'format': {'duration': '65.0', 'size': 104857600, 'bit_rate': 5000000},
            'streams': [
                {'codec_type': 'video', 'codec_name': 'h264', 'width': 1920, 'height': 1080, 'avg_frame_rate': '30/1'},
                {'codec_type': 'audio', 'codec_name': 'aac', 'sample_rate': '48000', 'channels': 2}
            ]
        }

        with patch.object(self.splitter, '_run_ffprobe', return_value=mock_metadata):
            with patch.object(self.splitter, '_extract_segment') as mock_extract:
                mock_extract.return_value = None

                result = self.splitter.split_video('/test/video.mp4', {'segment_duration': 30})

                assert result['segment_count'] == 3
                assert len(result['segments']) == 3
                assert result['segments'][0].duration == 30
                assert result['segments'][1].duration == 30
                assert result['segments'][2].duration == 5

    @patch('subprocess.run')
    def test_split_video_exact_duration(self, mock_run):
        mock_metadata = {
            'format': {'duration': '60.0', 'size': 104857600, 'bit_rate': 5000000},
            'streams': [
                {'codec_type': 'video', 'codec_name': 'h264', 'width': 1920, 'height': 1080, 'avg_frame_rate': '30/1'}
            ]
        }

        with patch.object(self.splitter, '_run_ffprobe', return_value=mock_metadata):
            with patch.object(self.splitter, '_extract_segment') as mock_extract:
                mock_extract.return_value = None

                result = self.splitter.split_video('/test/video.mp4', {'segment_duration': 30})

                assert result['segment_count'] == 2

    @patch('subprocess.run')
    def test_split_by_custom_intervals_validation(self, mock_run):
        mock_metadata = {
            'format': {'duration': '60.0', 'size': 104857600, 'bit_rate': 5000000},
            'streams': [
                {'codec_type': 'video', 'codec_name': 'h264', 'width': 1920, 'height': 1080, 'avg_frame_rate': '30/1'}
            ]
        }

        with patch.object(self.splitter, '_run_ffprobe', return_value=mock_metadata):
            with patch.object(self.splitter, '_extract_segment') as mock_extract:
                mock_extract.return_value = None

                invalid_intervals = [{'start_time': 50, 'end_time': 100}]

                with pytest.raises(Exception) as exc_info:
                    self.splitter.split_by_custom_intervals('/test/video.mp4', invalid_intervals)

                assert '超出视频范围' in str(exc_info.value)

    @patch('subprocess.run')
    def test_split_by_custom_intervals_valid(self, mock_run):
        mock_metadata = {
            'format': {'duration': '120.0', 'size': 104857600, 'bit_rate': 5000000},
            'streams': [
                {'codec_type': 'video', 'codec_name': 'h264', 'width': 1920, 'height': 1080, 'avg_frame_rate': '30/1'}
            ]
        }

        with patch.object(self.splitter, '_run_ffprobe', return_value=mock_metadata):
            with patch.object(self.splitter, '_extract_segment') as mock_extract:
                mock_extract.return_value = None

                intervals = [
                    {'start_time': 0, 'end_time': 30},
                    {'start_time': 40, 'end_time': 70},
                    {'start_time': 90, 'end_time': 120},
                ]

                result = self.splitter.split_by_custom_intervals('/test/video.mp4', intervals)

                assert result['segment_count'] == 3

    def test_merge_videos_empty(self):
        with pytest.raises(Exception) as exc_info:
            self.splitter.merge_videos([], '/test/output.mp4')

        assert '没有提供要合并' in str(exc_info.value)

    def test_create_concat_file(self):
        video_paths = [
            '/test/segment1.mp4',
            '/test/segment2.mp4',
            '/test/segment3.mp4',
        ]

        concat_file = self.splitter._create_concat_file(video_paths)

        assert os.path.exists(concat_file)

        with open(concat_file, 'r', encoding='utf-8') as f:
            content = f.read()

        assert "file '/test/segment1.mp4'" in content
        assert "file '/test/segment2.mp4'" in content
        assert "file '/test/segment3.mp4'" in content

        os.unlink(concat_file)

    def test_create_concat_file_special_chars(self):
        video_paths = [
            "/test/path with spaces/video.mp4",
            "/test/path'with'quotes/video.mp4",
        ]

        concat_file = self.splitter._create_concat_file(video_paths)

        assert os.path.exists(concat_file)

        with open(concat_file, 'r', encoding='utf-8') as f:
            content = f.read()

        assert "path with spaces" in content

        os.unlink(concat_file)

    @patch('subprocess.run')
    def test_get_audio_volume(self, mock_run):
        mock_stderr = b"""
            [Parsed_volumedetect_0 @ 0x55f8f8a98c00] mean_volume: -20.5 dB
            [Parsed_volumedetect_0 @ 0x55f8f8a98c00] max_volume: -5.0 dB
        """

        mock_run.return_value = MagicMock(
            returncode=0,
            stderr=mock_stderr,
            stdout=b''
        )

        result = self.splitter.get_audio_volume('/test/video.mp4')

        assert isinstance(result, AudioVolumeInfo)
        assert result.mean_volume == -20.5
        assert result.max_volume == -5.0
        assert result.has_audio is True

    @patch('subprocess.run')
    def test_get_audio_volume_no_audio(self, mock_run):
        mock_stderr = b"""
            No audio stream
        """

        mock_run.return_value = MagicMock(
            returncode=0,
            stderr=mock_stderr,
            stdout=b''
        )

        result = self.splitter.get_audio_volume('/test/video.mp4')

        assert result.mean_volume is None
        assert result.max_volume is None
        assert result.has_audio is False


class TestVideoSplitterIntegration:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.splitter = VideoSplitter({'output_dir': self.temp_dir})

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    def test_split_video_calls_extract_segment(self):
        mock_metadata = {
            'format': {'duration': '65.0', 'size': 104857600, 'bit_rate': 5000000},
            'streams': [
                {'codec_type': 'video', 'codec_name': 'h264', 'width': 1920, 'height': 1080, 'avg_frame_rate': '30/1'}
            ]
        }

        with patch.object(self.splitter, '_run_ffprobe', return_value=mock_metadata):
            with patch.object(self.splitter, '_extract_segment') as mock_extract:
                mock_extract.return_value = None

                self.splitter.split_video('/test/video.mp4', {'segment_duration': 30})

                assert mock_extract.call_count == 3
