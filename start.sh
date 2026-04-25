#!/bin/bash

# 视频剪辑 Agent - 一键启动脚本
# 同时启动前端和后端服务

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONT_DIR="$SCRIPT_DIR/front"
VENV_DIR="$SCRIPT_DIR/venv"
VENV_PATH="$VENV_DIR/bin/activate"
PYTHON_EXEC="$VENV_DIR/bin/python"
PIP_EXEC="$VENV_DIR/bin/pip"

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  🎬 视频剪辑 Agent 启动中...${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 Node.js 和 npm
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js 未安装，请先安装 Node.js${NC}"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ npm 未安装，请先安装 npm${NC}"
    exit 1
fi

# 检查虚拟环境
echo -e "${YELLOW}🔧 检查 Python 虚拟环境...${NC}"
if [ ! -f "$PYTHON_EXEC" ]; then
    echo -e "${RED}❌ 未找到虚拟环境: $VENV_DIR${NC}"
    echo -e "${YELLOW}   请先创建虚拟环境: python3 -m venv venv${NC}"
    exit 1
fi
echo -e "${GREEN}   ✅ 虚拟环境已就绪${NC}"
echo -e "   Python 路径: $PYTHON_EXEC"
echo -e "   Python 版本: $("$PYTHON_EXEC" --version 2>&1)"

# 检查前端依赖
echo -e "${YELLOW}📦 检查前端依赖...${NC}"
if [ ! -d "$FRONT_DIR/node_modules" ]; then
    echo -e "${YELLOW}   安装前端依赖中...${NC}"
    cd "$FRONT_DIR"
    npm install
    cd "$SCRIPT_DIR"
    echo -e "${GREEN}   ✅ 前端依赖安装完成${NC}"
else
    echo -e "${GREEN}   ✅ 前端依赖已存在${NC}"
fi

# 检查后端依赖
echo -e "${YELLOW}📦 检查后端依赖...${NC}"
if "$PYTHON_EXEC" -c "import uvicorn, fastapi, anthropic" 2>/dev/null; then
    echo -e "${GREEN}   ✅ 后端依赖已存在${NC}"
else
    echo -e "${YELLOW}   正在安装 Python 依赖...${NC}"
    "$PIP_EXEC" install -r "$SCRIPT_DIR/requirements.txt"
    echo -e "${GREEN}   ✅ Python 依赖安装完成${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  🚀 启动服务...${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 定义清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 正在停止服务...${NC}"
    if [ -n "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
        wait $BACKEND_PID 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
        wait $FRONTEND_PID 2>/dev/null || true
    fi
    echo -e "${GREEN}✅ 所有服务已停止${NC}"
    exit 0
}

# 捕获退出信号
trap cleanup SIGINT SIGTERM

# 启动后端服务（使用虚拟环境 Python 的绝对路径）
echo -e "${BLUE}🔧 启动后端服务 (端口 8000)...${NC}"
echo -e "   使用 Python: $PYTHON_EXEC"
"$PYTHON_EXEC" -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000 2>&1 &
BACKEND_PID=$!
echo -e "${GREEN}   ✅ 后端服务已启动 (PID: $BACKEND_PID)${NC}"

# 等待后端启动
echo -e "${YELLOW}   等待后端服务就绪...${NC}"
sleep 3

# 检查后端是否启动成功
if "$PYTHON_EXEC" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/status', timeout=5)" 2>/dev/null; then
    echo -e "${GREEN}   ✅ 后端服务健康检查通过${NC}"
else
    echo -e "${YELLOW}   ⚠️  后端服务启动中，继续等待...${NC}"
    sleep 2
fi

# 启动前端服务
echo -e "${BLUE}🌐 启动前端服务 (端口 3000)...${NC}"
cd "$FRONT_DIR"
npm run dev 2>&1 &
FRONTEND_PID=$!
cd "$SCRIPT_DIR"
echo -e "${GREEN}   ✅ 前端服务已启动 (PID: $FRONTEND_PID)${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✨ 所有服务已启动完成!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}📌 访问地址:${NC}"
echo -e "   前端: ${GREEN}http://localhost:3000${NC}"
echo -e "   后端 API: ${GREEN}http://localhost:8000${NC}"
echo -e "   API 文档: ${GREEN}http://localhost:8000/docs${NC}"
echo ""
echo -e "${BLUE}📊 进程信息:${NC}"
echo -e "   后端 PID: $BACKEND_PID"
echo -e "   前端 PID: $FRONTEND_PID"
echo ""
echo -e "${YELLOW}💡 按 Ctrl+C 停止所有服务${NC}"
echo ""

# 等待所有子进程
wait
