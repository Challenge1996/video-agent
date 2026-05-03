import os
import sys
import tempfile
import shutil
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Tuple

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.modules.video_resizer import (
    VideoResizer,
    VideoResizeResult,
    VideoCropResult,
    AspectRatioResult,
    COMMON_ASPECT_RATIOS,
    COMMON_RESOLUTIONS,
    AspectRatio,
)


class TestAspectRatioClass:
    """AspectRatio 类测试"""

    def test_aspect_ratio_creation(self):
        """测试创建 AspectRatio 实例"""
        ar = AspectRatio('9:16', 9, 16)
        
        assert ar.ratio == '9:16'
        assert ar.width == 9
        assert ar.height == 16
        assert ar.value == 9 / 16
        
        print(f"\n✓ AspectRatio 创建成功:")
        print(f"  - 比例: {ar.ratio}")
        print(f"  - 数值: {ar.value:.4f}")

    def test_common_aspect_ratios(self):
        """测试常用画幅比常量"""
        assert '9:16' in COMMON_ASPECT_RATIOS
        assert '16:9' in COMMON_ASPECT_RATIOS
        assert '1:1' in COMMON_ASPECT_RATIOS
        assert '4:3' in COMMON_ASPECT_RATIOS
        assert '3:4' in COMMON_ASPECT_RATIOS
        
        ar_9_16 = COMMON_ASPECT_RATIOS['9:16']
        assert ar_9_16.width == 9
        assert ar_9_16.height == 16
        assert abs(ar_9_16.value - 0.5625) < 0.001
        
        ar_16_9 = COMMON_ASPECT_RATIOS['16:9']
        assert abs(ar_16_9.value - 1.7778) < 0.001
        
        print(f"\n✓ 常用画幅比验证成功:")
        for name, ar in COMMON_ASPECT_RATIOS.items():
            print(f"  - {name}: {ar.width}:{ar.height} = {ar.value:.4f}")

    def test_common_resolutions(self):
        """测试常用分辨率常量"""
        assert '1080p' in COMMON_RESOLUTIONS
        assert '720p' in COMMON_RESOLUTIONS
        assert '480p' in COMMON_RESOLUTIONS
        assert '360p' in COMMON_RESOLUTIONS
        assert '4k' in COMMON_RESOLUTIONS
        assert '1080x1920' in COMMON_RESOLUTIONS
        assert '720x1280' in COMMON_RESOLUTIONS
        
        assert COMMON_RESOLUTIONS['1080p'] == (1920, 1080)
        assert COMMON_RESOLUTIONS['720p'] == (1280, 720)
        assert COMMON_RESOLUTIONS['1080x1920'] == (1080, 1920)
        assert COMMON_RESOLUTIONS['720x1280'] == (720, 1280)
        
        print(f"\n✓ 常用分辨率验证成功:")
        for name, res in COMMON_RESOLUTIONS.items():
            print(f"  - {name}: {res[0]}x{res[1]}")


