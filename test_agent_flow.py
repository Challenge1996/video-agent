#!/usr/bin/env python3
import os
import sys
import asyncio
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agents.video_editor_agent import SmartVideoEditorAgent
from src.config.config import config

async def main():
    print("=" * 60)
    print("测试 Agent 工具调用流程")
    print("=" * 60)
    
    # 检查输出目录
    output_dir = config.video.get('output_dir', './output')
    if not os.path.exists(output_dir):
        print(f"创建输出目录: {output_dir}")
        os.makedirs(output_dir, exist_ok=True)
    print(f"输出目录: {os.path.abspath(output_dir)}")
    
    # 创建 Agent
    print("\n创建 Agent 实例...")
    agent = SmartVideoEditorAgent()
    
    # 检查注册的工具
    print("\n检查注册的工具:")
    registered_tools = agent.tool_executor.get_registered_tools()
    for tool_name in registered_tools.keys():
        print(f"  - {tool_name}")
    
    # 测试视频路径
    test_video = '/Users/yajun/Documents/video-agent/media/test_video_1920x1080.mp4'
    print(f"\n测试视频: {test_video}")
    print(f"视频存在: {os.path.exists(test_video)}")
    
    # 方案1: 直接调用 switch_aspect_ratio_tool
    print("\n" + "=" * 60)
    print("方案1: 直接调用 switch_aspect_ratio_tool")
    print("=" * 60)
    
    from src.agents.video_editor_agent import switch_aspect_ratio_tool
    
    result1 = switch_aspect_ratio_tool.invoke({
        'video_path': test_video,
        'aspect_ratio': '9:16',
        'method': 'crop',
        'target_resolution': '720x1280'
    })
    
    print(f"结果: {json.dumps(result1, indent=2, ensure_ascii=False)}")
    
    if result1.get('success'):
        output_path1 = result1.get('output_path')
        if output_path1:
            abs_path1 = os.path.abspath(output_path1)
            print(f"\n输出文件路径: {abs_path1}")
            print(f"文件存在: {os.path.exists(abs_path1)}")
            if os.path.exists(abs_path1):
                print(f"文件大小: {os.path.getsize(abs_path1) / 1024:.2f} KB")
    
    # 方案2: 通过 tool_executor 调用
    print("\n" + "=" * 60)
    print("方案2: 通过 tool_executor 调用 switch_aspect_ratio_tool")
    print("=" * 60)
    
    execution_result = await agent.tool_executor.execute_tool(
        'switch_aspect_ratio_tool',
        {
            'video_path': test_video,
            'aspect_ratio': '9:16',
            'method': 'crop',
            'target_resolution': '720x1280'
        }
    )
    
    print(f"执行结果:")
    print(f"  success: {execution_result.success}")
    print(f"  tool_name: {execution_result.tool_name}")
    if execution_result.success:
        print(f"  result: {json.dumps(execution_result.result, indent=2, ensure_ascii=False)}")
        output_path2 = execution_result.result.get('output_path')
        if output_path2:
            abs_path2 = os.path.abspath(output_path2)
            print(f"\n  输出文件路径: {abs_path2}")
            print(f"  文件存在: {os.path.exists(abs_path2)}")
    else:
        print(f"  error: {execution_result.error}")
    
    # 方案3: 通过 Agent chat 方法模拟
    print("\n" + "=" * 60)
    print("方案3: 通过 Agent chat 方法模拟用户输入")
    print("=" * 60)
    
    user_input = f"请把这个文件 {test_video} 转化为9:16比例视频"
    print(f"用户输入: {user_input}")
    
    chat_response = await agent.chat(user_input)
    
    print(f"\nChat 响应:")
    print(f"  is_complete: {chat_response.is_complete}")
    print(f"  content: {chat_response.content[:500]}...")
    if chat_response.tool_calls:
        print(f"  tool_calls: {chat_response.tool_calls}")
    if chat_response.tool_results:
        print(f"  tool_results: {chat_response.tool_results}")
    
    # 检查 output 目录
    print("\n" + "=" * 60)
    print("检查 output 目录中的文件")
    print("=" * 60)
    
    output_files = os.listdir(output_dir) if os.path.exists(output_dir) else []
    for f in sorted(output_files):
        f_path = os.path.join(output_dir, f)
        f_size = os.path.getsize(f_path) / 1024
        print(f"  - {f} ({f_size:.2f} KB)")

if __name__ == '__main__':
    asyncio.run(main())
