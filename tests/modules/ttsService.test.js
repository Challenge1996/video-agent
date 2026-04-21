import TTSService from '../../src/modules/ttsService.js';
import testHelpers from '../testHelpers.js';
import sinon from 'sinon';
import fs from 'fs-extra';
import path from 'path';

describe('TTSService', () => {
  let ttsService;
  let tempDir;
  let sandbox;

  beforeEach(() => {
    tempDir = testHelpers.createTempDir();
    ttsService = new TTSService({
      outputDir: tempDir,
      languageCode: 'zh-CN',
      voiceName: 'zh-CN-Wavenet-A',
    });
    sandbox = sinon.createSandbox();
  });

  afterEach(() => {
    testHelpers.cleanupTempDir(tempDir);
    sandbox.restore();
  });

  describe('constructor', () => {
    test('should create instance with default options', () => {
      const service = new TTSService();
      expect(service).toBeInstanceOf(TTSService);
    });

    test('should create instance with custom options', () => {
      const service = new TTSService({
        languageCode: 'en-US',
        voiceName: 'en-US-Wavenet-D',
        speakingRate: 1.2,
        pitch: 2.0,
        outputDir: '/custom/path',
      });
      expect(service).toBeInstanceOf(TTSService);
    });
  });

  describe('createSSML', () => {
    test('should create basic SSML from text', () => {
      const text = '这是测试文本';
      const ssml = ttsService.createSSML(text);

      expect(ssml).toContain('<speak>');
      expect(ssml).toContain('</speak>');
      expect(ssml).toContain(text);
    });

    test('should include prosody tags when options provided', () => {
      const text = '测试';
      const ssml = ttsService.createSSML(text, {
        speakingRate: 1.5,
        pitch: 2.0,
        volume: 'loud',
      });

      expect(ssml).toContain('<prosody');
      expect(ssml).toContain('rate="1.5"');
      expect(ssml).toContain('pitch="+2st"');
      expect(ssml).toContain('volume="loud"');
    });

    test('should handle break times', () => {
      const text = '第一句__BREAK_0__第二句';
      const ssml = ttsService.createSSML(text, {
        breakTimes: ['500ms'],
      });

      expect(ssml).toContain('<break time="500ms"/>');
    });
  });

  describe('synthesizeSpeech with mock client', () => {
    test('should build correct request options', async () => {
      const mockClient = {
        synthesizeSpeech: sandbox.stub().resolves([{
          audioContent: Buffer.from('fake audio'),
        }]),
      };

      ttsService.client = mockClient;

      const getAudioInfoStub = sandbox.stub(ttsService, '_getAudioInfo').resolves({
        duration: 2.5,
        audio: { codec: 'mp3' },
      });

      const text = '测试文本';
      const result = await ttsService.synthesizeSpeech(text, {
        languageCode: 'en-US',
        voiceName: 'en-US-Wavenet-D',
        speakingRate: 1.5,
        pitch: 2.0,
      });

      expect(mockClient.synthesizeSpeech.calledOnce).toBe(true);
      const callArgs = mockClient.synthesizeSpeech.getCall(0).args[0];
      
      expect(callArgs.input.text).toBe(text);
      expect(callArgs.voice.languageCode).toBe('en-US');
      expect(callArgs.voice.name).toBe('en-US-Wavenet-D');
      expect(callArgs.audioConfig.speakingRate).toBe(1.5);
      expect(callArgs.audioConfig.pitch).toBe(2.0);
    });

    test('should throw error when synthesis fails', async () => {
      const mockClient = {
        synthesizeSpeech: sandbox.stub().rejects(new Error('API Error')),
      };

      ttsService.client = mockClient;

      await expect(
        ttsService.synthesizeSpeech('测试')
      ).rejects.toThrow('TTS 合成失败');
    });
  });

  describe('synthesizeBatch', () => {
    test('should handle text objects with options', async () => {
      const mockClient = {
        synthesizeSpeech: sandbox.stub().resolves([{
          audioContent: Buffer.from('fake audio'),
        }]),
      };

      ttsService.client = mockClient;

      sandbox.stub(ttsService, '_getAudioInfo').resolves({
        duration: 2.5,
        audio: { codec: 'mp3' },
      });

      const texts = [
        { text: '自定义文本', languageCode: 'en-US', voiceName: 'en-US-Wavenet-A' },
      ];
      
      const result = await ttsService.synthesizeBatch(texts);

      expect(result.success).toBe(true);
      expect(mockClient.synthesizeSpeech.calledOnce).toBe(true);
    });
  });

  describe('listVoices', () => {
    test('should call listVoices with correct language', async () => {
      const mockVoices = [
        {
          name: 'zh-CN-Wavenet-A',
          languageCodes: ['zh-CN'],
          ssmlGender: 'FEMALE',
          naturalSampleRateHertz: 24000,
        },
      ];

      const mockClient = {
        listVoices: sandbox.stub().resolves([{ voices: mockVoices }]),
      };

      ttsService.client = mockClient;

      const result = await ttsService.listVoices('zh-CN');

      expect(mockClient.listVoices.calledOnce).toBe(true);
      expect(mockClient.listVoices.getCall(0).args[0].languageCode).toBe('zh-CN');
      expect(result.voices.length).toBe(1);
      expect(result.voices[0].name).toBe('zh-CN-Wavenet-A');
    });

    test('should throw error when list voices fails', async () => {
      const mockClient = {
        listVoices: sandbox.stub().rejects(new Error('API Error')),
      };

      ttsService.client = mockClient;

      await expect(
        ttsService.listVoices()
      ).rejects.toThrow('获取语音列表失败');
    });
  });
});