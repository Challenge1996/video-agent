# Video-Agent

一个基于 Python 的智能视频编辑 Agent 系统，支持视频分割、TTS 语音合成、字幕生成、背景音乐添加和贴纸功能。使用 LangChain 和 LangGraph 构建智能 Agent，能够通过自然语言交互完成复杂的视频编辑任务。

## ✨ 功能特性

- 🎬 **视频分割**：按固定时长或自定义时间区间分割视频
- 🎙️ **TTS 语音合成**：支持 MiniMax 和 Google 两种 TTS 提供商
- 📝 **字幕生成**：从文本自动生成 SRT 格式字幕，支持时间轴精确计算
- 🎵 **背景音乐处理**：循环播放、淡入淡出、闪避效果（语音时段自动降低音量）
- 🏷️ **贴纸添加**：支持静态图片和动态 GIF 贴纸
- 🤖 **智能 Agent**：基于 LangGraph 的工作流，支持自然语言交互
- 🚀 **一键合成**：使用 `compose` 命令一次完成所有视频编辑操作

## 📁 项目结构

```
video-agent/
├── src/                          # 主源代码目录
│   ├── agents/                   # Agent 实现
│   │   └── video_editor_agent.py # 视频编辑 Agent 核心
│   ├── config/                   # 配置模块
│   │   └── config.py             # 全局配置类
│   ├── modules/                  # 功能模块
│   │   ├── video_splitter.py     # 视频分割
│   │   ├── video_composer.py     # 视频合成
│   │   ├── tts_service.py        # Google TTS
│   │   ├── minimax_tts_service.py # MiniMax TTS
│   │   ├── subtitle_generator.py # 字幕生成
│   │   ├── background_music.py   # 背景音乐
│   │   └── sticker_service.py    # 贴纸处理
│   ├── utils/                    # 工具函数
│   │   └── helpers.py            # 通用工具
│   ├── tests/                    # 测试文件
│   ├── index.py                  # 命令行入口
│   ├── lib.py                    # 库文件导出
│   └── requirements.txt          # Python 依赖
├── ts_temp/                      # 原 JavaScript 代码（已迁移）
├── credentials/                  # 凭证文件目录
├── PROJECT_ARCHITECTURE.md       # 详细项目架构文档
├── .env.example                  # 环境变量示例
└── README.md
```

## 🚀 快速开始

### 1. 环境准备

#### 系统依赖

**FFmpeg**（必需）：
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows (winget)
winget install ffmpeg
```

#### Python 环境

```bash
# 推荐使用虚拟环境
python -m venv venv
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate     # Windows

# 安装依赖
cd src
pip install -r requirements.txt
```

### 2. 配置

复制环境变量示例文件并修改：
```bash
cp .env.example .env
```

编辑 `.env` 文件，填入必要的配置：

```env
# TTS 提供商：minimax 或 google
TTS_PROVIDER=minimax

# MiniMax 配置（如果使用 MiniMax TTS）
MINIMAX_API_KEY=your_api_key
MINIMAX_GROUP_ID=your_group_id
MINIMAX_VOICE_ID=male-qn-qingse

# Google TTS 配置（可选）
# GOOGLE_APPLICATION_CREDENTIALS=./credentials/google-cloud-key.json

# 输出目录
OUTPUT_DIR=./output
TEMP_DIR=./temp
```

### 3. 运行

#### 命令行方式

```bash
# 查看帮助
python -m src.index --help

# 查看具体命令帮助
python -m src.index compose --help
```

## 📖 使用示例

### 一键合成视频（推荐）

这是最常用的功能，一次完成 TTS、字幕、背景音乐的添加：

```bash
# 完整合成：TTS + 字幕 + 背景音乐
python -m src.index compose \
  -i input.mp4 \
  -t "欢迎使用视频编辑 Agent。这是一个智能的视频处理工具，可以帮助您快速完成视频剪辑任务。" \
  -b background_music.mp3 \
  -o my_video

# 仅添加背景音乐
python -m src.index compose \
  -i input.mp4 \
  -b music.mp3 \
  --no-tts \
  --no-subtitles \
  -o output

# 仅添加 TTS 和字幕
python -m src.index compose \
  -i input.mp4 \
  -t "这是解说文本" \
  --no-bgm \
  -o output
```

### 视频分割

```bash
# 按 30 秒分割
python -m src.index split -i video.mp4 -d 30 -o ./segments

# 按自定义时间区间分割
python -m src.index split -i video.mp4 -c 0-10,20-30,40-50
```

### TTS 语音合成

```bash
# 从文本生成
python -m src.index tts -t "欢迎使用视频编辑 Agent" -o speech.mp3

