import tempfile
import shutil
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from src_py.config.config import config, Config
from src_py.utils.helpers import helpers
from src_py.modules.subtitle_generator import SubtitleGenerator


class TestConfig:
    def test_config_singleton(self):
        config1 = Config()
        config2 = Config()
        assert config1 is config2

    def test_config_default_values(self):
        assert config.video['default_segment_duration'] == 30
        assert config.audio['background_music_volume'] == 0.3
        assert config.subtitle['font_size'] == 24

    def test_config_directories(self):
        assert 'output' in config.directories
        assert 'temp' in config.directories


class TestHelpers:
    def test_format_timestamp(self):
        result = helpers.format_timestamp(123.456)
        assert result == '00:02:03,456'

    def test_format_timestamp_hours(self):
        result = helpers.format_timestamp(3661.5)
        assert result == '01:01:01,500'

    def test_parse_timestamp(self):
        result = helpers.parse_timestamp('00:02:03,456')
        assert result == 123.456

    def test_parse_timestamp_zero(self):
        result = helpers.parse_timestamp('invalid')
        assert result == 0.0

    def test_calculate_video_segments(self):
        segments = helpers.calculate_video_segments(65.0, 30.0)
        assert len(segments) == 3
        assert segments[0]['duration'] == 30.0
        assert segments[1]['duration'] == 30.0
        assert segments[2]['duration'] == 5.0

    def test_calculate_video_segments_exact(self):
        segments = helpers.calculate_video_segments(60.0, 30.0)
        assert len(segments) == 2
        assert segments[0]['duration'] == 30.0
        assert segments[1]['duration'] == 30.0

    def test_format_duration_minutes(self):
        result = helpers.format_duration(125.5)
        assert result == '2:05'

    def test_format_duration_hours(self):
        result = helpers.format_duration(3661.5)
        assert result == '1:01:01'

    def test_sanitize_filename(self):
        result = helpers.sanitize_filename('My Video: Test <File>.mp4')
        assert ':' not in result
        assert '<' not in result
        assert '>' not in result

    def test_split_text_for_tts_by_sentence(self):
        text = '这是第一句话。这是第二句话？这是第三句话！'
        segments = helpers.split_text_for_tts(text, max_chars_per_segment=50, split_by_sentence=True)
        assert len(segments) >= 1

    def test_split_text_for_tts_by_length(self):
        text = 'a' * 100
        segments = helpers.split_text_for_tts(text, max_chars_per_segment=30, split_by_sentence=False)
        assert len(segments) == 4

    def test_get_file_extension(self):
        result = helpers.get_file_extension('video.mp4')
        assert result == '.mp4'

    def test_get_file_name_without_extension(self):
        result = helpers.get_file_name_without_extension('/path/to/video.mp4')
        assert result == 'video'

    def test_ensure_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = os.path.join(temp_dir, 'test', 'nested')
            helpers.ensure_directory(test_dir)
            assert os.path.exists(test_dir)


class TestSubtitleGenerator:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.generator = SubtitleGenerator({'output_dir': self.temp_dir})

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    def test_generate_srt_from_text(self):
        text = '这是第一句话。这是第二句话。'
        result = self.generator.generate_srt_from_text(text, {
            'start_time': 0.0,
            'segment_by_sentence': True
        })

        assert result.count > 0
        assert result.srt_content
        assert '--> ' in result.srt_content

    def test_parse_srt(self):
        srt_content = """1
00:00:01,000 --> 00:00:03,000
这是第一句

2
00:00:04,000 --> 00:00:06,000
这是第二句
"""

        result = self.generator.parse_srt(srt_content)

        assert result.count == 2
        assert len(result.segments) == 2
        assert result.segments[0].start_time == 1.0
        assert result.segments[0].end_time == 3.0
        assert result.segments[1].text == '这是第二句'

    def test_save_srt(self):
        text = '测试字幕内容。'
        result = self.generator.generate_srt_from_text(text)
        output_path = os.path.join(self.temp_dir, 'test.srt')
        save_result = self.generator.save_srt(result, output_path)

        assert save_result['success']
        assert os.path.exists(output_path)

        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert '测试字幕内容' in content

    def test_adjust_timing(self):
        srt_content = """1
00:00:01,000 --> 00:00:03,000
测试
"""
        result = self.generator.parse_srt(srt_content)
        adjusted = self.generator.adjust_timing(result, {'offset': 2.0, 'speed_factor': 2.0})

        assert adjusted.segments[0].start_time == 6.0
        assert adjusted.segments[0].duration == 4.0

    def test_merge_subtitles(self):
        srt1 = """1
00:00:00,000 --> 00:00:02,000
第一组
"""
        srt2 = """1
00:00:00,000 --> 00:00:03,000
第二组
"""

        result1 = self.generator.parse_srt(srt1)
        result2 = self.generator.parse_srt(srt2)

        merged = self.generator.merge_subtitles([result1, result2], {'gap_between_groups': 1.0})

        assert merged.count == 2
        assert merged.segments[0].start_time == 0.0
        assert merged.segments[1].start_time == 3.0

    def test_create_ssml(self):
        text = '这是测试文本。'
        result = self.generator.generate_srt_from_text(text, {'total_duration': 5.0})
        assert result.count > 0
        assert '这是测试文本' in result.segments[0].text

    def test_split_by_length(self):
        long_text = 'a' * 100
        generator = SubtitleGenerator({'max_chars_per_line': 30})
        result = generator.generate_srt_from_text(
            long_text,
            {'segment_by_sentence': False, 'segment_by_length': True, 'max_chars_per_line': 30}
        )
        assert result.count > 1

    def test_estimate_duration(self):
        text = '这是一段测试文本。'
        result = self.generator.generate_srt_from_text(text)
        assert result.segments[0].duration > 0


class TestIntegrationSubtitleGenerator:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.generator = SubtitleGenerator({'output_dir': self.temp_dir})

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    def test_full_workflow(self):
        text = '这是第一个测试句子。这是第二个测试句子？这是第三个测试句子！'

        srt_data = self.generator.generate_srt_from_text(text)
        assert srt_data.count > 0

        output_path = os.path.join(self.temp_dir, 'output.srt')
        save_result = self.generator.save_srt(srt_data, output_path)
        assert save_result['success']
        assert os.path.exists(output_path)

        parsed_data = self.generator.parse_srt_file(output_path)
        assert parsed_data.count == srt_data.count

    def test_generate_from_tts_results(self):
        tts_results = [
            {'text': '第一句', 'duration': 2.0, 'audio_path': '/test/audio1.mp3'},
            {'text': '第二句', 'duration': 3.0, 'audio_path': '/test/audio2.mp3'},
        ]

        result = self.generator.generate_srt_from_tts_results(
            tts_results,
            {'start_time': 0.0, 'gap_between_segments': 0.5}
        )

        assert result.count == 2
        assert result.segments[0].end_time == 2.0
        assert result.segments[1].start_time == 2.5
        assert result.total_duration == 5.5
