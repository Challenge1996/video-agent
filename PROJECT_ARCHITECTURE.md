# Video-Agent 项目架构文档

## 1. 项目概述

Video-Agent 是一个基于 Python 的视频编辑智能 Agent 系统，支持视频分割、TTS 语音合成、字幕生成、背景音乐添加和贴纸功能。该系统使用 LangChain 和 LangGraph 构建智能 Agent，能够通过自然语言交互完成复杂的视频编辑任务。

## 2. 项目目录结构

```
video-agent/
├── src/                          # 主源代码目录（原 src_py）
│   ├── agents/                   # Agent 实现
│   │   ├── __init__.py
│   │   └── video_editor_agent.py # 视频编辑 Agent 核心实现
│   ├── config/                   # 配置模块
│   │   ├── __init__.py
│   │   └── config.py             # 全局配置类
│   ├── modules/                  # 功能模块
│   │   ├── __init__.py
│   │   ├── video_splitter.py     # 视频分割模块
│   │   ├── video_composer.py     # 视频合成模块
│   │   ├── tts_service.py        # Google TTS 服务
│   │   ├── minimax_tts_service.py # MiniMax TTS 服务
│   │   ├── subtitle_generator.py # 字幕生成模块
│   │   ├── background_music.py   # 背景音乐处理模块
│   │   └── sticker_service.py    # 贴纸处理模块
│   ├── utils/                    # 工具函数
│   │   ├── __init__.py
│   │   └── helpers.py            # 通用工具函数
│   ├── tests/                    # 测试文件
│   │   ├── __init__.py
│   │   └── test_real_scenarios.py # 实际场景测试
│   ├── __init__.py
│   ├── index.py                  # 命令行入口
│   ├── lib.py                    # 库文件（导出所有模块）
│   └── requirements.txt          # Python 依赖
├── ts_temp/                      # 原 JavaScript 代码（已迁移）
│   ├── src/                      # JavaScript 源代码
│   ├── tests/                    # JavaScript 测试
│   ├── package.json              # Node.js 配置
│   └── examples.js               # 示例代码
├── credentials/                  # 凭证文件目录
│   └── README.md
├── .env.example                  # 环境变量示例
├── .gitignore                    # Git 忽略文件
└── README.md                     # 项目说明文档
```

## 3. 核心模块说明

### 3.1 配置模块 (config/config.py)

**功能**：管理全局配置，支持从环境变量加载配置。

**核心类**：
- `Config`：单例配置类，包含以下配置项：
  - `tts`：TTS 提供商配置
  - `google`：Google 服务配置
  - `minimax`：MiniMax 服务配置
  - `ffmpeg`：FFmpeg 路径配置
  - `directories`：输出目录和临时目录配置
  - `video`：视频默认参数配置
  - `audio`：音频默认参数配置
  - `subtitle`：字幕默认参数配置
  - `sticker`：贴纸默认参数配置

**关键方法**：
- `ensure_directories()`：确保输出目录和临时目录存在
- `output_dir`：获取输出目录路径
- `temp_dir`：获取临时目录路径

### 3.2 工具函数模块 (utils/helpers.py)

**功能**：提供通用的工具函数，被其他模块广泛使用。

**核心函数**：
- `ensure_directory(dir_path)`：确保目录存在
- `generate_unique_id()`：生成唯一 ID
- `format_timestamp(seconds)`：将秒数格式化为 SRT 时间戳格式
- `parse_timestamp(timestamp)`：解析 SRT 时间戳为秒数
- `get_file_extension(filename)`：获取文件扩展名
- `get_file_name_without_extension(filename)`：获取不带扩展名的文件名
- `sanitize_filename(filename)`：清理文件名中的非法字符
- `calculate_video_segments(total_duration, segment_duration)`：计算视频分割片段
- `format_duration(seconds)`：格式化时长为可读字符串
- `split_text_for_tts(text, max_chars_per_segment, split_by_sentence)`：为 TTS 分割文本

### 3.3 视频分割模块 (modules/video_splitter.py)

**功能**：负责视频信息获取、视频分割和视频合并。

