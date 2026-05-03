#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agents.video_editor_agent import switch_aspect_ratio_tool

test_video = '/Users/yajun/Documents/video-agent/media/test_video_1920x1080.mp4'

if not os.path.exists(test_video):
    print(f'测试视频不存在: {test_video}')
    sys.exit(1)

print('=== 测试 switch_aspect_ratio_tool ===')
print(f'输入视频: {test_video}')
print(f'参数: aspect_ratio="9:16", method="crop", target_resolution="720x1280"')
print()

result = switch_aspect_ratio_tool.invoke({
    'video_path': test_video,
    'aspect_ratio': '9:16',
    'method': 'crop',
    'target_resolution': '720x1280'
})

print('结果:')
print(f'  success: {result.get("success")}')
if result.get('success'):
    print(f'  original_resolution: {result.get("original_resolution")}')
    print(f'  output_resolution: {result.get("output_resolution")}')
    print(f'  method_description: {result.get("method_description")}')
    print(f'  output_path: {result.get("output_path")}')
    print(f'  output_filename: {result.get("output_filename")}')
    
    output_path = result.get('output_path')
    if output_path and os.path.exists(output_path):
        print(f'  文件存在: Yes')
        file_size = os.path.getsize(output_path)
        print(f'  文件大小: {file_size / 1024 / 1024:.2f} MB')
    else:
        print(f'  文件存在: No - 这是问题!')
else:
    print(f'  error: {result.get("error")}')
