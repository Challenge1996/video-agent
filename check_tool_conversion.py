#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agents.video_editor_agent import tools
import json

print("=" * 60)
print("检查 tools 列表中工具的类型")
print("=" * 60)

for i, tool in enumerate(tools):
    print(f"\n--- 工具 {i+1}: {tool.name} ---")
    print(f"  类型: {type(tool)}")
    print(f"  描述: {tool.description[:80]}...")
    
    # 检查是否是 LangChain StructuredTool
    if hasattr(tool, 'get_openai_tool'):
        print(f"  有 get_openai_tool 方法: Yes")
        
        # 检查 OpenAI 格式
        openai_tool = tool.get_openai_tool()
        print(f"  OpenAI 格式: {json.dumps(openai_tool, indent=2, ensure_ascii=False)[:500]}...")
    
    # 检查 args_schema
    if hasattr(tool, 'args_schema'):
        print(f"  有 args_schema: Yes")

print("\n" + "=" * 60)
print("LangChain StructuredTool 到 Anthropic 格式的转换")
print("=" * 60)

def convert_to_anthropic_tool(tool):
    """将 LangChain StructuredTool 转换为 Anthropic 工具格式"""
    # 方式1: 使用 get_openai_tool，然后转换
    if hasattr(tool, 'get_openai_tool'):
        openai_tool = tool.get_openai_tool()
        # OpenAI 格式: {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
        # Anthropic 格式: {"name": ..., "description": ..., "input_schema": ...}
        func = openai_tool.get('function', {})
        return {
            "name": func.get('name', tool.name),
            "description": func.get('description', tool.description),
            "input_schema": func.get('parameters', {})
        }
    
    # 方式2: 直接使用属性
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.args_schema.model_json_schema() if hasattr(tool, 'args_schema') else {}
    }

# 测试转换
sample_tool = tools[0]  # 第一个工具
print(f"\n转换示例 ({sample_tool.name}):")
converted = convert_to_anthropic_tool(sample_tool)
print(json.dumps(converted, indent=2, ensure_ascii=False))

# 测试 switch_aspect_ratio_tool
print("\n" + "=" * 60)
print("switch_aspect_ratio_tool 转换结果")
print("=" * 60)

for tool in tools:
    if 'aspect' in tool.name.lower() or 'switch' in tool.name.lower():
        converted = convert_to_anthropic_tool(tool)
        print(json.dumps(converted, indent=2, ensure_ascii=False))
        break