**核心类**：
- `VideoInfo`：视频信息数据类
  - `duration`：视频时长（秒）
  - `size`：文件大小（字节）
  - `bitrate`：码率
  - `video`：视频流信息字典
  - `audio`：音频流信息字典（可选）

- `VideoSegment`：视频片段数据类
  - `index`：片段索引
  - `start_time`：开始时间
  - `end_time`：结束时间
  - `duration`：时长
  - `path`：文件路径
  - `filename`：文件名

- `VideoSplitter`：视频分割器类

**关键方法**：
- `get_video_info(video_path)`：获取视频详细信息
- `split_video(video_path, options)`：按固定时长分割视频
- `split_by_custom_intervals(video_path, intervals, output_dir)`：按自定义时间区间分割视频
- `merge_videos(video_paths, output_path, options)`：合并多个视频文件
- `get_audio_volume(video_path)`：检测视频音频音量

### 3.4 视频合成模块 (modules/video_composer.py)

**功能**：综合视频编辑功能，一键完成视频合成，包括 TTS 语音、字幕、背景音乐和贴纸的添加。

**核心类**：
- `ComposeResult`：合成结果数据类
  - `success`：是否成功
  - `output_path`：输出文件路径
  - `filename`：输出文件名
  - `original_video`：原始视频路径
  - `video_info`：视频信息字典
  - `tts_added`：是否添加了 TTS
  - `subtitles_added`：是否添加了字幕
  - `background_music_added`：是否添加了背景音乐
  - `stickers_added`：是否添加了贴纸

- `VideoComposer`：视频合成器类

**关键方法**：
- `compose_video(options)`：一键合成视频，支持以下选项：
  - `video_path`：输入视频路径
  - `text_content`：TTS 文本内容
  - `background_music_path`：背景音乐路径
  - `stickers`：贴纸列表
  - `add_tts`：是否添加 TTS
  - `add_subtitles`：是否添加字幕
  - `add_background_music`：是否添加背景音乐
  - `add_stickers`：是否添加贴纸
  - `output_file_name`：输出文件名

- `split_and_compose(options)`：先分割视频再合成
- `compose_from_segments(options)`：从多个片段合成

**音频优先级处理**：
- 自动检测视频原声音量
- 根据是否有 TTS 语音自动调整各音频轨道音量
- 支持闪避效果（ducking）

### 3.5 TTS 服务模块

**3.5.1 Google TTS 服务 (modules/tts_service.py)**

**功能**：使用 Google Cloud Text-to-Speech API 进行语音合成。

**核心类**：
- `TTSService`：Google TTS 服务类

**关键方法**：
- `synthesize_speech(text, options)`：合成单个文本
- `list_voices(language_code)`：列出可用语音

**3.5.2 MiniMax TTS 服务 (modules/minimax_tts_service.py)**

**功能**：使用 MiniMax API 进行语音合成，支持批量合成。

**核心类**：
- `MiniMaxTTSService`：MiniMax TTS 服务类

**关键方法**：
- `synthesize_speech(text, options)`：合成单个文本
- `synthesize_batch(texts, options)`：批量合成多个文本

### 3.6 字幕生成模块 (modules/subtitle_generator.py)

**功能**：生成和处理 SRT 格式字幕。

**核心类**：
- `SubtitleSegment`：字幕片段数据类
- `SubtitleData`：字幕数据类
- `SubtitleGenerator`：字幕生成器类

**关键方法**：
- `generate_srt_from_text(text, options)`：从文本生成字幕
- `generate_srt_from_tts_results(tts_results, options)`：从 TTS 结果生成字幕（时间轴更精确）
- `parse_srt_file(srt_path)`：解析 SRT 文件
- `save_srt(subtitle_data, output_path)`：保存字幕到文件

### 3.7 背景音乐模块 (modules/background_music.py)

**功能**：处理背景音乐，包括循环播放、淡入淡出、闪避效果等。

**核心类**：
- `AudioInfo`：音频信息数据类
- `BackgroundMusicResult`：背景音乐处理结果数据类
- `BackgroundMusicService`：背景音乐服务类

**关键方法**：
- `get_audio_info(audio_path)`：获取音频信息
- `loop_audio_to_duration(audio_path, target_duration, options)`：循环音频到目标时长
- `add_fade_effects(audio_path, options)`：添加淡入淡出效果
- `apply_ducking(audio_path, voice_segments, options)`：应用闪避效果（在语音时段降低音量）

