import SubtitleGenerator from '../../src/modules/subtitleGenerator.js';
import testHelpers from '../testHelpers.js';
import fs from 'fs-extra';
import path from 'path';

describe('SubtitleGenerator', () => {
  let subtitleGenerator;
  let tempDir;

  beforeEach(() => {
    tempDir = testHelpers.createTempDir();
    subtitleGenerator = new SubtitleGenerator({
      outputDir: tempDir,
    });
  });

  afterEach(() => {
    testHelpers.cleanupTempDir(tempDir);
  });

  describe('constructor', () => {
    test('should create instance with default options', () => {
      const gen = new SubtitleGenerator();
      expect(gen).toBeInstanceOf(SubtitleGenerator);
    });

    test('should create instance with custom options', () => {
      const gen = new SubtitleGenerator({
        outputDir: '/custom/path',
        defaultDurationPerChar: 0.2,
        minDuration: 2.0,
        maxDuration: 10.0,
      });
      expect(gen).toBeInstanceOf(SubtitleGenerator);
    });
  });

  describe('generateSRTFromText', () => {
    test('should generate SRT from simple text', () => {
      const text = '欢迎使用视频剪辑 Agent。这是一个功能强大的工具。';
      
      const result = subtitleGenerator.generateSRTFromText(text);
      
      expect(result).toBeDefined();
      expect(result.segments).toBeDefined();
      expect(result.srtContent).toBeDefined();
      expect(typeof result.count).toBe('number');
      expect(result.count).toBeGreaterThan(0);
    });

    test('should segment by sentence by default', () => {
      const text = '第一句。第二句。第三句。';
      
      const result = subtitleGenerator.generateSRTFromText(text);
      
      expect(result.segments.length).toBeGreaterThanOrEqual(3);
    });

    test('should handle totalDuration option', () => {
      const text = '这是一段测试文本。';
      
      const result = subtitleGenerator.generateSRTFromText(text, {
        totalDuration: 10,
      });
      
      expect(result).toBeDefined();
      expect(result.segments.length).toBeGreaterThan(0);
    });

    test('should generate valid SRT content', () => {
      const text = '测试文本。';
      
      const result = subtitleGenerator.generateSRTFromText(text);
      
      expect(result.srtContent).toMatch(/^\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n.+$/m);
    });
  });

  describe('generateSRTFromTTSResults', () => {
    test('should generate SRT from TTS results', () => {
      const ttsResults = [
        {
          text: '第一句话',
          duration: 2.5,
          audioPath: '/path/to/audio1.mp3',
        },
        {
          text: '第二句话',
          duration: 3.0,
          audioPath: '/path/to/audio2.mp3',
        },
      ];
      
      const result = subtitleGenerator.generateSRTFromTTSResults(ttsResults);
      
      expect(result).toBeDefined();
      expect(result.segments.length).toBe(2);
      expect(result.count).toBe(2);
      expect(result.srtContent).toBeDefined();
    });

    test('should calculate correct timings with gap', () => {
      const ttsResults = [
        { text: '第一句', duration: 2.0 },
        { text: '第二句', duration: 3.0 },
      ];
      
      const result = subtitleGenerator.generateSRTFromTTSResults(ttsResults, {
        gapBetweenSegments: 0.5,
      });
      
      expect(result.segments[0].startTime).toBe(0);
      expect(result.segments[0].endTime).toBe(2.0);
      expect(result.segments[1].startTime).toBe(2.5);
      expect(result.segments[1].endTime).toBe(5.5);
    });

    test('should include TTS audio path in segments', () => {
      const ttsResults = [
        {
          text: '测试',
          duration: 1.0,
          audioPath: '/test/audio.mp3',
        },
      ];
      
      const result = subtitleGenerator.generateSRTFromTTSResults(ttsResults);
      
      expect(result.segments[0].ttsAudioPath).toBe('/test/audio.mp3');
    });
  });

  describe('saveSRT', () => {
    test('should save SRT content to file', async () => {
      const subtitleData = {
        srtContent: '1\n00:00:00,000 --> 00:00:02,000\n测试字幕\n',
      };
      const outputPath = path.join(tempDir, 'test.srt');
      
      const result = await subtitleGenerator.saveSRT(subtitleData, outputPath);
      
      expect(result.success).toBe(true);
      expect(fs.existsSync(outputPath)).toBe(true);
      
      const content = fs.readFileSync(outputPath, 'utf-8');
      expect(content).toContain('测试字幕');
    });

    test('should handle segments input', async () => {
      const subtitleData = {
        segments: [
          {
            index: 1,
            startTime: 0,
            endTime: 2,
            duration: 2,
            text: '测试字幕',
          },
        ],
      };
      const outputPath = path.join(tempDir, 'test2.srt');
      
      const result = await subtitleGenerator.saveSRT(subtitleData, outputPath);
      
      expect(result.success).toBe(true);
      expect(fs.existsSync(outputPath)).toBe(true);
    });

    test('should throw error for invalid subtitle data', async () => {
      await expect(
        subtitleGenerator.saveSRT({ invalid: 'data' })
      ).rejects.toThrow();
    });
  });

  describe('parseSRT', () => {
    test('should parse valid SRT content', () => {
      const srtContent = `1
00:00:00,000 --> 00:00:02,500
第一句字幕

2
00:00:02,500 --> 00:00:05,000
第二句字幕
第三行`;
      
      const result = subtitleGenerator.parseSRT(srtContent);
      
      expect(result.segments.length).toBe(2);
      expect(result.count).toBe(2);
      expect(result.segments[0].text).toBe('第一句字幕');
      expect(result.segments[1].text).toBe('第二句字幕\n第三行');
    });

    test('should parse timestamps correctly', () => {
      const srtContent = `1
00:01:30,500 --> 00:02:00,000
测试`;
      
      const result = subtitleGenerator.parseSRT(srtContent);
      
      expect(result.segments[0].startTime).toBe(90.5);
      expect(result.segments[0].endTime).toBe(120.0);
      expect(result.segments[0].duration).toBe(29.5);
    });

    test('should return empty array for invalid content', () => {
      const result = subtitleGenerator.parseSRT('invalid content');
      
      expect(result.segments.length).toBe(0);
      expect(result.count).toBe(0);
    });
  });

  describe('parseSRTFile', () => {
    test('should parse SRT file', async () => {
      const srtContent = `1
00:00:00,000 --> 00:00:02,000
测试字幕`;
      const srtPath = path.join(tempDir, 'test.srt');
      fs.writeFileSync(srtPath, srtContent);
      
      const result = subtitleGenerator.parseSRTFile(srtPath);
      
      expect(result.segments.length).toBe(1);
      expect(result.segments[0].text).toBe('测试字幕');
    });

    test('should throw error for non-existent file', () => {
      expect(() => {
        subtitleGenerator.parseSRTFile('/non/existent/path.srt');
      }).toThrow();
    });
  });

  describe('mergeSubtitles', () => {
    test('should merge multiple subtitle groups', () => {
      const group1 = {
        segments: [
          { index: 1, startTime: 0, endTime: 2, duration: 2, text: '第一组' },
        ],
      };
      const group2 = {
        segments: [
          { index: 1, startTime: 0, endTime: 3, duration: 3, text: '第二组' },
        ],
      };
      
      const result = subtitleGenerator.mergeSubtitles([group1, group2]);
      
      expect(result.segments.length).toBe(2);
      expect(result.segments[0].text).toBe('第一组');
      expect(result.segments[1].text).toBe('第二组');
    });

    test('should handle gap between groups', () => {
      const group1 = {
        segments: [
          { index: 1, startTime: 0, endTime: 2, duration: 2, text: '第一' },
        ],
      };
      const group2 = {
        segments: [
          { index: 1, startTime: 0, endTime: 3, duration: 3, text: '第二' },
        ],
      };
      
      const result = subtitleGenerator.mergeSubtitles([group1, group2], {
        gapBetweenGroups: 1.0,
      });
      
      expect(result.segments[0].endTime).toBe(2);
      expect(result.segments[1].startTime).toBe(3);
    });

    test('should apply time offset', () => {
      const group1 = {
        segments: [
          { index: 1, startTime: 0, endTime: 2, duration: 2, text: '测试' },
        ],
      };
      
      const result = subtitleGenerator.mergeSubtitles([group1], {
        timeOffset: 10.0,
      });
      
      expect(result.segments[0].startTime).toBe(10);
      expect(result.segments[0].endTime).toBe(12);
    });
  });

  describe('adjustTiming', () => {
    test('should apply offset to all segments', () => {
      const subtitleData = {
        segments: [
          { index: 1, startTime: 0, endTime: 2, duration: 2, text: '测试' },
        ],
      };
      
      const result = subtitleGenerator.adjustTiming(subtitleData, {
        offset: 5.0,
      });
      
      expect(result.segments[0].startTime).toBe(5);
      expect(result.segments[0].endTime).toBe(7);
      expect(result.segments[0].duration).toBe(2);
    });

    test('should apply speed factor', () => {
      const subtitleData = {
        segments: [
          { index: 1, startTime: 0, endTime: 10, duration: 10, text: '测试' },
        ],
      };
      
      const result = subtitleGenerator.adjustTiming(subtitleData, {
        speedFactor: 0.5,
      });
      
      expect(result.segments[0].duration).toBe(5);
      expect(result.segments[0].endTime).toBe(5);
    });

    test('should set new start time', () => {
      const subtitleData = {
        segments: [
          { index: 1, startTime: 10, endTime: 20, duration: 10, text: '测试' },
        ],
      };
      
      const result = subtitleGenerator.adjustTiming(subtitleData, {
        newStartTime: 0,
      });
      
      expect(result.segments[0].startTime).toBe(0);
      expect(result.segments[0].duration).toBe(10);
    });
  });
});