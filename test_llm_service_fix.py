#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agents.llm_service import MiniMaxAnthropicService, LLMConfig, LLMProvider
from src.agents.video_editor_agent import tools, switch_aspect_ratio_tool
import json

print("=" * 70)
print("测试 MiniMaxAnthropicService 的工具转换逻辑")
print("=" * 70)

# 创建服务
config = LLMConfig(
    provider=LLMProvider.MINIMAX,
    model_name="MiniMax-M2.7",
    temperature=0.7,
    max_tokens=4096,
)

service = MiniMaxAnthropicService(config)

# 测试工具转换
print("\n" + "-" * 60)
print("测试 _convert_langchain_tool_to_anthropic 方法")
print("-" * 60)

for tool in tools:
    if 'aspect' in tool.name.lower() or 'switch' in tool.name.lower():
        print(f"\n工具: {tool.name}")
        converted = service._convert_langchain_tool_to_anthropic(tool)
        print(f"转换结果:")
        print(json.dumps(converted, indent=2, ensure_ascii=False))
        break

# 测试解析 tool_calls
print("\n" + "-" * 60)
print("测试 _parse_anthropic_tool_calls 方法")
print("-" * 60)

# 模拟 Anthropic 的响应 content blocks
class MockBlock:
    def __init__(self, block_type, **kwargs):
        self.type = block_type
        for key, value in kwargs.items():
            setattr(self, key, value)

mock_content = [
    MockBlock("text", text="我来帮你将视频转换为9:16比例。"),
    MockBlock(
        "tool_use",
        id="toolu_012345",
        name="switch_aspect_ratio_tool",
        input={
            "video_path": "/path/to/video.mp4",
            "aspect_ratio": "9:16"
        }
    )
]

print(f"\n模拟响应 content blocks:")
print(f"  - text block: \"我来帮你将视频转换为9:16比例。\"")
print(f"  - tool_use block:")
print(f"      id: toolu_012345")
print(f"      name: switch_aspect_ratio_tool")
print(f"      input: {{\"video_path\": \"/path/to/video.mp4\", \"aspect_ratio\": \"9:16\"}}")

tool_calls = service._parse_anthropic_tool_calls(mock_content)

print(f"\n解析结果:")
print(json.dumps(tool_calls, indent=2, ensure_ascii=False))

# 验证格式是否符合 LangChain tool_calls 格式
expected_format = [
    {
        "name": "switch_aspect_ratio_tool",
        "args": {
            "video_path": "/path/to/video.mp4",
            "aspect_ratio": "9:16"
        },
        "id": "toolu_012345"
    }
]

print("\n" + "-" * 60)
print("验证格式")
print("-" * 60)
print(f"解析的 tool_calls: {tool_calls}")
print(f"预期格式: {expected_format}")

if tool_calls == expected_format:
    print("✅ 格式匹配！")
else:
    print("⚠️ 格式不匹配")
    print(f"  差异: {set(str(expected_format)) - set(str(tool_calls))}")

# 检查 OpenAIService 的实现是否有参考
print("\n" + "=" * 70)
print("检查 OpenAIService 的 tool calling 实现（参考）")
print("=" * 70)

from src.agents.llm_service import OpenAIService

# 检查 OpenAIService.chat 方法
print("\nOpenAIService 使用 model.bind_tools() 来绑定工具")
print("然后检查 response.tool_calls 属性")

# 总结修复
print("\n" + "=" * 70)
print("修复总结")
print("=" * 70)
print("""
之前的问题：
1. MiniMaxAnthropicService.chat() 中，if tools: pass 完全忽略了 tools 参数
2. MiniMaxAnthropicService._parse_anthropic_response() 中，tool_calls=[] 硬编码为空

修复内容：
1. 添加了 _convert_langchain_tool_to_anthropic() 方法
   - 将 LangChain StructuredTool 转换为 Anthropic 工具格式
   - 优先使用 get_openai_tool()，否则使用 args_schema

2. 添加了 _parse_anthropic_tool_calls() 方法
   - 解析 Anthropic 响应中的 tool_use blocks
   - 转换为 LangChain tool_calls 格式

3. 修改了 _parse_anthropic_response() 方法
   - 调用 _parse_anthropic_tool_calls() 来解析工具调用
   - tool_calls 返回 None 而不是空列表（如果没有工具调用）

4. 修改了 chat() 方法
   - 将 tools 参数转换为 Anthropic 格式
   - 添加到 create_kwargs 中传递给 API

另外还修复了 ToolExecutor.execute_tool() 中的问题：
- 之前直接调用 tool_func(**parameters)
- 现在检查是否有 ainvoke/invoke 方法，优先使用这些方法
- 因为 LangChain StructuredTool 没有 __call__ 方法
""")