### 3.8 贴纸模块 (modules/sticker_service.py)

**功能**：为视频添加静态或动态贴纸。

**核心类**：
- `StickerResult`：贴纸处理结果数据类
- `StickerService`：贴纸服务类

**关键方法**：
- `add_single_sticker(video_path, sticker, options)`：添加单个贴纸
- `add_multiple_stickers(video_path, stickers, options)`：添加多个贴纸

**支持的贴纸位置**：
- top-left, top, top-right
- middle-left, middle, middle-right
- bottom-left, bottom, bottom-right

## 4. Agent 架构与调用流程

### 4.1 Agent 状态定义 (AgentState)

Agent 使用 TypedDict 定义状态，用于在工作流节点之间传递数据：

```python
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]  # 消息列表（累加）
    video_path: Optional[str]                              # 当前视频路径
    text_content: Optional[str]                            # 文本内容
    background_music_path: Optional[str]                   # 背景音乐路径
    stickers: Optional[List[Dict[str, Any]]]              # 贴纸列表
    actions: Annotated[List[str], operator.add]           # 已执行的操作列表（累加）
    current_step: Optional[str]                            # 当前步骤
    results: Dict[str, Any]                                # 执行结果
    errors: Annotated[List[str], operator.add]            # 错误列表（累加）
```

### 4.2 工作流构建

Agent 使用 LangGraph 的 `StateGraph` 构建工作流：

1. **节点定义**：
   - `model`：调用 LLM 模型，分析用户需求并决定使用哪些工具
   - `tools`：执行工具函数的节点

2. **边定义**：
   - `START` → `model`：从开始节点到模型节点
   - `model` → `should_continue`：条件边，根据模型输出决定下一步
   - `tools` → `model`：工具执行完成后回到模型节点

3. **条件判断 (should_continue)**：
   - 如果模型输出包含 `tool_calls`，则转到 `tools` 节点执行工具
   - 否则，转到 `END` 结束工作流

