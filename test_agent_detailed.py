#!/usr/bin/env python3
import os
import sys
import asyncio
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agents.video_editor_agent import SmartVideoEditorAgent
from src.agents.llm_service import get_llm_service
from src.agents.video_editor_agent import tools
from src.config.config import config

async def main():
    print("=" * 70)
    print("详细测试：检查 Agent 工具调用和结果传递")
    print("=" * 70)
    
    agent = SmartVideoEditorAgent()
    llm_service = get_llm_service()
    
    test_video = '/Users/yajun/Documents/video-agent/media/test_video_1920x1080.mp4'
    
    print(f"\n测试视频: {test_video}")
    print(f"视频存在: {os.path.exists(test_video)}")
    
    # 步骤1：先模拟第一次 LLM 调用，看看它会选择什么工具
    print("\n" + "=" * 70)
    print("步骤1：检查 LLM 会选择什么工具")
    print("=" * 70)
    
    user_input = f"请把这个文件 {test_video} 转化为9:16比例视频"
    
    messages = [
        {"role": "system", "content": "你是一个视频编辑助手。当用户说'转换为9:16'或'切换画幅比'时，使用 switch_aspect_ratio_tool 工具。"},
        {"role": "user", "content": user_input}
    ]
    
    from langchain_core.messages import HumanMessage, SystemMessage
    
    langchain_messages = [
        SystemMessage(content="你是一个视频编辑助手。可用工具：switch_aspect_ratio_tool（切换画幅比，参数：video_path, aspect_ratio='9:16', method='crop', target_resolution='720x1280'）"),
        HumanMessage(content=user_input)
    ]
    
    print(f"用户输入: {user_input}")
    print("\n调用 LLM 并传入工具定义...")
    
    response = await llm_service.chat(langchain_messages, tools=tools)
    
    print(f"\nLLM 响应:")
    print(f"  Content: {response.content[:200] if response.content else 'None'}...")
    print(f"  Tool calls: {response.tool_calls}")
    
    if response.tool_calls:
        for tc in response.tool_calls:
            print(f"\n  工具调用详情:")
            print(f"    工具名: {tc.get('name')}")
            print(f"    参数: {json.dumps(tc.get('args', {}), indent=4, ensure_ascii=False)}")
    
    # 步骤2：如果选择了 switch_aspect_ratio_tool，手动执行并检查结果
    print("\n" + "=" * 70)
    print("步骤2：手动执行 switch_aspect_ratio_tool 并检查结果")
    print("=" * 70)
    
    from src.agents.video_editor_agent import switch_aspect_ratio_tool
    
    # 使用 LLM 可能传递的参数格式
    test_params1 = {
        'video_path': test_video,
        'aspect_ratio': '9:16'
    }
    
    print(f"\n测试参数1 (简化): {test_params1}")
    result1 = switch_aspect_ratio_tool.invoke(test_params1)
    print(f"结果1: {json.dumps(result1, indent=2, ensure_ascii=False)}")
    
    # 检查文件是否存在
    if result1.get('success'):
        output_path1 = result1.get('output_path')
        abs_path1 = os.path.abspath(output_path1)
        print(f"\n输出文件1: {abs_path1}")
        print(f"文件存在: {os.path.exists(abs_path1)}")
        
        if os.path.exists(abs_path1):
            print(f"文件大小: {os.path.getsize(abs_path1) / 1024:.2f} KB")
        else:
            print("⚠️ 文件不存在！")
    else:
        print(f"⚠️ 执行失败: {result1.get('error')}")
    
    # 步骤3：测试完整的参数
    print("\n" + "=" * 70)
    print("步骤3：测试完整参数")
    print("=" * 70)
    
    test_params2 = {
        'video_path': test_video,
        'aspect_ratio': '9:16',
        'method': 'crop',
        'target_resolution': '720x1280'
    }
    
    print(f"测试参数2 (完整): {test_params2}")
    result2 = switch_aspect_ratio_tool.invoke(test_params2)
    print(f"结果2: {json.dumps(result2, indent=2, ensure_ascii=False)}")
    
    # 检查文件
    if result2.get('success'):
        output_path2 = result2.get('output_path')
        abs_path2 = os.path.abspath(output_path2)
        print(f"\n输出文件2: {abs_path2}")
        print(f"文件存在: {os.path.exists(abs_path2)}")
    
    # 步骤4：检查 output 目录
    print("\n" + "=" * 70)
    print("步骤4：检查 output 目录")
    print("=" * 70)
    
    output_dir = config.video.get('output_dir', './output')
    abs_output_dir = os.path.abspath(output_dir)
    
    print(f"输出目录: {abs_output_dir}")
    print(f"目录存在: {os.path.exists(abs_output_dir)}")
    
    if os.path.exists(abs_output_dir):
        files = os.listdir(abs_output_dir)
        print(f"\n目录中的文件 ({len(files)} 个):")
        for f in sorted(files):
            f_path = os.path.join(abs_output_dir, f)
            f_size = os.path.getsize(f_path) / 1024
            f_mtime = os.path.getmtime(f_path)
            import time
            f_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(f_mtime))
            print(f"  - {f} ({f_size:.2f} KB, {f_time})")

if __name__ == '__main__':
    asyncio.run(main())
