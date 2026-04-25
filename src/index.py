import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.config import config
from src.utils.helpers import helpers
from src.modules.video_splitter import VideoSplitter
from src.modules.tts_service import TTSService
from src.modules.minimax_tts_service import MiniMaxTTSService
from src.modules.subtitle_generator import SubtitleGenerator
from src.modules.background_music import BackgroundMusicService
from src.modules.sticker_service import StickerService
from src.modules.video_composer import VideoComposer


def main():
    parser = argparse.ArgumentParser(
        description='视频剪辑 Agent - 支持视频分割、TTS语音合成、字幕添加、背景音乐',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    split_parser = subparsers.add_parser('split', help='分割视频')
    split_parser.add_argument('-i', '--input', required=True, help='输入视频文件路径')
    split_parser.add_argument('-o', '--output', help='输出目录')
    split_parser.add_argument('-d', '--duration', type=int, default=30, help='每个片段的时长（秒）')
    split_parser.add_argument('-c', '--custom', help='自定义时间区间，格式：start1-end1,start2-end2')

    tts_parser = subparsers.add_parser('tts', help='文本转语音')
    tts_parser.add_argument('-t', '--text', help='要转换的文本')
    tts_parser.add_argument('-f', '--file', help='从文件读取文本')
    tts_parser.add_argument('-o', '--output', help='输出音频文件路径')
    tts_parser.add_argument('--provider', default='minimax', choices=['minimax', 'google'], help='TTS提供商')
    tts_parser.add_argument('--voice-id', help='语音ID')
    tts_parser.add_argument('-r', '--rate', type=float, default=1.0, help='语速')

    subtitle_parser = subparsers.add_parser('subtitle', help='生成字幕')
    subtitle_parser.add_argument('-t', '--text', help='文本内容')
    subtitle_parser.add_argument('-f', '--file', help='从文件读取文本')
    subtitle_parser.add_argument('-s', '--srt', help='输入 SRT 文件（用于解析或合并）')
    subtitle_parser.add_argument('-o', '--output', help='输出 SRT 文件路径')
    subtitle_parser.add_argument('-d', '--duration', type=float, help='总时长（用于计算时间轴）')

    bgm_parser = subparsers.add_parser('bgm', help='处理背景音乐')
    bgm_parser.add_argument('-i', '--input', required=True, help='输入音频文件路径')
    bgm_parser.add_argument('-o', '--output', help='输出音频文件路径')
    bgm_parser.add_argument('-d', '--duration', type=float, help='目标时长（秒）')
    bgm_parser.add_argument('-v', '--volume', type=float, default=0.3, help='音量（0.0-1.0）')
    bgm_parser.add_argument('--fade-in', type=float, default=1.0, help='淡入时长')
    bgm_parser.add_argument('--fade-out', type=float, default=1.0, help='淡出时长')

    compose_parser = subparsers.add_parser('compose', help='合成视频（整合所有功能）')
    compose_parser.add_argument('-i', '--input', required=True, help='输入视频文件路径')
    compose_parser.add_argument('-t', '--text', help='TTS 文本内容')
    compose_parser.add_argument('--text-file', help='从文件读取 TTS 文本')
    compose_parser.add_argument('-b', '--bgm', help='背景音乐文件路径')
    compose_parser.add_argument('-o', '--output', help='输出文件名（不含扩展名）')
    compose_parser.add_argument('-s', '--segment-duration', type=int, default=30, help='视频分割时长')
    compose_parser.add_argument('--no-tts', action='store_true', help='不添加 TTS')
    compose_parser.add_argument('--no-subtitles', action='store_true', help='不添加字幕')
    compose_parser.add_argument('--no-bgm', action='store_true', help='不添加背景音乐')
    compose_parser.add_argument('--split', action='store_true', help='先分割视频再合成')

    info_parser = subparsers.add_parser('info', help='获取视频/音频信息')
    info_parser.add_argument('-i', '--input', required=True, help='输入文件路径')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    if args.command == 'split':
        handle_split(args)
    elif args.command == 'tts':
        handle_tts(args)
    elif args.command == 'subtitle':
        handle_subtitle(args)
    elif args.command == 'bgm':
        handle_bgm(args)
    elif args.command == 'compose':
        handle_compose(args)
    elif args.command == 'info':
        handle_info(args)


def handle_split(args):
    try:
        splitter = VideoSplitter({
            'output_dir': args.output or config.temp_dir,
        })

        if args.custom:
            intervals = []
            for interval_str in args.custom.split(','):
                start, end = map(float, interval_str.split('-'))
                intervals.append({'start_time': start, 'end_time': end})
            result = splitter.split_by_custom_intervals(
                args.input,
                intervals,
                args.output
            )
        else:
            result = splitter.split_video(args.input, {
                'segment_duration': args.duration,
                'output_dir': args.output,
            })

        print('视频分割完成！')
        print(f'原始视频: {result["original_video"]}')
        print(f'视频时长: {helpers.format_duration(result["original_info"].duration)}')
        print(f'分割片段数: {result["segment_count"]}')
        print('\n生成的片段:')
        for index, segment in enumerate(result['segments']):
            print(f'  {index + 1}. {segment.filename} ({helpers.format_duration(segment.duration)})')
            print(f'     路径: {segment.path}')
    except Exception as error:
        print(f'视频分割失败: {error}')
        sys.exit(1)


def handle_tts(args):
    try:
        if args.provider == 'google':
            tts_service = TTSService({
                'speaking_rate': args.rate,
            })
        else:
            tts_service = MiniMaxTTSService({
                'voice_id': args.voice_id,
                'speed': args.rate,
            })

        text = args.text
        if args.file:
            with open(args.file, 'r', encoding='utf-8') as f:
                text = f.read()

        if not text:
            print('请提供 --text 或 --file 参数')
            sys.exit(1)

        options = {}
        if args.output:
            options['output_filename'] = os.path.basename(args.output)
            options['output_dir'] = os.path.dirname(args.output)
        if args.voice_id:
            options['voice_id'] = args.voice_id

        result = tts_service.synthesize_speech(text, options)

        print('TTS 合成完成！')
        print(f'文本: {text[:100]}...' if len(text) > 100 else f'文本: {text}')
        print(f'输出文件: {result.audio_path}')
        print(f'时长: {helpers.format_duration(result.duration)}')
    except Exception as error:
        print(f'TTS 合成失败: {error}')
        sys.exit(1)


def handle_subtitle(args):
    try:
        subtitle_generator = SubtitleGenerator()

        if args.srt:
            subtitle_data = subtitle_generator.parse_srt_file(args.srt)
            print('SRT 文件解析完成！')
            print(f'字幕数量: {subtitle_data.count}')
            print(f'总时长: {helpers.format_duration(subtitle_data.total_duration)}')

            if args.output:
                save_result = subtitle_generator.save_srt(subtitle_data, args.output)
                print(f'字幕已保存到: {save_result["path"]}')
            return

        text = args.text
        if args.file:
            with open(args.file, 'r', encoding='utf-8') as f:
                text = f.read()

        if not text:
            print('请提供 --text、--file 或 --srt 参数')
            sys.exit(1)

        options = {}
        if args.duration:
            options['total_duration'] = args.duration

        subtitle_data = subtitle_generator.generate_srt_from_text(text, options)

        print('字幕生成完成！')
        print(f'字幕数量: {subtitle_data.count}')

        if args.output:
            save_result = subtitle_generator.save_srt(subtitle_data, args.output)
            print(f'字幕已保存到: {save_result["path"]}')
        else:
            print('\n生成的 SRT 内容:')
            print(subtitle_data.srt_content)
    except Exception as error:
        print(f'字幕生成失败: {error}')
        sys.exit(1)


def handle_bgm(args):
    try:
        bgm_service = BackgroundMusicService({
            'default_volume': args.volume,
            'fade_duration': args.fade_in,
        })

        if args.duration:
            result = bgm_service.loop_audio_to_duration(
                args.input,
                args.duration,
                {
                    'output_dir': os.path.dirname(args.output) if args.output else None,
                    'output_filename': os.path.basename(args.output) if args.output else None,
                    'volume': args.volume,
                    'fade_in': args.fade_in,
                    'fade_out': args.fade_out,
                }
            )
            print('背景音乐循环处理完成！')
        else:
            result = bgm_service.add_fade_effects(args.input, {
                'output_dir': os.path.dirname(args.output) if args.output else None,
                'output_filename': os.path.basename(args.output) if args.output else None,
                'fade_in': args.fade_in,
                'fade_out': args.fade_out,
            })
            print('淡入淡出效果处理完成！')

        print(f'输出文件: {result.output_path}')
    except Exception as error:
        print(f'背景音乐处理失败: {error}')
        sys.exit(1)


def handle_compose(args):
    try:
        composer = VideoComposer()

        text_content = args.text
        if args.text_file:
            with open(args.text_file, 'r', encoding='utf-8') as f:
                text_content = f.read()

        if args.split:
            result = composer.split_and_compose({
                'video_path': args.input,
                'segment_duration': args.segment_duration,
                'text_content': text_content,
                'background_music_path': args.bgm,
                'output_file_name': args.output,
                'add_tts': not args.no_tts and bool(text_content),
                'add_subtitles': not args.no_subtitles,
                'add_background_music': not args.no_bgm and bool(args.bgm),
            })
        else:
            result = composer.compose_video({
                'video_path': args.input,
                'text_content': text_content,
                'background_music_path': args.bgm,
                'output_file_name': args.output,
                'add_tts': not args.no_tts and bool(text_content),
                'add_subtitles': not args.no_subtitles,
                'add_background_music': not args.no_bgm and bool(args.bgm),
            })

        print('视频合成完成！')
        print(f'输出文件: {result.output_path}')
        print(f'视频时长: {helpers.format_duration(result.video_info.get("duration", 0))}')
        print(f'分辨率: {result.video_info.get("video", {}).get("width")}x{result.video_info.get("video", {}).get("height")}')
        print('\n应用的效果:')
        print(f'  - TTS: {"已添加" if result.tts_added else "未添加"}')
        print(f'  - 字幕: {"已添加" if result.subtitles_added else "未添加"}')
        print(f'  - 背景音乐: {"已添加" if result.background_music_added else "未添加"}')
    except Exception as error:
        print(f'视频合成失败: {error}')
        sys.exit(1)


def handle_info(args):
    try:
        ext = os.path.splitext(args.input)[1].lower()

        if ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
            splitter = VideoSplitter()
            info = splitter.get_video_info(args.input)
            print('视频信息:')
            print('-' * 40)
            print(f'时长: {helpers.format_duration(info.duration)}')
            print(f'大小: {(info.size / 1024 / 1024):.2f} MB')
            print(f'码率: {(info.bitrate / 1000):.2f} kbps')
            print('\n视频流:')
            print(f'  编码: {info.video.get("codec")}')
            print(f'  分辨率: {info.video.get("width")}x{info.video.get("height")}')
            print(f'  帧率: {info.video.get("fps")} fps')
            if info.audio:
                print('\n音频流:')
                print(f'  编码: {info.audio.get("codec")}')
                print(f'  采样率: {info.audio.get("sample_rate")} Hz')
                print(f'  声道: {info.audio.get("channels")}')
        elif ext in ['.mp3', '.wav', '.ogg', '.flac', '.aac']:
            bgm_service = BackgroundMusicService()
            info = bgm_service.get_audio_info(args.input)
            print('音频信息:')
            print('-' * 40)
            print(f'时长: {helpers.format_duration(info.duration)}')
            print(f'大小: {(info.size / 1024 / 1024):.2f} MB')
            print(f'码率: {(info.bitrate / 1000):.2f} kbps')
            if info.audio:
                print('\n音频流:')
                print(f'  编码: {info.audio.get("codec")}')
                print(f'  采样率: {info.audio.get("sample_rate")} Hz')
                print(f'  声道: {info.audio.get("channels")}')
        else:
            print('不支持的文件格式')
            sys.exit(1)
    except Exception as error:
        print(f'获取文件信息失败: {error}')
        sys.exit(1)


if __name__ == '__main__':
    main()
