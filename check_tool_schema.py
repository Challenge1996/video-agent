#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agents.video_editor_agent import switch_aspect_ratio_tool
import json

print("=" * 60)
print("检查 StructuredTool 详细信息")
print("=" * 60)

# 工具名和描述
print(f"\n工具名: {switch_aspect_ratio_tool.name}")
print(f"工具描述: {switch_aspect_ratio_tool.description[:150]}...")

# 检查 args_schema
print("\n" + "-" * 40)
print("args_schema:")
schema = switch_aspect_ratio_tool.args_schema
print(f"  类型: {type(schema)}")
print(f"  Schema 类名: {schema.__name__ if hasattr(schema, '__name__') else 'N/A'}")

# 获取 JSON Schema
if hasattr(schema, 'model_json_schema'):
    json_schema = schema.model_json_schema()
    print("\n  JSON Schema:")
    print(json.dumps(json_schema, indent=2, ensure_ascii=False))

# 检查直接转换为 Anthropic 格式
print("\n" + "=" * 60)
print("转换为 Anthropic 工具格式")
print("=" * 60)

anthropic_tool = {
    "name": switch_aspect_ratio_tool.name,
    "description": switch_aspect_ratio_tool.description,
    "input_schema": switch_aspect_ratio_tool.args_schema.model_json_schema()
}

print(json.dumps(anthropic_tool, indent=2, ensure_ascii=False))

# 检查 LangChain 的 OpenAIFunctionsAgentOutputParser 或类似的
print("\n" + "=" * 60)
print("检查如何解析 tool_use 响应")
print("=" * 60)

# 模拟 Anthropic 的 tool_use 响应
sample_response_content = [
    {
        "type": "text",
        "text": "我来帮你将视频转换为9:16比例。"
    },
    {
        "type": "tool_use",
        "id": "toolu_012345",
        "name": "switch_aspect_ratio_tool",
        "input": {
            "video_path": "/path/to/video.mp4",
            "aspect_ratio": "9:16"
        }
    }
]

print("Anthropic 响应格式:")
print(json.dumps(sample_response_content, indent=2, ensure_ascii=False))

print("\nLangChain tool_calls 格式:")
tool_calls_format = [
    {
        "name": "switch_aspect_ratio_tool",
        "args": {
            "video_path": "/path/to/video.mp4",
            "aspect_ratio": "9:16"
        },
        "id": "toolu_012345"
    }
]
print(json.dumps(tool_calls_format, indent=2, ensure_ascii=False))
