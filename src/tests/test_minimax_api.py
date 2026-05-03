#!/usr/bin/env python3
"""
测试脚本：验证 MiniMax LLM API 修复
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

print("=" * 60)
print("MiniMax LLM API 修复验证测试")
print("=" * 60)

print("\n【1/4】检查当前配置...")
print("-" * 60)

current_base_url = os.getenv("MINIMAX_LLM_BASE_URL", "未设置（使用默认值）")
print(f"  MINIMAX_LLM_BASE_URL: {current_base_url}")
print(f"  新的默认值: https://api.minimaxi.com/anthropic")

print("\n【2/4】重新导入模块并清除缓存...")
print("-" * 60)

import importlib

import src.agents.llm_service
importlib.reload(src.agents.llm_service)

from src.agents.llm_service import (
    LLMServiceFactory,
    get_default_llm_config,
    MiniMaxAnthropicService,
)

LLMServiceFactory.clear_cache()
print("  ✅ LLMServiceFactory 缓存已清除")

config = get_default_llm_config()
print(f"  ✅ 新配置加载成功")
print(f"  - Provider: {config.provider.value}")
print(f"  - Model: {config.model_name}")
print(f"  - Base URL: {config.base_url if config.base_url else '使用默认值'}")
print(f"  - API Key 已设置: {bool(config.api_key)}")

print("\n【3/4】初始化 LLM 服务...")
print("-" * 60)

try:
    service = LLMServiceFactory.create(config)
    print(f"  ✅ LLM 服务创建成功")
    print(f"  - 服务类型: {type(service).__name__}")
    
    client = service.get_model()
    print(f"  ✅ 客户端初始化成功")
    print(f"  - 客户端类型: {type(client).__name__}")
    
except Exception as e:
    print(f"  ❌ 初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n【4/4】测试 API 调用（如果有有效 API Key）...")
print("-" * 60)

api_key = os.getenv("MINIMAX_API_KEY")

if api_key and api_key != "your_minimax_api_key":
    print("  检测到已配置 API Key，尝试发送测试消息...")
    
    from langchain_core.messages import (
        HumanMessage,
        SystemMessage,
    )
    
    async def test_api_call():
        messages = [
            SystemMessage(content="你是一个友好的助手，请用中文回答问题。"),
            HumanMessage(content="你好，请简单介绍一下你自己，用一两句话即可。"),
        ]
        
        print(f"\n  发送消息: '{messages[-1].content}'")
        print("  等待响应...\n")
        
        try:
            response = await service.chat(messages)
            
            print("  " + "=" * 50)
            print("  API 响应成功!")
            print("  " + "=" * 50)
            
            if response.thinking:
                print(f"  Thinking: {response.thinking[:200]}...")
            
            print(f"\n  回复内容:")
            print(f"  {response.content}")
            print(f"\n  完成原因: {response.finish_reason}")
            print("  " + "=" * 50)
            
            print("\n  ✅ MiniMax API 调用成功！")
            return True
            
        except Exception as e:
            print(f"  ❌ API 调用失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    success = asyncio.run(test_api_call())
    
    if success:
        print("\n" + "=" * 60)
        print("🎉 测试总结：修复成功！")
        print("=" * 60)
        print("""
问题原因：
  - 之前的 MINIMAX_LLM_BASE_URL 默认值是 https://api.minimax.chat/v1
  - 但 MiniMax 的 Anthropic 兼容 API 应该使用 https://api.minimaxi.com/anthropic

修复内容：
  1. 修改了 llm_service.py 中的默认 base_url
  2. 更新了 .env.example 中的配置示例

现在你可以：
  1. 启动 Web 服务: python -m uvicorn src.web.app:app --reload
  2. 访问 http://localhost:8000/chat
  3. 在对话框中发送消息测试

""")
    else:
        print("\n" + "=" * 60)
        print("⚠️  测试总结：API 调用失败")
        print("=" * 60)
        print("""
可能的原因：
  1. API Key 无效或过期
  2. 网络连接问题
  3. 账户余额不足
  4. Base URL 仍然不正确

请检查你的配置：
  - MINIMAX_API_KEY
  - MINIMAX_LLM_BASE_URL (应该是 https://api.minimaxi.com/anthropic)
""")
else:
    print("  ⚠️  MINIMAX_API_KEY 未配置或为默认值，跳过实时 API 测试")
    print("\n" + "=" * 60)
    print("配置说明")
    print("=" * 60)
    print("""
请在 .env 文件中配置以下变量：

# MiniMax LLM 配置（用于 AI 对话）
MINIMAX_API_KEY=你的_api_key
MINIMAX_LLM_BASE_URL=https://api.minimaxi.com/anthropic
LLM_PROVIDER=minimax
LLM_MODEL=MiniMax-M2.7

# MiniMax TTS 配置（用于语音合成，可选）
MINIMAX_GROUP_ID=你的_group_id
MINIMAX_BASE_URL=https://api.minimax.chat/v1/t2a_v2

配置完成后，运行此脚本进行验证。
""")
