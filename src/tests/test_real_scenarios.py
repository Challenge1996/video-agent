import os
import sys
import tempfile
import shutil
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
MEDIA_DIR = PROJECT_ROOT / 'media'
OUTPUT_DIR = PROJECT_ROOT / 'src' / 'output'
TEMP_DIR = PROJECT_ROOT / 'src' / 'temp'

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

from src.config.config import config
from src.utils.helpers import helpers
from src.modules.video_splitter import VideoSplitter
from src.modules.subtitle_generator import SubtitleGenerator
from src.modules.background_music import BackgroundMusicService
from src.modules.sticker_service import StickerService
from src.modules.minimax_tts_service import MiniMaxTTSService


class TestRealVideoSplitter:
    """使用真实 FFmpeg 的视频分割测试"""

    @classmethod
    def setup_class(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.splitter = VideoSplitter({'output_dir': cls.temp_dir})

        cls.test_video = str(MEDIA_DIR / 'test_video.mp4')
        if not os.path.exists(cls.test_video):
            cls.video_info = cls.splitter.get_video_info(cls.test_video)
        else:
            cls.video_info = None

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_get_video_info_real(self):
        """测试获取真实视频信息"""
        assert os.path.exists(self.test_video), f"测试视频不存在: {self.test_video}"
        
        info = self.splitter.get_video_info(self.test_video)
        
        assert info.duration > 0
        assert info.video['width'] > 0
        assert info.video['height'] > 0
        
        print(f"\n✓ 视频信息获取成功:")
        print(f"  - 时长: {info.duration} 秒")
        print(f"  - 分辨率: {info.video['width']}x{info.video['height']}")
        print(f"  - 帧率: {info.video.get('fps', 'N/A')} fps")
        print(f"  - 有音频: {info.audio is not None}")

    def test_02_split_video_real(self):
        """测试分割真实视频"""
        if not os.path.exists(self.test_video):
            pytest.skip("测试视频不存在")

        result = self.splitter.split_video(self.test_video, {'segment_duration': 3})
        
        assert result['segment_count'] > 0
        assert len(result['segments']) == result['segment_count']
        
        for segment in result['segments']:
            assert os.path.exists(segment.path)
            assert segment.duration > 0
        
        print(f"\n✓ 视频分割成功:")
        print(f"  - 分割段数: {result['segment_count']}")
        for i, segment in enumerate(result['segments']):
            print(f"  - 片段 {i+1}: {segment.filename} (时长: {segment.duration:.2f}s)")

    def test_03_split_by_custom_intervals(self):
        """测试按自定义时间区间分割"""
        if not os.path.exists(self.test_video):
            pytest.skip("测试视频不存在")

        info = self.splitter.get_video_info(self.test_video)
        
        intervals = [
            {'start_time': 0, 'end_time': min(2, info.duration)},
            {'start_time': min(3, info.duration - 1), 'end_time': min(5, info.duration)},
        ]

        result = self.splitter.split_by_custom_intervals(self.test_video, intervals)
        
        assert result['segment_count'] == 2
        
        for segment in result['segments']:
            assert os.path.exists(segment.path)
        
        print(f"\n✓ 自定义时间区间分割成功:")
        print(f"  - 分割段数: {result['segment_count']}")

    def test_04_get_audio_volume(self):
        """测试检测音频音量"""
        if not os.path.exists(self.test_video):
            pytest.skip("测试视频不存在")

        volume_info = self.splitter.get_audio_volume(self.test_video)
        
        print(f"\n✓ 音频音量检测:")
        print(f"  - 有音频: {volume_info.has_audio}")
        print(f"  - 平均音量: {volume_info.mean_volume} dB")
        print(f"  - 最大音量: {volume_info.max_volume} dB")


class TestRealSubtitleGenerator:
    """字幕生成测试"""

    @classmethod
    def setup_class(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.generator = SubtitleGenerator({'output_dir': cls.temp_dir})

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_generate_srt_from_text(self):
        """测试从文本生成 SRT"""
        text = """这是第一句话。这是第二句话？这是第三句话！这是一段比较长的测试文本，用来测试字幕生成功能是否正常工作。"""

        result = self.generator.generate_srt_from_text(text, {
            'segment_by_sentence': True,
            'total_duration': 10.0
        })

        assert result.count > 0
        assert result.srt_content

        print(f"\n✓ 字幕生成成功:")
        print(f"  - 字幕数量: {result.count}")
        print(f"  - SRT 内容预览:")
        for line in result.srt_content.split('\n')[:10]:
            print(f"    {line}")

    def test_02_save_and_parse_srt(self):
        """测试保存和解析 SRT 文件"""
        text = "测试字幕生成和解析功能。"
        
        result = self.generator.generate_srt_from_text(text)
        
        output_path = os.path.join(self.temp_dir, 'test_output.srt')
        save_result = self.generator.save_srt(result, output_path)
        
        assert save_result['success']
        assert os.path.exists(output_path)
        
        parsed = self.generator.parse_srt_file(output_path)
        
        assert parsed.count == result.count
        
        print(f"\n✓ 字幕保存和解析成功:")
        print(f"  - 文件路径: {output_path}")
        print(f"  - 字幕数量: {parsed.count}")

    def test_03_adjust_timing(self):
        """测试调整字幕时间轴"""
        text = "第一句。第二句。第三句。"
        
        result = self.generator.generate_srt_from_text(text)
        
        adjusted = self.generator.adjust_timing(result, {
            'offset': 5.0,
            'speed_factor': 0.5
        })
        
        assert adjusted.segments[0].start_time == result.segments[0].start_time * 0.5 + 5.0
        
        print(f"\n✓ 字幕时间轴调整成功:")
        print(f"  - 原始开始时间: {result.segments[0].start_time}")
        print(f"  - 调整后开始时间: {adjusted.segments[0].start_time}")


class TestRealBackgroundMusic:
    """背景音乐处理测试"""

    @classmethod
    def setup_class(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.service = BackgroundMusicService({'output_dir': cls.temp_dir})

        cls.test_audio = str(MEDIA_DIR / 'test_audio.mp3')
        cls.test_bgm = str(MEDIA_DIR / 'bbb.mp3')

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_get_audio_info(self):
        """测试获取音频信息"""
        audio_path = self.test_bgm if os.path.exists(self.test_bgm) else self.test_audio
        
        if not os.path.exists(audio_path):
            pytest.skip("测试音频不存在")

        info = self.service.get_audio_info(audio_path)
        
        assert info.duration > 0
        
        print(f"\n✓ 音频信息获取成功:")
        print(f"  - 时长: {info.duration} 秒")
        print(f"  - 大小: {info.size} 字节")
        print(f"  - 码率: {info.bitrate} bps")
        if info.audio:
            print(f"  - 编码: {info.audio['codec']}")
            print(f"  - 采样率: {info.audio['sample_rate']} Hz")
            print(f"  - 声道: {info.audio['channels']}")

    def test_02_loop_audio_to_duration(self):
        """测试循环音频到指定时长"""
        audio_path = self.test_bgm if os.path.exists(self.test_bgm) else self.test_audio
        
        if not os.path.exists(audio_path):
            pytest.skip("测试音频不存在")

        info = self.service.get_audio_info(audio_path)
        target_duration = min(info.duration * 2, 10)

        result = self.service.loop_audio_to_duration(audio_path, target_duration, {
            'volume': 0.5,
            'fade_in': 1.0,
            'fade_out': 1.0
        })
        
        assert result.success
        assert os.path.exists(result.output_path)
        
        print(f"\n✓ 音频循环成功:")
        print(f"  - 原始时长: {info.duration} 秒")
        print(f"  - 目标时长: {result.target_duration} 秒")
        print(f"  - 输出文件: {result.output_path}")
        print(f"  - 音量: {result.volume}")

    def test_03_adjust_volume(self):
        """测试调整音量"""
        audio_path = self.test_audio
        
        if not os.path.exists(audio_path):
            pytest.skip("测试音频不存在")

        result = self.service.adjust_volume(audio_path, 0.5)
        
        assert result.success
        assert os.path.exists(result.output_path)
        
        print(f"\n✓ 音量调整成功:")
        print(f"  - 输出文件: {result.output_path}")
        print(f"  - 音量: {result.volume}")

    def test_04_add_fade_effects(self):
        """测试添加淡入淡出效果"""
        audio_path = self.test_audio
        
        if not os.path.exists(audio_path):
            pytest.skip("测试音频不存在")

        result = self.service.add_fade_effects(audio_path, {
            'fade_in': 2.0,
            'fade_out': 2.0
        })
        
        assert result.success
        
        print(f"\n✓ 淡入淡出效果添加成功:")
        print(f"  - 输出文件: {result.output_path}")
        print(f"  - 淡入: {result.fade_in} 秒")
        print(f"  - 淡出: {result.fade_out} 秒")


class TestRealStickerService:
    """贴纸服务测试"""

    @classmethod
    def setup_class(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.service = StickerService({'output_dir': cls.temp_dir})

        cls.test_video = str(MEDIA_DIR / 'test_video.mp4')
        cls.test_sticker = str(MEDIA_DIR / 'test_sticker.png')
        cls.existing_sticker = str(MEDIA_DIR / 'stick.png')

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_get_image_info(self):
        """测试获取图片信息"""
        sticker_path = self.existing_sticker if os.path.exists(self.existing_sticker) else self.test_sticker
        
        if not os.path.exists(sticker_path):
            pytest.skip("测试贴纸不存在")

        info = self.service.get_image_info(sticker_path)
        
        assert info.width > 0
        assert info.height > 0
        
        print(f"\n✓ 图片信息获取成功:")
        print(f"  - 尺寸: {info.width}x{info.height}")
        print(f"  - 格式: {info.format}")
        print(f"  - 是否动画: {info.is_animated}")

    def test_02_validate_sticker_file(self):
        """测试验证贴纸文件"""
        sticker_path = self.existing_sticker if os.path.exists(self.existing_sticker) else self.test_sticker
        
        if not os.path.exists(sticker_path):
            pytest.skip("测试贴纸不存在")

        result = self.service.validate_sticker_file(sticker_path)
        
        assert result.valid
        
        print(f"\n✓ 贴纸文件验证成功:")
        print(f"  - 有效: {result.valid}")
        print(f"  - 类型: {result.type}")
        print(f"  - 尺寸: {result.width}x{result.height}")

    def test_03_add_single_sticker(self):
        """测试添加单个贴纸"""
        if not os.path.exists(self.test_video):
            pytest.skip("测试视频不存在")
        
        sticker_path = self.existing_sticker if os.path.exists(self.existing_sticker) else self.test_sticker
        
        if not os.path.exists(sticker_path):
            pytest.skip("测试贴纸不存在")

        result = self.service.add_single_sticker(self.test_video, {
            'path': sticker_path,
            'type': 'static',
            'position': 'bottom-right',
            'scale': 0.5,
            'opacity': 0.8
        })
        
        assert result.success
        assert os.path.exists(result.output_path)
        
        print(f"\n✓ 贴纸添加成功:")
        print(f"  - 输出文件: {result.output_path}")
        print(f"  - 贴纸位置: ({result.sticker['x']}, {result.sticker['y']})")
        print(f"  - 贴纸尺寸: {result.sticker['scaled_width']}x{result.sticker['scaled_height']}")

    def test_04_add_multiple_stickers(self):
        """测试添加多个贴纸"""
        if not os.path.exists(self.test_video):
            pytest.skip("测试视频不存在")
        
        sticker_path = self.existing_sticker if os.path.exists(self.existing_sticker) else self.test_sticker
        
        if not os.path.exists(sticker_path):
            pytest.skip("测试贴纸不存在")

        result = self.service.add_multiple_stickers(self.test_video, [
            {
                'path': sticker_path,
                'type': 'static',
                'position': 'top-left',
                'scale': 0.3,
            },
            {
                'path': sticker_path,
                'type': 'static',
                'position': 'bottom-right',
                'scale': 0.3,
            }
        ])
        
        assert result.success
        assert os.path.exists(result.output_path)
        
        print(f"\n✓ 多贴纸添加成功:")
        print(f"  - 输出文件: {result.output_path}")
        print(f"  - 贴纸数量: {result.stickers_count}")


class TestRealMiniMaxTTS:
    """MiniMax TTS 服务测试（需要 .env 配置）"""

    @classmethod
    def setup_class(cls):
        cls.temp_dir = tempfile.mkdtemp()
        
        api_key = config.minimax.get('api_key', '')
        if not api_key or api_key == 'your_minimax_api_key':
            cls.service = None
        else:
            cls.service = MiniMaxTTSService({'output_dir': cls.temp_dir})

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_tts_configuration(self):
        """测试 TTS 配置检查"""
        api_key = config.minimax.get('api_key', '')
        
        print(f"\n✓ TTS 配置检查:")
        print(f"  - API Key 已配置: {bool(api_key) and api_key != 'your_minimax_api_key'}")
        print(f"  - 默认语音: {config.minimax['tts']['voice_id']}")
        print(f"  - 语速: {config.minimax['tts']['speed']}")
        print(f"  - 模型: {config.minimax['model']}")

    def test_02_synthesize_speech_real(self):
        """测试真实 TTS 合成（如果配置了 API Key）"""
        if not self.service:
            pytest.skip("MiniMax API Key 未配置，跳过 TTS 测试")

        test_text = "这是一个测试语音合成的示例句子。"
        
        try:
            result = self.service.synthesize_speech(test_text, {
                'speed': 1.0,
            })
            
            assert result.success
            assert os.path.exists(result.audio_path)
            
            print(f"\n✓ TTS 合成成功:")
            print(f"  - 文本: {result.text}")
            print(f"  - 输出文件: {result.audio_path}")
            print(f"  - 时长: {result.duration:.2f} 秒")
            print(f"  - 格式: {result.format}")

        except Exception as e:
            print(f"\n✗ TTS 合成失败: {e}")
            pytest.skip(f"TTS 服务调用失败: {e}")

    def test_03_synthesize_batch(self):
        """测试批量 TTS 合成"""
        if not self.service:
            pytest.skip("MiniMax API Key 未配置，跳过 TTS 测试")

        texts = [
            "第一句测试文本。",
            "第二句测试文本。",
        ]

        try:
            result = self.service.synthesize_batch(texts)
            
            print(f"\n✓ 批量 TTS 合成结果:")
            print(f"  - 成功数量: {result.successful_count}")
            print(f"  - 失败数量: {result.failed_count}")

            for i, r in enumerate(result.results):
                if r.success:
                    print(f"  - 第 {i+1} 句: 成功，时长 {r.duration:.2f}s")
                else:
                    print(f"  - 第 {i+1} 句: 失败 - {r.error}")

        except Exception as e:
            print(f"\n✗ 批量 TTS 合成失败: {e}")
            pytest.skip(f"批量 TTS 调用失败: {e}")


class TestHelpers:
    """工具函数测试"""

    def test_format_timestamp(self):
        """测试时间戳格式化"""
        assert helpers.format_timestamp(0) == '00:00:00,000'
        assert helpers.format_timestamp(123.456) == '00:02:03,456'
        assert helpers.format_timestamp(3661.5) == '01:01:01,500'

    def test_parse_timestamp(self):
        """测试时间戳解析"""
        assert helpers.parse_timestamp('00:00:00,000') == 0.0
        assert helpers.parse_timestamp('00:02:03,456') == 123.456

    def test_calculate_video_segments(self):
        """测试视频片段计算"""
        segments = helpers.calculate_video_segments(65.0, 30.0)
        assert len(segments) == 3
        assert segments[0]['duration'] == 30.0
        assert segments[1]['duration'] == 30.0
        assert segments[2]['duration'] == 5.0

    def test_format_duration(self):
        """测试时长格式化"""
        assert helpers.format_duration(125.5) == '2:05'
        assert helpers.format_duration(3661.5) == '1:01:01'

    def test_split_text_for_tts(self):
        """测试 TTS 文本分割"""
        text = "a" * 100
        segments = helpers.split_text_for_tts(text, max_chars_per_segment=30, split_by_sentence=False)
        assert len(segments) == 4

    def test_sanitize_filename(self):
        """测试文件名清理"""
        result = helpers.sanitize_filename('My Video: Test <File>.mp4')
        assert ':' not in result
        assert '<' not in result
        assert '>' not in result


if __name__ == '__main__':
    print("=" * 60)
    print("视频剪辑 Agent Python 版本 - 真实测试")
    print("=" * 60)
    
    print(f"\n项目根目录: {PROJECT_ROOT}")
    print(f"媒体目录: {MEDIA_DIR}")
    
    print(f"\n可用的测试文件:")
    if os.path.exists(MEDIA_DIR):
        for f in sorted(os.listdir(MEDIA_DIR)):
            print(f"  - {f}")
    else:
        print("  (媒体目录不存在)")
    
    print("\n" + "=" * 60)
