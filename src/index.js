#!/usr/bin/env node

import { program } from 'commander';
import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';
import VideoSplitter from './modules/videoSplitter.js';
import TTSService from './modules/ttsService.js';
import SubtitleGenerator from './modules/subtitleGenerator.js';
import BackgroundMusicService from './modules/backgroundMusic.js';
import VideoComposer from './modules/videoComposer.js';
import config from './config/index.js';
import helpers from './utils/helpers.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

program
  .name('video-agent')
  .description('视频剪辑 Agent - 支持视频分割、TTS语音合成、字幕添加、背景音乐')
  .version('1.0.0');

program
  .command('split')
  .description('分割视频')
  .requiredOption('-i, --input <path>', '输入视频文件路径')
  .option('-o, --output <dir>', '输出目录')
  .option('-d, --duration <seconds>', '每个片段的时长（秒）', '30')
  .option('-c, --custom <intervals>', '自定义时间区间，格式：start1-end1,start2-end2')
  .action(async (options) => {
    try {
      const splitter = new VideoSplitter({
        outputDir: options.output || config.directories.temp,
      });

      let result;
      if (options.custom) {
        const intervals = options.custom.split(',').map(interval => {
          const [start, end] = interval.split('-').map(Number);
          return { startTime: start, endTime: end };
        });
        result = await splitter.splitByCustomIntervals(
          options.input,
          intervals,
          options.output
        );
      } else {
        result = await splitter.splitVideo(options.input, {
          segmentDuration: parseInt(options.duration),
          outputDir: options.output,
        });
      }

      console.log('视频分割完成！');
      console.log(`原始视频: ${result.originalVideo}`);
      console.log(`视频时长: ${helpers.formatDuration(result.originalInfo.duration)}`);
      console.log(`分割片段数: ${result.segmentCount}`);
      console.log('\n生成的片段:');
      result.segments.forEach((segment, index) => {
        console.log(`  ${index + 1}. ${segment.filename} (${helpers.formatDuration(segment.duration)})`);
        console.log(`     路径: ${segment.path}`);
      });
    } catch (error) {
      console.error('视频分割失败:', error.message);
      process.exit(1);
    }
  });

program
  .command('tts')
  .description('文本转语音')
  .requiredOption('-t, --text <text>', '要转换的文本')
  .option('-f, --file <path>', '从文件读取文本')
  .option('-o, --output <path>', '输出音频文件路径')
  .option('-l, --language <code>', '语言代码', 'zh-CN')
  .option('-v, --voice <name>', '语音名称', 'zh-CN-Wavenet-A')
  .option('-r, --rate <rate>', '语速', '1.0')
  .option('-p, --pitch <pitch>', '音调', '0.0')
  .action(async (options) => {
    try {
      const ttsService = new TTSService({
        languageCode: options.language,
        voiceName: options.voice,
        speakingRate: parseFloat(options.rate),
        pitch: parseFloat(options.pitch),
      });

      let text = options.text;
      if (options.file) {
        text = fs.readFileSync(options.file, 'utf-8');
      }

      const result = await ttsService.synthesizeSpeech(text, {
        outputFileName: options.output ? path.basename(options.output) : undefined,
        outputDir: options.output ? path.dirname(options.output) : undefined,
      });

      console.log('TTS 合成完成！');
      console.log(`文本: ${text.substring(0, 100)}${text.length > 100 ? '...' : ''}`);
      console.log(`输出文件: ${result.audioPath}`);
      console.log(`时长: ${helpers.formatDuration(result.duration)}`);
    } catch (error) {
      console.error('TTS 合成失败:', error.message);
      process.exit(1);
    }
  });

