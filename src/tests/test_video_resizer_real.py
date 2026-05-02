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

sys.path.insert(0, str(PROJECT_ROOT))

from src.config.config import config
from src.utils.helpers import helpers
from src.modules.video_resizer import VideoResizer, COMMON_ASPECT_RATIOS, COMMON_RESOLUTIONS


class TestRealVideoResizer:
    """使用真实 FFmpeg 的视频尺寸调整测试"""

    @classmethod
    def setup_class(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.resizer = VideoResizer({
            'output_dir': cls.temp_dir,
            'temp_dir': cls.temp_dir,
        })

        cls.test_video = str(MEDIA_DIR / 'test_video.mp4')
        if not os.path.exists(cls.test_video):
            pytest.skip(f"测试视频不存在: {cls.test_video}")
        
        info = cls.resizer._get_video_dimensions(cls.test_video)
        cls.original_width, cls.original_height = info
        cls.original_aspect = cls.resizer._calculate_aspect_ratio(cls.original_width, cls.original_height)

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_get_video_resolution_info(self):
        """测试获取视频分辨率信息"""
        info = self.resizer.get_video_resolution_info(self.test_video)
        
        assert info['width'] == self.original_width
        assert info['height'] == self.original_height
        assert info['resolution'] == f"{self.original_width}x{self.original_height}"
        
        print(f"\n✓ 视频分辨率信息获取成功:")
        print(f"  - 分辨率: {info['resolution']}")
        print(f"  - 画幅比: {info['aspect_ratio']}")
        print(f"  - 方向: {info['orientation']}")

    def test_02_resize_video_to_720p(self):
        """测试调整视频分辨率到 720p"""
        print(f"\n原始视频分辨率: {self.original_width}x{self.original_height}")
        
        result = self.resizer.resize_video(
            self.test_video,
            resolution='720p'
        )
        
        assert result.success, f"调整分辨率失败: {result.error}"
        assert os.path.exists(result.output_path)
        
        output_width, output_height = self.resizer._get_video_dimensions(result.output_path)
        
        expected_ratio = self.original_width / self.original_height
        actual_ratio = output_width / output_height
        
        assert abs(expected_ratio - actual_ratio) < 0.01
        
        print(f"\n✓ 分辨率调整成功:")
        print(f"  - 原始: {result.original_width}x{result.original_height}")
        print(f"  - 输出: {result.output_width}x{result.output_height}")
        print(f"  - 输出文件: {result.output_path}")
        
        output_info = self.resizer._get_video_dimensions(result.output_path)
        print(f"  - 实际输出分辨率: {output_info[0]}x{output_info[1]}")

    def test_03_resize_video_by_width(self):
        """测试按宽度调整视频"""
        target_width = 640
        
        result = self.resizer.resize_video(
            self.test_video,
            target_width=target_width
        )
        
        assert result.success
        assert os.path.exists(result.output_path)
        
        print(f"\n✓ 按宽度调整成功:")
        print(f"  - 目标宽度: {target_width}")
        print(f"  - 输出: {result.output_width}x{result.output_height}")

    def test_04_crop_video_by_aspect_ratio_9_16(self):
        """测试按 9:16 画幅比裁剪"""
        result = self.resizer.crop_video(
            self.test_video,
            aspect_ratio='9:16'
        )
        
        assert result.success
        assert os.path.exists(result.output_path)
        
        output_width, output_height = self.resizer._get_video_dimensions(result.output_path)
        output_aspect = self.resizer._calculate_aspect_ratio(output_width, output_height)
        
        target_ratio = 9 / 16
        actual_ratio = output_width / output_height
        
        print(f"\n✓ 9:16 画幅比裁剪测试:")
        print(f"  - 原始: {self.original_width}x{self.original_height} ({self.original_aspect})")
        print(f"  - 裁剪区域: ({result.crop_x}, {result.crop_y}) {result.crop_width}x{result.crop_height}")
        print(f"  - 输出文件: {result.output_path}")
        print(f"  - 输出分辨率: {output_width}x{output_height}")
        print(f"  - 输出画幅比: {output_aspect}")
        print(f"  - 目标比例: {target_ratio:.4f}")
        print(f"  - 实际比例: {actual_ratio:.4f}")

    def test_05_convert_aspect_ratio_crop(self):
        """测试转换画幅比 - crop 方式（中心裁剪）"""
        target_aspect = '9:16'
        
        result = self.resizer.convert_aspect_ratio(
            self.test_video,
            target_aspect=target_aspect,
            method='crop',
            target_resolution='720x1280'
        )
        
        assert result.success
        assert os.path.exists(result.output_path)
        
        output_width, output_height = self.resizer._get_video_dimensions(result.output_path)
        
        print(f"\n✓ 画幅比转换成功 (crop 方式):")
        print(f"  - 原始: {result.original_aspect_ratio} ({result.original_width}x{result.original_height})")
        print(f"  - 目标: {result.target_aspect_ratio}")
        print(f"  - 输出: {result.output_width}x{result.output_height}")
        print(f"  - 实际输出: {output_width}x{output_height}")
        print(f"  - 方法: {result.method}")
        print(f"  - 输出文件: {result.output_path}")

    def test_06_convert_aspect_ratio_pad(self):
        """测试转换画幅比 - pad 方式（加黑边）"""
        target_aspect = '9:16'
        
        result = self.resizer.convert_aspect_ratio(
            self.test_video,
            target_aspect=target_aspect,
            method='pad',
            target_resolution='720x1280',
            pad_color='black'
        )
        
        assert result.success
        assert os.path.exists(result.output_path)
        
        output_width, output_height = self.resizer._get_video_dimensions(result.output_path)
        
        print(f"\n✓ 画幅比转换成功 (pad 方式):")
        print(f"  - 原始: {result.original_aspect_ratio} ({result.original_width}x{result.original_height})")
        print(f"  - 目标: {result.target_aspect_ratio}")
        print(f"  - 输出: {result.output_width}x{result.output_height}")
        print(f"  - 实际输出: {output_width}x{output_height}")
        print(f"  - 方法: {result.method} (加黑边填充)")
        print(f"  - 输出文件: {result.output_path}")

    def test_07_convert_to_douyin_format(self):
        """测试一键转换为抖音竖屏格式"""
        result = self.resizer.convert_to_douyin_format(
            self.test_video,
            method='crop',
            target_resolution='720x1280'
        )
        
        assert result.success
        assert os.path.exists(result.output_path)
        
        output_width, output_height = self.resizer._get_video_dimensions(result.output_path)
        
        method_desc = '中心裁剪' if result.method == 'crop' else '加黑边填充' if result.method == 'pad' else '无需转换'
        
        print(f"\n✓ 抖音竖屏格式转换成功:")
        print(f"  - 原始: {result.original_aspect_ratio} ({result.original_width}x{result.original_height})")
        print(f"  - 目标: {result.target_aspect_ratio} (抖音竖屏)")
        print(f"  - 输出: {result.output_width}x{result.output_height}")
        print(f"  - 实际输出: {output_width}x{output_height}")
        print(f"  - 方法: {method_desc}")
        print(f"  - 输出文件: {result.output_path}")
        
        expected_ratio = 9 / 16
        actual_ratio = output_width / output_height
        assert abs(expected_ratio - actual_ratio) < 0.02, f"画幅比不符合预期: 期望 {expected_ratio:.4f}, 实际 {actual_ratio:.4f}"

    def test_08_crop_video_exact_region(self):
        """测试精确区域裁剪"""
        if self.original_width < 500 or self.original_height < 500:
            pytest.skip("视频分辨率太小，无法进行精确区域裁剪测试")
        
        crop_width = min(self.original_width, 500)
        crop_height = min(self.original_height, 500)
        
        result = self.resizer.crop_video(
            self.test_video,
            crop_width=crop_width,
            crop_height=crop_height,
            crop_x=100,
            crop_y=100
        )
        
        assert result.success
        assert os.path.exists(result.output_path)
        
        output_width, output_height = self.resizer._get_video_dimensions(result.output_path)
        
        print(f"\n✓ 精确区域裁剪成功:")
        print(f"  - 裁剪位置: ({result.crop_x}, {result.crop_y})")
        print(f"  - 裁剪尺寸: {result.crop_width}x{result.crop_height}")
        print(f"  - 输出尺寸: {output_width}x{output_height}")
        print(f"  - 输出文件: {result.output_path}")

    def test_09_resize_video_custom_resolution(self):
        """测试自定义分辨率调整"""
        custom_resolution = '640x360'
        
        result = self.resizer.resize_video(
            self.test_video,
            resolution=custom_resolution
        )
        
        assert result.success
        assert os.path.exists(result.output_path)
        
        output_width, output_height = self.resizer._get_video_dimensions(result.output_path)
        
        print(f"\n✓ 自定义分辨率调整成功:")
        print(f"  - 目标分辨率: {custom_resolution}")
        print(f"  - 输出: {result.output_width}x{result.output_height}")
        print(f"  - 实际输出: {output_width}x{output_height}")


class TestCLICommands:
    """CLI 命令测试"""

    @classmethod
    def setup_class(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_video = str(MEDIA_DIR / 'test_video.mp4')
        
        if not os.path.exists(cls.test_video):
            pytest.skip(f"测试视频不存在: {cls.test_video}")

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_cli_help_resize(self):
        """测试 resize 命令帮助"""
        import subprocess
        
        result = subprocess.run(
            [sys.executable, '-m', 'src.index', 'resize', '--help'],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT)
        )
        
        assert result.returncode == 0
        assert '--width' in result.stdout or '--width' in result.stdout
        assert '分辨率' in result.stdout or 'resolution' in result.stdout
        
        print(f"\n✓ resize 命令帮助验证成功")

    def test_cli_help_crop(self):
        """测试 crop 命令帮助"""
        import subprocess
        
        result = subprocess.run(
            [sys.executable, '-m', 'src.index', 'crop', '--help'],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT)
        )
        
        assert result.returncode == 0
        
        print(f"\n✓ crop 命令帮助验证成功")

    def test_cli_help_aspect(self):
        """测试 aspect 命令帮助"""
        import subprocess
        
        result = subprocess.run(
            [sys.executable, '-m', 'src.index', 'aspect', '--help'],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT)
        )
        
        assert result.returncode == 0
        
        print(f"\n✓ aspect 命令帮助验证成功")

    def test_cli_help_douyin(self):
        """测试 douyin 命令帮助"""
        import subprocess
        
        result = subprocess.run(
            [sys.executable, '-m', 'src.index', 'douyin', '--help'],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT)
        )
        
        assert result.returncode == 0
        assert '抖音' in result.stdout or 'douyin' in result.stdout.lower()
        
        print(f"\n✓ douyin 命令帮助验证成功")


if __name__ == '__main__':
    print("=" * 60)
    print("VideoResizer 模块 - 真实视频测试")
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
    
    pytest.main([__file__, "-v", "-s"])