class TestVideoResizer:
    """VideoResizer 类测试"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.resizer = VideoResizer({
            'output_dir': self.temp_dir,
            'temp_dir': self.temp_dir,
        })

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """测试初始化"""
        assert self.resizer is not None
        assert self.resizer.options['output_dir'] == self.temp_dir
        assert self.resizer.options['temp_dir'] == self.temp_dir
        
        print(f"\n✓ VideoResizer 初始化成功:")
        print(f"  - 输出目录: {self.resizer.options['output_dir']}")
        print(f"  - 临时目录: {self.resizer.options['temp_dir']}")

    def test_calculate_aspect_ratio(self):
        """测试计算画幅比"""
        test_cases = [
            (1920, 1080, '16:9'),
            (1080, 1920, '9:16'),
            (1280, 720, '16:9'),
            (720, 1280, '9:16'),
            (1080, 1080, '1:1'),
            (1440, 1080, '4:3'),
        ]
        
        print(f"\n✓ 画幅比计算测试:")
        for width, height, expected in test_cases:
            result = self.resizer._calculate_aspect_ratio(width, height)
            print(f"  - {width}x{height} -> {result} (期望: {expected})")

    def test_get_video_resolution_info(self):
        """测试获取视频分辨率信息（模拟）"""
        original_method = self.resizer._get_video_dimensions
        
        def mock_get_dimensions(video_path: str) -> Tuple[int, int]:
            return (1920, 1080)
        
        self.resizer._get_video_dimensions = mock_get_dimensions
        
        info = self.resizer.get_video_resolution_info("test.mp4")
        
        assert info['width'] == 1920
        assert info['height'] == 1080
        assert info['aspect_ratio'] == '16:9'
        assert info['resolution'] == '1920x1080'
        assert info['orientation'] == 'landscape'
        
        self.resizer._get_video_dimensions = original_method
        
        print(f"\n✓ 视频分辨率信息获取成功:")
        print(f"  - 分辨率: {info['resolution']}")
        print(f"  - 画幅比: {info['aspect_ratio']}")
        print(f"  - 方向: {info['orientation']}")

    def test_generate_output_path(self):
        """测试生成输出路径"""
        input_path = '/test/video.mp4'
        suffix = '720p'
        
        output_path = self.resizer._generate_output_path(input_path, suffix, self.temp_dir)
        
        assert os.path.dirname(output_path) == self.temp_dir
        assert 'video_720p' in os.path.basename(output_path)
        assert output_path.endswith('.mp4')
        
        print(f"\n✓ 输出路径生成成功:")
        print(f"  - 输入: {input_path}")
        print(f"  - 输出: {output_path}")


class TestResultDataclasses:
    """结果数据类测试"""

    def test_video_resize_result(self):
        """测试 VideoResizeResult"""
        result = VideoResizeResult(
            success=True,
            output_path='/output/video_720p.mp4',
            original_width=1920,
            original_height=1080,
            output_width=1280,
            output_height=720,
            original_aspect_ratio='16:9',
            output_aspect_ratio='16:9',
            operation='resize'
        )
        
        assert result.success is True
        assert result.output_path == '/output/video_720p.mp4'
        assert result.original_width == 1920
        assert result.output_height == 720
        
        print(f"\n✓ VideoResizeResult 创建成功:")
        print(f"  - 原始: {result.original_width}x{result.original_height}")
        print(f"  - 输出: {result.output_width}x{result.output_height}")

    def test_video_crop_result(self):
        """测试 VideoCropResult"""
        result = VideoCropResult(
            success=True,
            output_path='/output/video_cropped.mp4',
            original_width=1920,
            original_height=1080,
            crop_x=420,
            crop_y=0,
            crop_width=1080,
            crop_height=1080
        )
        
        assert result.success is True
        assert result.crop_x == 420
        assert result.crop_width == 1080
        
        print(f"\n✓ VideoCropResult 创建成功:")
        print(f"  - 裁剪区域: ({result.crop_x}, {result.crop_y}) {result.crop_width}x{result.crop_height}")

    def test_aspect_ratio_result(self):
        """测试 AspectRatioResult"""
        result = AspectRatioResult(
            success=True,
            output_path='/output/video_douyin.mp4',
            original_width=1920,
            original_height=1080,
            original_aspect_ratio='16:9',
            target_aspect_ratio='9:16',
            output_width=720,
            output_height=1280,
            method='crop'
        )
        
        assert result.success is True
        assert result.original_aspect_ratio == '16:9'
        assert result.target_aspect_ratio == '9:16'
        assert result.method == 'crop'
        
        print(f"\n✓ AspectRatioResult 创建成功:")
        print(f"  - 原始: {result.original_aspect_ratio}")
        print(f"  - 目标: {result.target_aspect_ratio}")
        print(f"  - 方法: {result.method}")


class TestAgentTools:
    """Agent tools 测试"""

    def test_tools_list_contains_new_tools(self):
        """测试 tools 列表包含新工具"""
        from src.agents.video_editor_agent import tools
        
        tool_names = [tool.name for tool in tools]
        
        assert 'resize_video_tool' in tool_names
        assert 'crop_video_tool' in tool_names
        assert 'convert_aspect_ratio_tool' in tool_names
        assert 'convert_to_douyin_format_tool' in tool_names
        
        print(f"\n✓ Agent tools 列表验证成功:")
        print(f"  - 工具总数: {len(tools)}")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description[:50]}...")

    def test_tool_descriptions(self):
        """测试工具描述"""
        from src.agents.video_editor_agent import (
            resize_video_tool,
            crop_video_tool,
            convert_aspect_ratio_tool,
            convert_to_douyin_format_tool,
        )
        
        assert resize_video_tool.description is not None
        assert '调整视频分辨率' in resize_video_tool.description
        
        assert crop_video_tool.description is not None
        assert '裁剪视频画面' in crop_video_tool.description
        
        assert convert_aspect_ratio_tool.description is not None
        assert '转换视频画幅比' in convert_aspect_ratio_tool.description
        
        assert convert_to_douyin_format_tool.description is not None
        assert '抖音竖屏格式' in convert_to_douyin_format_tool.description
        
        print(f"\n✓ 工具描述验证成功:")
        print(f"  - resize_video_tool: {resize_video_tool.description[:60]}...")
        print(f"  - crop_video_tool: {crop_video_tool.description[:60]}...")
        print(f"  - convert_aspect_ratio_tool: {convert_aspect_ratio_tool.description[:60]}...")
        print(f"  - convert_to_douyin_format_tool: {convert_to_douyin_format_tool.description[:60]}...")

    def test_video_editor_agent_methods(self):
        """测试 VideoEditorAgent 新方法"""
        from src.agents.video_editor_agent import VideoEditorAgent
        
        agent = VideoEditorAgent()
        
        assert hasattr(agent, 'video_resizer')
        assert hasattr(agent, 'resize_video')
        assert hasattr(agent, 'crop_video')
        assert hasattr(agent, 'convert_aspect_ratio')
        assert hasattr(agent, 'convert_to_douyin_format')
        
        print(f"\n✓ VideoEditorAgent 新方法验证成功:")
        print(f"  - video_resizer 实例: {agent.video_resizer is not None}")
        print(f"  - resize_video 方法: {callable(agent.resize_video)}")
        print(f"  - crop_video 方法: {callable(agent.crop_video)}")
        print(f"  - convert_aspect_ratio 方法: {callable(agent.convert_aspect_ratio)}")
        print(f"  - convert_to_douyin_format 方法: {callable(agent.convert_to_douyin_format)}")


if __name__ == '__main__':
    print("=" * 60)
    print("VideoResizer 模块 - 单元测试")
    print("=" * 60)
    
    pytest.main([__file__, "-v", "-s"])
