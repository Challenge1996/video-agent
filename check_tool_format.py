#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agents.video_editor_agent import switch_aspect_ratio_tool, tools
import json

print("=" * 60)
print("检查 StructuredTool 的工具定义格式")
print("=" * 60)

# 检查 get_openai_tool 方法
if hasattr(switch_aspect_ratio_tool, 'get_openai_tool'):
    print("\n=== get_openai_tool 输出 ===")
    tool_def = switch_aspect_ratio_tool.get_openai_tool()
    print(json.dumps(tool_def, indent=2, ensure_ascii=False))

# 检查 Anthropic 格式需要什么
print("\n" + "=" * 60)
print("Anthropic 工具格式参考")
print("=" * 60)
print("""
Anthropic 格式:
{
  "name": "tool_name",
  "description": "tool description",
  "input_schema": {
    "type": "object",
    "properties": {...},
    "required": [...]
  }
}
""")

# 从 OpenAI 格式转换
if hasattr(switch_aspect_ratio_tool, 'get_openai_tool'):
    tool_def = switch_aspect_ratio_tool.get_openai_tool()
    
    # 转换为 Anthropic 格式
    anthropic_tool = {
        "name": tool_def["function"]["name"],
        "description": tool_def["function"]["description"],
        "input_schema": tool_def["function"]["parameters"]
    }
    
    print("转换为 Anthropic 格式:")
    print(json.dumps(anthropic_tool, indent=2, ensure_ascii=False))

# 检查 response 中的 tool_use block 格式
print("\n" + "=" * 60)
print("Anthropic 响应中的 tool_use block 格式")
print("=" * 60)
print("""
响应 content 示例:
[
  {
    "type": "text",
    "text": "我来帮你..."
  },
  {
    "type": "tool_use",
    "id": "toolu_xxx",
    "name": "switch_aspect_ratio_tool",
    "input": {
      "video_path": "/path/to/video.mp4",
      "aspect_ratio": "9:16"
    }
  }
]

LangChain tool_calls 格式:
[
  {
    "name": "switch_aspect_ratio_tool",
    "args": {...},
    "id": "toolu_xxx"
  }
]
""")
