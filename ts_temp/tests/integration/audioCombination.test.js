import VideoComposer from '../../src/modules/videoComposer.js';
import MiniMaxTTSService from '../../src/modules/miniMaxTTSService.js';
import GoogleTTSService from '../../src/modules/ttsService.js';
import testHelpers from '../testHelpers.js';
import sinon from 'sinon';
import fs from 'fs-extra';
import path from 'path';
import ffmpeg from 'fluent-ffmpeg';

const TEST_VIDEO_PATH = path.join(process.cwd(), 'media/1.mp4');
const TEST_BGM_PATH = path.join(process.cwd(), 'media/bg.aac');
const TEST_TEXT = '今天是不是很开心呀(laughs)，当然了！';

describe('音频集成测试', () => {
  let videoComposer;
  let tempDir;
  let sandbox;

  beforeAll(() => {
    if (!fs.existsSync(TEST_VIDEO_PATH)) {
      console.warn(`测试视频文件不存在: ${TEST_VIDEO_PATH}`);
    }
    if (!fs.existsSync(TEST_BGM_PATH)) {
      console.warn(`测试背景音乐文件不存在: ${TEST_BGM_PATH}`);
    }
  });

  beforeEach(() => {
    tempDir = testHelpers.createTempDir();
    sandbox = sinon.createSandbox();
  });

  afterEach(() => {
    testHelpers.cleanupTempDir(tempDir);
    sandbox.restore();
  });

  describe('MiniMax TTS 服务测试', () => {
    test('应该正确初始化 MiniMaxTTSService', () => {
      const ttsService = new MiniMaxTTSService({
        apiKey: 'test-api-key',
        baseUrl: 'https://api.minimax.chat/v1/t2a_v2',
      });

      expect(ttsService).toBeInstanceOf(MiniMaxTTSService);
      expect(ttsService.options.apiKey).toBe('test-api-key');
      expect(ttsService.options.baseUrl).toBe('https://api.minimax.chat/v1/t2a_v2');
    });

    test('应该正确返回基础 URL', () => {
      const ttsService = new MiniMaxTTSService({
        apiKey: 'test-api-key',
        baseUrl: 'https://api.minimax.chat/v1/t2a_v2',
      });

      const url = ttsService._getBaseUrl();
      expect(url).toBe('https://api.minimax.chat/v1/t2a_v2');
    });

    test('应该正确返回带查询参数的 URL', () => {
      const ttsService = new MiniMaxTTSService({
        apiKey: 'test-api-key',
        baseUrl: 'https://api.minimax.chat/v1/t2a_v2?param=value',
      });

      const url = ttsService._getBaseUrl();
      expect(url).toBe('https://api.minimax.chat/v1/t2a_v2?param=value');
    });
  });

  describe('VideoComposer TTS 提供商切换测试', () => {
    test('应该默认使用 MiniMax 作为 TTS 提供商', () => {
      const composer = new VideoComposer({
        outputDir: path.join(tempDir, 'output'),
        tempDir: path.join(tempDir, 'temp'),
      });

      expect(composer.ttsService).toBeInstanceOf(MiniMaxTTSService);
    });

    test('应该支持显式指定 MiniMax 提供商', () => {
      const composer = new VideoComposer({
        outputDir: path.join(tempDir, 'output'),
        tempDir: path.join(tempDir, 'temp'),
        ttsProvider: 'minimax',
      });

      expect(composer.ttsService).toBeInstanceOf(MiniMaxTTSService);
    });

    test('应该支持指定 Google 提供商', () => {
      const composer = new VideoComposer({
        outputDir: path.join(tempDir, 'output'),
        tempDir: path.join(tempDir, 'temp'),
        ttsProvider: 'google',
      });

      expect(composer.ttsService).toBeInstanceOf(GoogleTTSService);
    });

    test('未知提供商应该默认使用 MiniMax', () => {
      const composer = new VideoComposer({
        outputDir: path.join(tempDir, 'output'),
        tempDir: path.join(tempDir, 'temp'),
        ttsProvider: 'unknown',
      });

      expect(composer.ttsService).toBeInstanceOf(MiniMaxTTSService);
    });
  });

  describe('音频优先级逻辑测试', () => {
    test('_calculateAudioPriority 应该正确计算优先级 - 有 TTS 的情况', () => {
      const composer = new VideoComposer({
        outputDir: path.join(tempDir, 'output'),
        tempDir: path.join(tempDir, 'temp'),
      });

      const config1 = composer._calculateAudioPriority(
        true,
        true,
        { meanVolume: -20, maxVolume: -15, hasAudio: true },
        true
      );
      expect(config1.useOriginalAudio).toBe(false);
      expect(config1.isOriginalAudioSilent).toBe(false);
    });

    test('_calculateAudioPriority 应该正确计算优先级 - 无 TTS 有视频原声的情况', () => {
      const composer = new VideoComposer({
        outputDir: path.join(tempDir, 'output'),
        tempDir: path.join(tempDir, 'temp'),
      });

      const config2 = composer._calculateAudioPriority(
        false,
        true,
        { meanVolume: -20, maxVolume: -15, hasAudio: true },
        true
      );
      expect(config2.useOriginalAudio).toBe(true);
      expect(config2.isOriginalAudioSilent).toBe(false);
    });

    test('_calculateAudioPriority 应该正确计算优先级 - 视频原声静音的情况', () => {
      const composer = new VideoComposer({
        outputDir: path.join(tempDir, 'output'),
        tempDir: path.join(tempDir, 'temp'),
      });

      const config3 = composer._calculateAudioPriority(
        true,
        true,
        { meanVolume: -60, maxVolume: -55, hasAudio: true },
        true
      );
      expect(config3.isOriginalAudioSilent).toBe(true);
    });

    test('_calculateAudioPriority 应该正确计算优先级 - 无视频原声的情况', () => {
      const composer = new VideoComposer({
        outputDir: path.join(tempDir, 'output'),
        tempDir: path.join(tempDir, 'temp'),
      });

      const config4 = composer._calculateAudioPriority(
        false,
        true,
        { meanVolume: null, maxVolume: null, hasAudio: false },
        false
      );
      expect(config4.useOriginalAudio).toBe(false);
      expect(config4.isOriginalAudioSilent).toBe(true);
    });

    test('_calculateAudioPriority 应该正确计算背景音乐音量', () => {
      const composer = new VideoComposer({
        outputDir: path.join(tempDir, 'output'),
        tempDir: path.join(tempDir, 'temp'),
      });

      const configWithTTS = composer._calculateAudioPriority(
        true,
        true,
        { meanVolume: -20, maxVolume: -15, hasAudio: true },
        true
      );
      expect(configWithTTS.backgroundMusicVolume).toBe(0.15);

      const configWithoutTTS = composer._calculateAudioPriority(
        false,
        true,
        { meanVolume: -20, maxVolume: -15, hasAudio: true },
        true
      );
      expect(configWithoutTTS.backgroundMusicVolume).toBe(0.2);

      const configSilentWithTTS = composer._calculateAudioPriority(
        true,
        true,
        { meanVolume: -60, maxVolume: -55, hasAudio: true },
        true
      );
      expect(configSilentWithTTS.backgroundMusicVolume).toBe(0.3);
    });
  });

  describe('基本视频合成测试', () => {
    test('应该能够创建 VideoComposer 实例', () => {
      const composer = new VideoComposer({
        outputDir: path.join(tempDir, 'output'),
        tempDir: path.join(tempDir, 'temp'),
      });

      expect(composer).toBeInstanceOf(VideoComposer);
      expect(composer.videoSplitter).toBeDefined();
      expect(composer.ttsService).toBeDefined();
      expect(composer.subtitleGenerator).toBeDefined();
      expect(composer.backgroundMusicService).toBeDefined();
      expect(composer.stickerService).toBeDefined();
    });

    test('应该验证视频路径必填', async () => {
      const composer = new VideoComposer({
        outputDir: path.join(tempDir, 'output'),
        tempDir: path.join(tempDir, 'temp'),
      });

      await expect(
        composer.composeVideo({})
      ).rejects.toThrow('必须提供视频路径');
    });

    test('应该验证视频文件存在', async () => {
      const composer = new VideoComposer({
        outputDir: path.join(tempDir, 'output'),
        tempDir: path.join(tempDir, 'temp'),
      });

      await expect(
        composer.composeVideo({
          videoPath: '/non/existent/video.mp4',
        })
      ).rejects.toThrow('视频文件不存在');
    });
  });
});