program
  .command('subtitle')
  .description('生成字幕')
  .option('-t, --text <text>', '文本内容')
  .option('-f, --file <path>', '从文件读取文本')
  .option('-s, --srt <path>', '输入 SRT 文件（用于解析或合并）')
  .option('-o, --output <path>', '输出 SRT 文件路径')
  .option('-d, --duration <seconds>', '总时长（用于计算时间轴）')
  .option('--tts-results <path>', 'TTS 结果 JSON 文件路径')
  .action(async (options) => {
    try {
      const subtitleGenerator = new SubtitleGenerator();
      let subtitleData;

      if (options.srt) {
        subtitleData = subtitleGenerator.parseSRTFile(options.srt);
        console.log('SRT 文件解析完成！');
        console.log(`字幕数量: ${subtitleData.count}`);
        console.log(`总时长: ${helpers.formatDuration(subtitleData.totalDuration)}`);
        
        if (options.output) {
          const saveResult = await subtitleGenerator.saveSRT(subtitleData, options.output);
          console.log(`字幕已保存到: ${saveResult.path}`);
        }
        return;
      }

      if (options.ttsResults) {
        const ttsResults = JSON.parse(fs.readFileSync(options.ttsResults, 'utf-8'));
        subtitleData = subtitleGenerator.generateSRTFromTTSResults(ttsResults.results || ttsResults);
      } else if (options.text || options.file) {
        let text = options.text;
        if (options.file) {
          text = fs.readFileSync(options.file, 'utf-8');
        }
        subtitleData = subtitleGenerator.generateSRTFromText(text, {
          totalDuration: options.duration ? parseFloat(options.duration) : null,
        });
      } else {
        console.error('请提供 --text、--file 或 --tts-results 参数');
        process.exit(1);
      }

      console.log('字幕生成完成！');
      console.log(`字幕数量: ${subtitleData.count}`);
      
      if (options.output) {
        const saveResult = await subtitleGenerator.saveSRT(subtitleData, options.output);
        console.log(`字幕已保存到: ${saveResult.path}`);
      } else {
        console.log('\n生成的 SRT 内容:');
        console.log(subtitleData.srtContent);
      }
    } catch (error) {
      console.error('字幕生成失败:', error.message);
      process.exit(1);
    }
  });

program
  .command('bgm')
  .description('处理背景音乐')
  .requiredOption('-i, --input <path>', '输入音频文件路径')
  .option('-o, --output <path>', '输出音频文件路径')
  .option('-d, --duration <seconds>', '目标时长（秒）')
  .option('-v, --volume <volume>', '音量（0.0-1.0）', '0.3')
  .option('--fade-in <seconds>', '淡入时长', '1.0')
  .option('--fade-out <seconds>', '淡出时长', '1.0')
  .option('--ducking', '应用闪避效果')
  .option('--voice-segments <path>', '语音片段 JSON 文件（用于闪避）')
  .action(async (options) => {
    try {
      const bgmService = new BackgroundMusicService({
        defaultVolume: parseFloat(options.volume),
        fadeDuration: parseFloat(options.fadeIn),
      });

      let result;

      if (options.duration) {
        result = await bgmService.loopAudioToDuration(
          options.input,
          parseFloat(options.duration),
          {
            outputDir: options.output ? path.dirname(options.output) : undefined,
            outputFileName: options.output ? path.basename(options.output) : undefined,
            volume: parseFloat(options.volume),
            fadeIn: parseFloat(options.fadeIn),
            fadeOut: parseFloat(options.fadeOut),
          }
        );
        console.log('背景音乐循环处理完成！');
      } else if (options.ducking && options.voiceSegments) {
        const voiceSegments = JSON.parse(fs.readFileSync(options.voiceSegments, 'utf-8'));
        result = await bgmService.applyDucking(
          options.input,
          voiceSegments,
          {
            outputDir: options.output ? path.dirname(options.output) : undefined,
            outputFileName: options.output ? path.basename(options.output) : undefined,
          }
        );
        console.log('闪避效果处理完成！');
      } else {
        result = await bgmService.addFadeEffects(options.input, {
          outputDir: options.output ? path.dirname(options.output) : undefined,
          outputFileName: options.output ? path.basename(options.output) : undefined,
          fadeIn: parseFloat(options.fadeIn),
          fadeOut: parseFloat(options.fadeOut),
        });
        console.log('淡入淡出效果处理完成！');
      }

      console.log(`输出文件: ${result.outputPath}`);
    } catch (error) {
      console.error('背景音乐处理失败:', error.message);
      process.exit(1);
    }
  });

