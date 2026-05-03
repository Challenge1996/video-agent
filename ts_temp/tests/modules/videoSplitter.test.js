import VideoSplitter from '../../src/modules/videoSplitter.js';
import testHelpers from '../testHelpers.js';
import sinon from 'sinon';
import fs from 'fs-extra';
import path from 'path';
import ffmpeg from 'fluent-ffmpeg';

describe('VideoSplitter', () => {
  let videoSplitter;
  let tempDir;
  let sandbox;

  beforeEach(() => {
    tempDir = testHelpers.createTempDir();
    videoSplitter = new VideoSplitter({
      outputDir: tempDir,
      segmentDuration: 30,
    });
    sandbox = sinon.createSandbox();
  });

  afterEach(() => {
    testHelpers.cleanupTempDir(tempDir);
    sandbox.restore();
  });

  describe('constructor', () => {
    test('should create instance with default options', () => {
      const splitter = new VideoSplitter();
      expect(splitter).toBeInstanceOf(VideoSplitter);
    });

    test('should create instance with custom options', () => {
      const splitter = new VideoSplitter({
        segmentDuration: 60,
        outputDir: '/custom/path',
      });
      expect(splitter).toBeInstanceOf(VideoSplitter);
    });
  });

  describe('_createConcatFile', () => {
    test('should create valid concat file', () => {
      const videoPaths = [
        '/test/segment1.mp4',
        '/test/segment2.mp4',
        '/test/segment3.mp4',
      ];

      const concatFile = videoSplitter._createConcatFile(videoPaths);

      expect(fs.existsSync(concatFile)).toBe(true);
      const content = fs.readFileSync(concatFile, 'utf-8');
      expect(content).toContain("file '/test/segment1.mp4'");
      expect(content).toContain("file '/test/segment2.mp4'");
      expect(content).toContain("file '/test/segment3.mp4'");

      fs.unlinkSync(concatFile);
    });

    test('should handle paths with special characters', () => {
      const videoPaths = [
        "/test/path with spaces/video.mp4",
        "/test/path'with'quotes/video.mp4",
      ];

      const concatFile = videoSplitter._createConcatFile(videoPaths);

      expect(fs.existsSync(concatFile)).toBe(true);
      const content = fs.readFileSync(concatFile, 'utf-8');
      expect(content).toContain("file '/test/path with spaces/video.mp4'");

      fs.unlinkSync(concatFile);
    });
  });

  describe('splitVideo (with mocked ffprobe)', () => {
    test('should calculate correct segments based on duration', async () => {
      const mockMetadata = testHelpers.createMockVideoMetadata({
        format: { duration: '65.0', size: 104857600, bit_rate: 5000000 },
      });

      const ffprobeStub = sandbox.stub(ffmpeg, 'ffprobe').callsFake((path, callback) => {
        callback(null, mockMetadata);
      });

      const extractSegmentStub = sandbox.stub(videoSplitter, '_extractSegment').resolves('output.mp4');

      const result = await videoSplitter.splitVideo('/test/video.mp4', {
        segmentDuration: 30,
      });

      expect(result.segmentCount).toBe(3);
      expect(result.segments.length).toBe(3);
      expect(result.segments[0].duration).toBe(30);
      expect(result.segments[1].duration).toBe(30);
      expect(result.segments[2].duration).toBe(5);
    });

    test('should handle exact duration video', async () => {
      const mockMetadata = testHelpers.createMockVideoMetadata({
        format: { duration: '60.0' },
      });

      sandbox.stub(ffmpeg, 'ffprobe').callsFake((path, callback) => {
        callback(null, mockMetadata);
      });

      sandbox.stub(videoSplitter, '_extractSegment').resolves('output.mp4');

      const result = await videoSplitter.splitVideo('/test/video.mp4', {
        segmentDuration: 30,
      });

      expect(result.segmentCount).toBe(2);
    });

    test('should throw error when ffprobe fails', async () => {
      sandbox.stub(ffmpeg, 'ffprobe').callsFake((path, callback) => {
        callback(new Error('ffprobe error'));
      });

      await expect(
        videoSplitter.getVideoInfo('/test/video.mp4')
      ).rejects.toThrow('无法获取视频信息');
    });
  });

  describe('splitByCustomIntervals validation', () => {
    test('should throw error for invalid interval (out of range)', async () => {
      const mockMetadata = testHelpers.createMockVideoMetadata({
        format: { duration: '60.0' },
      });

      sandbox.stub(ffmpeg, 'ffprobe').callsFake((path, callback) => {
        callback(null, mockMetadata);
      });

      sandbox.stub(videoSplitter, '_extractSegment').resolves('output.mp4');

      const invalidIntervals = [
        { startTime: 50, endTime: 100 },
      ];

      await expect(
        videoSplitter.splitByCustomIntervals('/test/video.mp4', invalidIntervals)
      ).rejects.toThrow('时间区间超出视频范围');
    });

    test('should validate multiple intervals', async () => {
      const mockMetadata = testHelpers.createMockVideoMetadata({
        format: { duration: '120.0' },
      });

      sandbox.stub(ffmpeg, 'ffprobe').callsFake((path, callback) => {
        callback(null, mockMetadata);
      });

      sandbox.stub(videoSplitter, '_extractSegment').resolves('output.mp4');

      const intervals = [
        { startTime: 0, endTime: 30 },
        { startTime: 40, endTime: 70 },
        { startTime: 90, endTime: 120 },
      ];

      const result = await videoSplitter.splitByCustomIntervals(
        '/test/video.mp4',
        intervals
      );

      expect(result.segmentCount).toBe(3);
    });
  });

  describe('mergeVideos', () => {
    test('should throw error when no videos provided', async () => {
      await expect(
        videoSplitter.mergeVideos([], '/test/output.mp4')
      ).rejects.toThrow('没有提供要合并的视频文件');
    });
  });
});