# 从文件生成
python -m src.index tts -f script.txt --voice-id "female-qn-qingse"
```

### 字幕生成

```bash
# 从文本生成字幕
python -m src.index subtitle -t "第一句话。第二句话。" -d 10 -o output.srt

# 解析现有 SRT 文件
python -m src.index subtitle -s existing.srt
```

### 背景音乐处理

```bash
# 循环音乐到 60 秒，音量 0.3
python -m src.index bgm -i music.mp3 -d 60 -v 0.3 -o output.mp3

# 添加淡入淡出效果
python -m src.index bgm -i music.mp3 --fade-in 2 --fade-out 2 -o output.mp3
```

### 获取媒体信息

```bash
# 获取视频信息
python -m src.index info -i video.mp4

# 获取音频信息
python -m src.index info -i music.mp3
```

## 🤖 使用 Agent

项目包含基于 LangGraph 的智能 Agent，可以通过自然语言进行交互：

```python
from src.agents.video_editor_agent import VideoEditorAgent

# 创建 Agent
agent = VideoEditorAgent()

# 直接调用工具
result = agent.compose_video(
    video_path="input.mp4",
    text_content="这是解说文本",
    background_music_path="music.mp3"
)
print(f"输出文件: {result['output_path']}")

# 获取视频信息
info = agent.get_video_info("input.mp4")
print(f"视频时长: {info['duration']} 秒")
print(f"分辨率: {info['resolution']}")
```

## 📚 详细文档

查看 [PROJECT_ARCHITECTURE.md](./PROJECT_ARCHITECTURE.md) 获取完整的项目架构说明，包括：

- 详细的模块设计
- Agent 工作流调用流程
- 所有 Tool 的实现详解
- 命令行完整参数说明
- 配置项详细说明
- 故障排除指南

## 🛠️ 开发

### 运行测试

```bash
cd src
pytest tests/ -v
```

### 扩展开发

#### 添加新工具

1. 在 `src/modules/` 中创建新的功能模块
2. 在 `src/agents/video_editor_agent.py` 中：
   - 实例化新模块
   - 使用 `@tool` 装饰器创建工具函数
   - 将新工具添加到 `tools` 列表中

#### 自定义 Agent 行为

修改 `src/agents/video_editor_agent.py` 中的：
- `system_prompt`：修改系统提示词
- `should_continue`：修改工作流条件判断
- `AgentState`：添加或修改状态字段

## 📋 命令参考

| 命令 | 描述 | 主要参数 |
|------|------|----------|
| `split` | 分割视频 | `-i` 输入, `-d` 时长, `-c` 自定义区间 |
| `tts` | 文本转语音 | `-t` 文本, `-f` 文件, `--provider` 提供商 |
| `subtitle` | 生成字幕 | `-t` 文本, `-s` SRT 文件, `-d` 时长 |
| `bgm` | 处理背景音乐 | `-i` 输入, `-d` 时长, `-v` 音量 |
| `compose` | 合成视频（推荐） | `-i` 输入, `-t` 文本, `-b` 音乐, `-o` 输出 |
| `info` | 获取媒体信息 | `-i` 输入文件 |

## 🔧 配置项

### TTS 配置

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `TTS_PROVIDER` | TTS 提供商 | `minimax` |
| `MINIMAX_API_KEY` | MiniMax API 密钥 | - |
| `MINIMAX_GROUP_ID` | MiniMax 组 ID | - |
| `MINIMAX_VOICE_ID` | 默认语音 ID | `male-qn-qingse` |
| `MINIMAX_SPEED` | 默认语速 | `1.0` |

### 目录配置

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `OUTPUT_DIR` | 输出目录 | `./output` |
| `TEMP_DIR` | 临时目录 | `./temp` |

### FFmpeg 配置

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `FFMPEG_PATH` | FFmpeg 路径 | `ffmpeg` |
| `FFPROBE_PATH` | FFprobe 路径 | `ffprobe` |

## ❓ 常见问题

### Q: FFmpeg 命令失败？
A: 检查 FFmpeg 是否正确安装，以及输入文件路径是否正确。

### Q: TTS 合成失败？
A: 检查 API 密钥是否正确配置，以及网络连接是否正常。

### Q: 字幕不显示？
A: 检查字幕文件格式是否正确，以及字体是否支持中文。

### Q: 音频不同步？
A: 检查视频和音频的帧率、采样率是否匹配。

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**版本**：v1.0.0  
**最后更新**：2026-04-24