program
  .command('compose')
  .description('合成视频（整合所有功能）')
  .requiredOption('-i, --input <path>', '输入视频文件路径')
  .option('-t, --text <text>', 'TTS 文本内容')
  .option('--text-file <path>', '从文件读取 TTS 文本')
  .option('-b, --bgm <path>', '背景音乐文件路径')
  .option('-o, --output <name>', '输出文件名（不含扩展名）')
  .option('-s, --segment-duration <seconds>', '视频分割时长', '30')
  .option('--no-tts', '不添加 TTS')
  .option('--no-subtitles', '不添加字幕')
  .option('--no-bgm', '不添加背景音乐')
  .option('--split', '先分割视频再合成')
  .action(async (options) => {
    try {
      const composer = new VideoComposer();

      let textContent = options.text;
      if (options.textFile) {
        textContent = fs.readFileSync(options.textFile, 'utf-8');
      }

      let result;

      if (options.split) {
        result = await composer.splitAndCompose({
          videoPath: options.input,
          segmentDuration: parseInt(options.segmentDuration),
          textContent: textContent,
          backgroundMusicPath: options.bgm,
          outputFileName: options.output,
          addTTS: options.tts !== false && !!textContent,
          addSubtitles: options.subtitles !== false,
          addBackgroundMusic: options.bgm !== false && !!options.bgm,
        });
      } else {
        result = await composer.composeVideo({
          videoPath: options.input,
          textContent: textContent,
          backgroundMusicPath: options.bgm,
          outputFileName: options.output,
          addTTS: options.tts !== false && !!textContent,
          addSubtitles: options.subtitles !== false,
          addBackgroundMusic: options.bgm !== false && !!options.bgm,
        });
      }

      console.log('视频合成完成！');
      console.log(`输出文件: ${result.outputPath}`);
      console.log(`视频时长: ${helpers.formatDuration(result.videoInfo.duration)}`);
      console.log(`分辨率: ${result.videoInfo.video.width}x${result.videoInfo.video.height}`);
      console.log('\n应用的效果:');
      console.log(`  - TTS: ${result.ttsAdded ? '已添加' : '未添加'}`);
      console.log(`  - 字幕: ${result.subtitlesAdded ? '已添加' : '未添加'}`);
      console.log(`  - 背景音乐: ${result.backgroundMusicAdded ? '已添加' : '未添加'}`);
    } catch (error) {
      console.error('视频合成失败:', error.message);
      process.exit(1);
    }
  });

program
  .command('list-voices')
  .description('列出可用的 TTS 语音')
  .option('-l, --language <code>', '语言代码', 'zh-CN')
  .action(async (options) => {
    try {
      const ttsService = new TTSService();
      const result = await ttsService.listVoices(options.language);

      console.log(`可用的 ${options.language} 语音列表:`);
      console.log('-' .repeat(60));
      result.voices.forEach((voice, index) => {
        console.log(`${index + 1}. 名称: ${voice.name}`);
        console.log(`   语言: ${voice.languageCodes.join(', ')}`);
        console.log(`   性别: ${voice.ssmlGender}`);
        console.log(`   采样率: ${voice.naturalSampleRateHertz}Hz`);
        console.log('');
      });
    } catch (error) {
      console.error('获取语音列表失败:', error.message);
      process.exit(1);
    }
  });

program
  .command('info')
  .description('获取视频/音频信息')
  .requiredOption('-i, --input <path>', '输入文件路径')
  .action(async (options) => {
    try {
      const ext = path.extname(options.input).toLowerCase();
      let info;

      if (['.mp4', '.avi', '.mov', '.mkv', '.webm'].includes(ext)) {
        const splitter = new VideoSplitter();
        info = await splitter.getVideoInfo(options.input);
        console.log('视频信息:');
        console.log('-' .repeat(40));
        console.log(`时长: ${helpers.formatDuration(info.duration)}`);
        console.log(`大小: ${(info.size / 1024 / 1024).toFixed(2)} MB`);
        console.log(`码率: ${(info.bitrate / 1000).toFixed(2)} kbps`);
        console.log('\n视频流:');
        console.log(`  编码: ${info.video.codec}`);
        console.log(`  分辨率: ${info.video.width}x${info.video.height}`);
        console.log(`  帧率: ${info.video.fps} fps`);
        if (info.audio) {
          console.log('\n音频流:');
          console.log(`  编码: ${info.audio.codec}`);
          console.log(`  采样率: ${info.audio.sampleRate} Hz`);
          console.log(`  声道: ${info.audio.channels}`);
        }
      } else if (['.mp3', '.wav', '.ogg', '.flac', '.aac'].includes(ext)) {
        const bgmService = new BackgroundMusicService();
        info = await bgmService.getAudioInfo(options.input);
        console.log('音频信息:');
        console.log('-' .repeat(40));
        console.log(`时长: ${helpers.formatDuration(info.duration)}`);
        console.log(`大小: ${(info.size / 1024 / 1024).toFixed(2)} MB`);
        console.log(`码率: ${(info.bitrate / 1000).toFixed(2)} kbps`);
        if (info.audio) {
          console.log('\n音频流:');
          console.log(`  编码: ${info.audio.codec}`);
          console.log(`  采样率: ${info.audio.sampleRate} Hz`);
          console.log(`  声道: ${info.audio.channels}`);
        }
      } else {
        console.error('不支持的文件格式');
        process.exit(1);
      }
    } catch (error) {
      console.error('获取文件信息失败:', error.message);
      process.exit(1);
    }
  });

program.parse(process.argv);

if (process.argv.length < 3) {
  program.help();
}