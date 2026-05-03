#!/usr/bin/env python3
"""
测试脚本：验证 /api/chat 接口和核心 Agent 功能
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

print("=" * 60)
print("视频剪辑 Agent - 诊断测试")
print("=" * 60)

print("\n【1/5】检查环境变量配置...")
print("-" * 60)

env_vars = {
    "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "未设置"),
    "LLM_MODEL": os.getenv("LLM_MODEL", "未设置"),
    "MINIMAX_API_KEY": os.getenv("MINIMAX_API_KEY", "未设置")[:20] + "..." if os.getenv("MINIMAX_API_KEY") else "未设置",
    "MINIMAX_GROUP_ID": os.getenv("MINIMAX_GROUP_ID", "未设置"),
    "MINIMAX_LLM_BASE_URL": os.getenv("MINIMAX_LLM_BASE_URL", "未设置"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "未设置")[:20] + "..." if os.getenv("OPENAI_API_KEY") else "未设置",
}

for key, value in env_vars.items():
    print(f"  {key}: {value}")

print("\n【2/5】导入核心模块...")
print("-" * 60)

try:
    from src.agents.llm_service import (
        LLMProvider,
        LLMConfig,
        LLMServiceFactory,
        get_default_llm_config,
        get_llm_service,
        MiniMaxAnthropicService,
    )
    print("  ✅ LLM 服务模块导入成功")
except Exception as e:
    print(f"  ❌ LLM 服务模块导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from src.agents.video_editor_agent import (
        get_smart_agent,
        SmartVideoEditorAgent,
        ChatResponse,
    )
    print("  ✅ 视频编辑 Agent 模块导入成功")
except Exception as e:
    print(f"  ❌ 视频编辑 Agent 模块导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n【3/5】检查 LLM 配置...")
print("-" * 60)

try:
    config = get_default_llm_config()
    print(f"  Provider: {config.provider.value}")
    print(f"  Model: {config.model_name}")
    print(f"  Temperature: {config.temperature}")
    print(f"  Max Tokens: {config.max_tokens}")
    print(f"  API Key 已设置: {bool(config.api_key)}")
    print(f"  Group ID: {config.group_id}")
except Exception as e:
    print(f"  ❌ 获取默认配置失败: {e}")
    import traceback
    traceback.print_exc()

print("\n【4/5】测试初始化 Smart Agent...")
print("-" * 60)

try:
    agent = get_smart_agent()
    print(f"  ✅ Smart Agent 初始化成功")
    print(f"  Agent 类型: {type(agent).__name__}")
except Exception as e:
    print(f"  ❌ Smart Agent 初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n【5/5】测试创建对话...")
print("-" * 60)

try:
    conv_id = agent.create_conversation("测试对话")
    print(f"  ✅ 对话创建成功")
    print(f"  对话 ID: {conv_id}")
except Exception as e:
    print(f"  ❌ 对话创建失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("诊断测试完成")
print("=" * 60)

print("\n【可选测试】测试发送简单消息（需要有效 API Key）...")
print("-" * 60)

api_key = os.getenv("MINIMAX_API_KEY")
if api_key and api_key != "your_minimax_api_key":
    print("  检测到已配置 API Key，尝试发送测试消息...")
    
    async def test_chat():
        try:
            print("\n  发送消息: '你好，请简单介绍一下你自己'")
            print("  等待响应...\n")
            
            response = await agent.chat(
                user_input="你好，请简单介绍一下你自己。",
                conversation_id=conv_id,
                auto_execute_tools=True,
            )
            
            print("  " + "=" * 50)
            print("  响应结果:")
            print("  " + "=" * 50)
            print(f"  内容: {response.content}")
            print(f"  对话 ID: {response.conversation_id}")
            print(f"  工具调用: {response.tool_calls}")
            print(f"  工具结果: {response.tool_results}")
            print("  " + "=" * 50)
            print("\n  ✅ 聊天测试成功！")
            
        except Exception as e:
            print(f"  ❌ 聊天测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(test_chat())
else:
    print("  ⚠️  MINIMAX_API_KEY 未配置或为默认值，跳过实时 API 测试")
    print("\n  提示：请在 .env 文件中配置有效的 MINIMAX_API_KEY 和 MINIMAX_GROUP_ID")
    print("  然后再次运行此脚本进行完整测试。")

print("\n" + "=" * 60)
print("测试总结")
print("=" * 60)

print("""
如果核心模块初始化成功，但实时聊天失败，可能的原因：

1. API Key 无效或过期
2. Group ID 不正确
3. 网络连接问题（需要访问 MiniMax API）
4. 账户余额不足

如果 UI 中消息发送不出去，请检查：
1. 浏览器开发者工具中的 Network 标签，查看 /api/chat 请求的响应
2. 服务器控制台的错误日志
3. 确保 .env 文件中的配置正确
""")