### 4.3 完整调用流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户输入                                    │
│  例如："帮我把这个视频加上语音解说和背景音乐"                         │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      1. 初始化 Agent                              │
│  - 创建 VideoEditorAgent 实例                                     │
│  - 初始化工作流 (StateGraph)                                      │
│  - 注册所有可用工具                                                │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      2. 构建初始状态                              │
│  AgentState = {                                                   │
│      'messages': [HumanMessage(content=用户输入)],                │
│      'video_path': None,                                          │
│      'text_content': None,                                        │
│      'background_music_path': None,                               │
│      'stickers': None,                                             │
│      'actions': [],                                                │
│      'current_step': None,                                         │
│      'results': {},                                                │
│      'errors': []                                                  │
│  }                                                                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      3. 进入工作流 (START → model)               │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      4. model 节点执行                            │
│                                                                   │
│  4.1 系统提示词注入：                                               │
│      "你是一个专业的视频编辑Agent。你可以使用以下工具..."           │
│                                                                   │
│  4.2 LLM 分析用户需求：                                             │
│      - 理解用户意图："添加语音解说和背景音乐"                        │
│      - 识别需要的工具：generate_tts_tool, add_background_music_tool │
│      - 或建议使用 compose_video_tool 一键完成                      │
│                                                                   │
│  4.3 生成工具调用决策：                                             │
│      - 方式A：调用 compose_video_tool（推荐，一键完成）             │
│      - 方式B：依次调用 generate_tts_tool → generate_subtitles_tool │
│                → add_background_music_tool                         │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      5. 条件判断 (should_continue)               │
│                                                                   │
│  检查模型输出是否包含 tool_calls：                                  │
│  ┌─────────────┐         ┌─────────────┐                          │
│  │ 有 tool_calls │────────▶│  转到 tools  │                          │
│  └─────────────┘         └─────────────┘                          │
│         │                        │                                 │
│         │ 没有 tool_calls        │ 执行完成                        │
│         ▼                        ▼                                 │
│  ┌─────────────┐         ┌─────────────┐                          │
│  │  转到 END   │         │ 返回结果    │                          │
│  └─────────────┘         └─────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼ (假设有 tool_calls)
┌─────────────────────────────────────────────────────────────────┐
│                      6. tools 节点执行                            │
│                                                                   │
│  执行工具函数（使用 LangGraph 的 ToolNode）：                       │
│                                                                   │
│  示例：调用 compose_video_tool                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. 提取参数：                                               │   │
│  │    - video_path: 用户提供的视频路径                          │   │
│  │    - text_content: 用户提供的解说文本                        │   │
│  │    - background_music_path: 用户提供的音乐路径               │   │
│  │    - add_tts: True                                         │   │
│  │    - add_subtitles: True                                   │   │
│  │    - add_background_music: True                            │   │
│  │                                                            │   │
│  │ 2. 执行 VideoComposer.compose_video()                     │   │
│  │                                                            │   │
│  │ 3. 内部执行流程：                                           │   │
│  │    a. 检测视频原声音量                                       │   │
│  │    b. 生成 TTS 语音（调用 MiniMaxTTSService）               │   │
│  │    c. 生成字幕（调用 SubtitleGenerator）                    │   │
│  │    d. 处理背景音乐（循环、淡入淡出、闪避）                    │   │
│  │    e. 合并音轨到视频                                         │   │
│  │    f. 添加字幕到视频                                         │   │
│  │    g. 清理临时文件                                           │   │
│  │                                                            │   │
│  │ 4. 返回结果：                                               │   │
│  │    {                                                        │   │
│  │      'success': True,                                       │   │
│  │      'output_path': '/path/to/output.mp4',                 │   │
│  │      'effects_applied': {                                   │   │
│  │          'tts': True,                                       │   │
│  │          'subtitles': True,                                 │   │
│  │          'background_music': True                           │   │
│  │      }                                                       │   │
│  │    }                                                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      7. tools → model 循环                       │
│                                                                   │
│  工具执行完成后，结果被添加到 messages 中，然后回到 model 节点：      │
│                                                                   │
│  - LLM 查看工具执行结果                                             │
│  - 决定是否需要继续调用其他工具                                      │
│  - 或总结结果给用户                                                 │
│                                                                   │
│  可能的循环：                                                       │
│  model → tools → model → tools → ... → model → END              │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      8. 工作流结束 (END)                         │
│                                                                   │
│  返回最终状态：                                                    │
│  {                                                                 │
│      'messages': [                                                │
│          HumanMessage(用户输入),                                   │
│          AIMessage(工具调用决策),                                  │
│          ToolMessage(工具执行结果),                                │
│          AIMessage(最终总结)                                       │
│      ],                                                           │
│      'results': {                                                  │
│          'compose_video': {                                        │
│              'success': True,                                      │
│              'output_path': '/path/to/output.mp4'                 │
│          }                                                         │
│      },                                                           │
│      'actions': ['compose_video'],                                │
│      'errors': []                                                  │
│  }                                                                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      9. 返回结果给用户                            │
│                                                                   │
│  提取最后一条消息的内容，返回给用户：                                │
│  "视频合成完成！输出文件: /path/to/output.mp4                     │
│   应用的效果:                                                       │
│   - TTS语音: 已添加                                                │
│   - 字幕: 已添加                                                   │
│   - 背景音乐: 已添加"                                               │
└─────────────────────────────────────────────────────────────────┘
```

## 5. Tool 实现详解

Agent 共实现了 9 个工具函数，使用 `@tool` 装饰器注册到 LangChain 工具系统。

### 5.1 工具列表

| 工具名称 | 功能描述 | 主要参数 |
|---------|---------|---------|
| `split_video_tool` | 分割视频 | `video_path`, `segment_duration` |
| `get_video_info_tool` | 获取视频信息 | `video_path` |
| `generate_tts_tool` | 生成 TTS 语音 | `text`, `output_path`, `voice_id`, `speed` |
| `generate_subtitles_tool` | 生成字幕 | `text`, `output_path`, `total_duration` |
| `add_background_music_tool` | 添加背景音乐 | `video_path`, `music_path`, `volume`, `output_path` |
| `add_sticker_tool` | 添加贴纸 | `video_path`, `sticker_path`, `position`, `scale`, `opacity` |
| `compose_video_tool` | 一键合成视频 | `video_path`, `text_content`, `background_music_path`, `stickers`, 各种开关 |
| `merge_videos_tool` | 合并视频 | `video_paths`, `output_path` |
| `get_audio_info_tool` | 获取音频信息 | `audio_path` |

### 5.2 核心工具实现详解

#### 5.2.1 split_video_tool

**功能**：将视频分割成多个片段。

**实现位置**：`src/agents/video_editor_agent.py:44-79`

**工作流程**：
1. 调用 `VideoSplitter.split_video()` 方法
2. 内部使用 FFmpeg 执行 `-ss`（开始时间）和 `-t`（时长）参数进行快速分割
3. 使用 `-c:v copy` 和 `-c:a copy` 进行无损分割（不重新编码）
4. 返回分割结果，包括每个片段的路径、时长等信息

**关键代码**：
```python
@tool
def split_video_tool(video_path: str, segment_duration: int = 30) -> Dict[str, Any]:
    try:
        result = video_splitter_instance.split_video(
            video_path,
            {'segment_duration': segment_duration}
        )
        segments_info = [
            {
                'index': s.index,
                'start_time': s.start_time,
                'end_time': s.end_time,
                'duration': s.duration,
                'path': s.path,
                'filename': s.filename
            }
            for s in result['segments']
        ]
        return {
            'success': True,
            'original_video': result['original_video'],
            'segment_count': result['segment_count'],
            'segments': segments_info,
            'original_duration': result['original_info'].duration
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
```

#### 5.2.2 get_video_info_tool

**功能**：获取视频文件的详细信息。

**实现位置**：`src/agents/video_editor_agent.py:83-109`

**工作流程**：
1. 调用 `VideoSplitter.get_video_info()` 方法
2. 内部使用 FFprobe 执行 `-show_format` 和 `-show_streams` 参数
3. 解析 JSON 输出，提取视频和音频流信息
4. 返回格式化的信息字典

**返回字段**：
- `duration`：视频时长（秒）
- `size_mb`：文件大小（MB）
- `bitrate_kbps`：码率（kbps）
- `video_codec`：视频编码
- `resolution`：分辨率（如 "1920x1080"）
- `fps`：帧率
- `has_audio`：是否有音频
- `audio_codec`：音频编码
- `audio_sample_rate`：音频采样率
- `audio_channels`：音频声道数

#### 5.2.3 generate_tts_tool

**功能**：使用 TTS 生成语音文件。

**实现位置**：`src/agents/video_editor_agent.py:113-144`

**工作流程**：
1. 创建 `MiniMaxTTSService` 实例
2. 调用 `synthesize_speech()` 方法
3. 内部使用 HTTP 请求调用 MiniMax TTS API
4. 保存音频文件到临时目录
5. 返回音频文件路径和时长

**支持的参数**：
- `voice_id`：语音 ID（默认使用配置中的语音）
- `speed`：语速（1.0 为正常速度）

#### 5.2.4 generate_subtitles_tool

**功能**：从文本生成 SRT 格式字幕。

**实现位置**：`src/agents/video_editor_agent.py:148-194`

**工作流程**：
1. 创建 `SubtitleGenerator` 实例
2. 调用 `generate_srt_from_text()` 方法
3. 内部逻辑：
   - 使用 `split_text_for_tts()` 按句子分割文本
   - 为每个句子计算时间轴（基于字符数估算时长）
   - 格式化为 SRT 格式
4. 可选：保存到指定的输出路径

**SRT 格式示例**：
```
1
00:00:00,000 --> 00:00:03,500
这是第一句字幕

2
00:00:03,500 --> 00:00:07,200
这是第二句字幕
```

#### 5.2.5 add_background_music_tool

**功能**：为视频添加背景音乐。

**实现位置**：`src/agents/video_editor_agent.py:198-255`

**工作流程**：
1. 获取视频时长
2. 调用 `BackgroundMusicService.loop_audio_to_duration()` 循环音乐到视频时长
3. 应用淡入淡出效果
4. 使用 FFmpeg 合并视频和音频：
   - `-map 0:v:0`：选择第一个输入的视频流
   - `-map 0:a:0?`：选择第一个输入的音频流（如果存在）
   - `-map 1:a:0`：选择第二个输入的音频流（背景音乐）
   - `-shortest`：以最短的输入为准

#### 5.2.6 add_sticker_tool

**功能**：为视频添加静态或动态贴纸。

**实现位置**：`src/agents/video_editor_agent.py:259-317`

**支持的贴纸类型**：
- 静态贴纸：PNG、JPG 等图片格式
- 动态贴纸：GIF 格式

**支持的位置**：
```
top-left      top      top-right
    ┌─────────────────────────┐
    │                         │
middle-left  middle  middle-right
    │                         │
    └─────────────────────────┘
bottom-left   bottom   bottom-right
```

**实现方式**：
使用 FFmpeg 的 `-filter_complex` 参数：
- 对于静态贴纸：使用 `overlay` 滤镜
- 对于 GIF 贴纸：使用 `ignore_loop=0` + `overlay` 滤镜

#### 5.2.7 compose_video_tool（核心工具）

**功能**：综合视频编辑功能，一键完成视频合成。

**实现位置**：`src/agents/video_editor_agent.py:321-383`

**特点**：这是最强大、最常用的工具，可以一次性完成多项操作。

**支持的功能组合**：
1. **TTS 语音** + **字幕** + **背景音乐** + **贴纸**（完整组合）
2. **TTS 语音** + **字幕**（仅语音和字幕）
3. **背景音乐** + **贴纸**（仅音乐和贴纸）
4. 任意组合...

**内部执行流程**：
```
┌──────────────────────────────────────────────────────────────┐
│                    compose_video_tool 执行流程                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. 参数验证和初始化                                           │
│     ├── 检查 video_path 是否存在                              │
│     ├── 获取视频信息                                          │
│     └── 初始化各服务实例                                       │
│                                                              │
│  2. 音频优先级计算（可选）                                     │
│     ├── 检测视频原声音量                                       │
│     └── 根据是否有 TTS 调整各音轨音量                          │
│                                                              │
│  3. 生成 TTS 语音（如果 add_tts=True 且有 text_content）     │
│     ├── 分割文本为多个片段                                     │
│     ├── 调用 MiniMax API 合成语音                             │
│     └── 保存音频文件                                          │
│                                                              │
│  4. 生成字幕（如果 add_subtitles=True）                       │
│     ├── 从 TTS 结果或纯文本生成                                │
│     ├── 计算时间轴                                            │
│     └── 保存 SRT 文件                                         │
│                                                              │
│  5. 处理背景音乐（如果 add_background_music=True）            │
│     ├── 循环音乐到视频时长                                     │
│     ├── 应用淡入淡出效果                                       │
│     └── 可选：应用闪避效果                                     │
│                                                              │
│  6. 合并音轨到视频                                             │
│     ├── 使用 FFmpeg 的 -map 参数选择音轨                      │
│     ├── 设置各音轨音量                                         │
│     └── 应用 -shortest 参数                                   │
│                                                              │
│  7. 添加字幕（如果有字幕文件）                                 │
│     └── 使用 subtitles 滤镜烧录字幕                           │
│                                                              │
│  8. 添加贴纸（如果 add_stickers=True 且有 stickers）          │
│     └── 依次添加每个贴纸                                       │
│                                                              │
│  9. 清理临时文件（可选）                                       │
│     └── 删除临时目录中的中间文件                                │
│                                                              │
│  10. 返回结果                                                 │
│      ├── output_path: 最终输出路径                            │
│      ├── effects_applied: 应用的效果列表                      │
│      └── video_info: 视频信息                                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 5.2.8 merge_videos_tool

**功能**：合并多个视频文件。

**实现位置**：`src/agents/video_editor_agent.py:387-406`

**实现方式**：
使用 FFmpeg 的 `concat` 协议：
1. 创建一个文本文件，列出所有要合并的视频路径
2. 使用 `-f concat -safe 0 -i list.txt` 参数
3. 使用 `-c:v copy -c:a copy` 进行无损合并

**注意事项**：
- 所有视频必须有相同的编码、分辨率和帧率
- 否则需要重新编码（设置 `video_codec` 和 `audio_codec` 参数）

#### 5.2.9 get_audio_info_tool

**功能**：获取音频文件的详细信息。

**实现位置**：`src/agents/video_editor_agent.py:410-432`

**工作流程**：
1. 调用 `BackgroundMusicService.get_audio_info()` 方法
2. 内部使用 FFprobe 获取音频信息
3. 返回格式化的信息字典

## 6. 命令行使用方式

项目提供了命令行接口，可以直接通过命令行使用各种功能。

### 6.1 基本命令格式

```bash
python -m src.index <command> [options]
```

### 6.2 可用命令

#### 6.2.1 split - 分割视频

```bash
python -m src.index split -i input.mp4 -d 30
```

**参数**：
- `-i, --input`：输入视频文件路径（必需）
- `-o, --output`：输出目录
- `-d, --duration`：每个片段的时长（秒，默认 30）
- `-c, --custom`：自定义时间区间，格式：`start1-end1,start2-end2`

**示例**：
```bash
# 按 30 秒分割
python -m src.index split -i video.mp4 -d 30

# 按自定义时间区间分割
python -m src.index split -i video.mp4 -c 0-10,20-30,40-50
```

#### 6.2.2 tts - 文本转语音

```bash
python -m src.index tts -t "你好，这是一个测试"
```

**参数**：
- `-t, --text`：要转换的文本
- `-f, --file`：从文件读取文本
- `-o, --output`：输出音频文件路径
- `--provider`：TTS 提供商（minimax 或 google，默认 minimax）
- `--voice-id`：语音 ID
- `-r, --rate`：语速（默认 1.0）

**示例**：
```bash
# 从文本生成
python -m src.index tts -t "欢迎使用视频编辑 Agent" -o output.mp3

# 从文件生成
python -m src.index tts -f script.txt --voice-id "female-qn-qingse"
```

#### 6.2.3 subtitle - 生成字幕

```bash
python -m src.index subtitle -t "这是字幕内容" -o output.srt
```

**参数**：
- `-t, --text`：文本内容
- `-f, --file`：从文件读取文本
- `-s, --srt`：输入 SRT 文件（用于解析或合并）
- `-o, --output`：输出 SRT 文件路径
- `-d, --duration`：总时长（用于计算时间轴）

**示例**：
```bash
# 从文本生成字幕
python -m src.index subtitle -t "第一句话。第二句话。" -d 10 -o output.srt

# 解析现有 SRT 文件
python -m src.index subtitle -s existing.srt
```

#### 6.2.4 bgm - 处理背景音乐

```bash
python -m src.index bgm -i music.mp3 -d 60 -v 0.3
```

**参数**：
- `-i, --input`：输入音频文件路径（必需）
- `-o, --output`：输出音频文件路径
- `-d, --duration`：目标时长（秒）
- `-v, --volume`：音量（0.0-1.0，默认 0.3）
- `--fade-in`：淡入时长（秒，默认 1.0）
- `--fade-out`：淡出时长（秒，默认 1.0）

**示例**：
```bash
# 循环音乐到 60 秒，音量 0.3
python -m src.index bgm -i music.mp3 -d 60 -v 0.3 -o output.mp3

# 添加淡入淡出效果
python -m src.index bgm -i music.mp3 --fade-in 2 --fade-out 2 -o output.mp3
```

#### 6.2.5 compose - 合成视频（推荐）

```bash
python -m src.index compose -i input.mp4 -t "解说文本" -b music.mp3
```

**参数**：
- `-i, --input`：输入视频文件路径（必需）
- `-t, --text`：TTS 文本内容
- `--text-file`：从文件读取 TTS 文本
- `-b, --bgm`：背景音乐文件路径
- `-o, --output`：输出文件名（不含扩展名）
- `-s, --segment-duration`：视频分割时长（秒，默认 30）
- `--no-tts`：不添加 TTS
- `--no-subtitles`：不添加字幕
- `--no-bgm`：不添加背景音乐
- `--split`：先分割视频再合成

**示例**：
```bash
# 完整合成：TTS + 字幕 + 背景音乐
python -m src.index compose -i video.mp4 -t "这是解说文本" -b music.mp3 -o output

# 仅添加背景音乐
python -m src.index compose -i video.mp4 -b music.mp3 --no-tts --no-subtitles -o output

# 先分割再合成
python -m src.index compose -i video.mp4 -t "解说文本" --split -s 30 -o output
```

#### 6.2.6 info - 获取视频/音频信息

```bash
python -m src.index info -i input.mp4
```

**参数**：
- `-i, --input`：输入文件路径（必需）

**示例**：
```bash
# 获取视频信息
python -m src.index info -i video.mp4

# 获取音频信息
python -m src.index info -i music.mp3
```

## 7. 配置说明

### 7.1 环境变量配置

项目使用 `python-dotenv` 从 `.env` 文件加载配置。复制 `.env.example` 为 `.env` 并修改相应值：

```bash
cp .env.example .env
```

### 7.2 配置项说明

#### TTS 配置
```env
# TTS 提供商：minimax 或 google
TTS_PROVIDER=minimax

# MiniMax 配置（如果使用 MiniMax TTS）
MINIMAX_API_KEY=your_api_key
MINIMAX_GROUP_ID=your_group_id
MINIMAX_VOICE_ID=male-qn-qingse
MINIMAX_SPEED=1.0

# Google TTS 配置（如果使用 Google TTS）
GOOGLE_APPLICATION_CREDENTIALS=./credentials/google-cloud-key.json
GOOGLE_TTS_LANGUAGE_CODE=zh-CN
GOOGLE_TTS_VOICE_NAME=zh-CN-Wavenet-A
```

#### FFmpeg 配置
```env
# FFmpeg 路径（如果不在 PATH 中）
FFMPEG_PATH=ffmpeg
FFPROBE_PATH=ffprobe
```

#### 目录配置
```env
# 输出目录
OUTPUT_DIR=./output

# 临时目录
TEMP_DIR=./temp
```

### 7.3 配置优先级

配置按以下优先级加载：
1. 环境变量
2. `.env` 文件中的配置
3. 代码中的默认值

## 8. 依赖安装

### 8.1 Python 依赖

```bash
cd src
pip install -r requirements.txt
```

### 8.2 系统依赖

**FFmpeg**（必需）：
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows (使用 winget)
winget install ffmpeg
```

### 8.3 可选依赖

**Google Cloud Text-to-Speech**：
```bash
pip install google-cloud-text-to-speech
```

## 9. 测试

### 9.1 运行测试

```bash
cd src
pytest tests/ -v
```

### 9.2 测试场景

测试文件 `tests/test_real_scenarios.py` 包含以下测试场景：
1. 视频分割测试
2. 字幕生成测试
3. 背景音乐处理测试
4. 贴纸添加测试
5. TTS 合成测试（需要 API 密钥）

## 10. 扩展开发

### 10.1 添加新工具

1. 在 `src/modules/` 中创建新的功能模块
2. 在 `src/agents/video_editor_agent.py` 中：
   - 实例化新模块
   - 使用 `@tool` 装饰器创建工具函数
   - 将新工具添加到 `tools` 列表中

### 10.2 自定义 Agent 行为

修改 `src/agents/video_editor_agent.py` 中的：
- `system_prompt`：修改系统提示词
- `should_continue`：修改工作流条件判断
- `AgentState`：添加或修改状态字段

## 11. 故障排除

### 11.1 常见问题

**Q: FFmpeg 命令失败？**
A: 检查 FFmpeg 是否正确安装，以及输入文件路径是否正确。

**Q: TTS 合成失败？**
A: 检查 API 密钥是否正确配置，以及网络连接是否正常。

**Q: 字幕不显示？**
A: 检查字幕文件格式是否正确，以及字体是否支持中文。

**Q: 音频不同步？**
A: 检查视频和音频的帧率、采样率是否匹配。

### 11.2 调试模式

设置环境变量启用更详细的日志：
```bash
export LOG_LEVEL=DEBUG
```

## 12. 版本历史

- **v1.0.0**：初始版本
  - 支持视频分割、TTS 合成、字幕生成、背景音乐添加
  - 基于 LangChain/LangGraph 的 Agent 架构
  - 命令行接口

---

**文档版本**：v1.0  
**最后更新**：2026-04-24
