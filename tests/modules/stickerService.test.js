import StickerService from '../../src/modules/stickerService.js';
import testHelpers from '../testHelpers.js';
import sinon from 'sinon';
import fs from 'fs-extra';
import path from 'path';
import ffmpeg from 'fluent-ffmpeg';

describe('StickerService', () => {
  let stickerService;
  let tempDir;
  let sandbox;

  beforeEach(() => {
    tempDir = testHelpers.createTempDir();
    stickerService = new StickerService({
      outputDir: path.join(tempDir, 'output'),
    });
    sandbox = sinon.createSandbox();
  });

  afterEach(() => {
    testHelpers.cleanupTempDir(tempDir);
    sandbox.restore();
  });

  describe('constructor', () => {
    test('should create instance with default options', () => {
      const service = new StickerService();
      expect(service).toBeInstanceOf(StickerService);
    });

    test('should create instance with custom options', () => {
      const customOutputDir = path.join(tempDir, 'custom-output');
      const service = new StickerService({
        outputDir: customOutputDir,
        defaultOpacity: 0.8,
        defaultScale: 0.5,
        defaultPosition: 'bottom-right',
      });
      expect(service).toBeInstanceOf(StickerService);
    });
  });

  describe('_validateStickerOptions', () => {
    test('should throw error when sticker path is empty', () => {
      const videoInfo = { width: 1920, height: 1080, duration: 60 };
      expect(() => {
        stickerService._validateStickerOptions({}, videoInfo);
      }).toThrow('贴纸路径不能为空');
    });

    test('should throw error when sticker file does not exist', () => {
      const videoInfo = { width: 1920, height: 1080, duration: 60 };
      expect(() => {
        stickerService._validateStickerOptions({ path: '/non/existent/image.png' }, videoInfo);
      }).toThrow('贴纸文件不存在');
    });

    test('should throw error when scale is invalid', () => {
      const stickerPath = path.join(tempDir, 'test.png');
      fs.writeFileSync(stickerPath, 'fake image content');
      const videoInfo = { width: 1920, height: 1080, duration: 60 };

      expect(() => {
        stickerService._validateStickerOptions({ path: stickerPath, scale: 0 }, videoInfo);
      }).toThrow('缩放比例必须大于0');

      expect(() => {
        stickerService._validateStickerOptions({ path: stickerPath, scale: -1 }, videoInfo);
      }).toThrow('缩放比例必须大于0');
    });

    test('should throw error when opacity is invalid', () => {
      const stickerPath = path.join(tempDir, 'test.png');
      fs.writeFileSync(stickerPath, 'fake image content');
      const videoInfo = { width: 1920, height: 1080, duration: 60 };

      expect(() => {
        stickerService._validateStickerOptions({ path: stickerPath, opacity: -0.1 }, videoInfo);
      }).toThrow('透明度必须在0到1之间');

      expect(() => {
        stickerService._validateStickerOptions({ path: stickerPath, opacity: 1.1 }, videoInfo);
      }).toThrow('透明度必须在0到1之间');
    });

    test('should throw error when startSeconds is negative', () => {
      const stickerPath = path.join(tempDir, 'test.png');
      fs.writeFileSync(stickerPath, 'fake image content');
      const videoInfo = { width: 1920, height: 1080, duration: 60 };

      expect(() => {
        stickerService._validateStickerOptions({ path: stickerPath, startSeconds: -1 }, videoInfo);
      }).toThrow('开始时间不能为负数');
    });

    test('should throw error when duration is invalid', () => {
      const stickerPath = path.join(tempDir, 'test.png');
      fs.writeFileSync(stickerPath, 'fake image content');
      const videoInfo = { width: 1920, height: 1080, duration: 60 };

      expect(() => {
        stickerService._validateStickerOptions({ path: stickerPath, duration: 0 }, videoInfo);
      }).toThrow('持续时间必须大于0');

      expect(() => {
        stickerService._validateStickerOptions({ path: stickerPath, duration: -5 }, videoInfo);
      }).toThrow('持续时间必须大于0');
    });

    test('should throw error when sticker type is invalid', () => {
      const stickerPath = path.join(tempDir, 'test.png');
      fs.writeFileSync(stickerPath, 'fake image content');
      const videoInfo = { width: 1920, height: 1080, duration: 60 };

      expect(() => {
        stickerService._validateStickerOptions({ path: stickerPath, type: 'invalid' }, videoInfo);
      }).toThrow('不支持的贴纸类型');
    });

    test('should return validated options for valid sticker', () => {
      const stickerPath = path.join(tempDir, 'test.png');
      fs.writeFileSync(stickerPath, 'fake image content');
      const videoInfo = { width: 1920, height: 1080, duration: 60 };

      const result = stickerService._validateStickerOptions({
        path: stickerPath,
        type: 'static',
        position: 'top-right',
        scale: 0.8,
        opacity: 0.9,
        startSeconds: 5,
        duration: 10,
        x: 100,
        y: 100,
      }, videoInfo);

      expect(result.stickerPath).toBe(stickerPath);
      expect(result.type).toBe('static');
      expect(result.position).toBe('top-right');
      expect(result.scale).toBe(0.8);
      expect(result.opacity).toBe(0.9);
      expect(result.startSeconds).toBe(5);
      expect(result.duration).toBe(10);
      expect(result.x).toBe(100);
      expect(result.y).toBe(100);
    });

    test('should use default values when not specified', () => {
      const stickerPath = path.join(tempDir, 'test.png');
      fs.writeFileSync(stickerPath, 'fake image content');
      const videoInfo = { width: 1920, height: 1080, duration: 60 };

      const result = stickerService._validateStickerOptions({
        path: stickerPath,
      }, videoInfo);

      expect(result.type).toBe('static');
      expect(result.startSeconds).toBe(0);
      expect(result.duration).toBeNull();
    });
  });

  describe('_calculatePosition', () => {
    const videoWidth = 1920;
    const videoHeight = 1080;
    const stickerWidth = 200;
    const stickerHeight = 100;

    test('should use explicit x and y coordinates when provided', () => {
      const result = stickerService._calculatePosition(
        'top-left',
        videoWidth,
        videoHeight,
        stickerWidth,
        stickerHeight,
        500,
        300
      );
      expect(result.x).toBe(500);
      expect(result.y).toBe(300);
    });

    test('should calculate position for all predefined locations', () => {
      const positions = [
        'top-left',
        'top',
        'top-right',
        'middle-left',
        'middle',
        'middle-right',
        'bottom-left',
        'bottom',
        'bottom-right',
      ];

      positions.forEach(pos => {
        const result = stickerService._calculatePosition(
          pos,
          videoWidth,
          videoHeight,
          stickerWidth,
          stickerHeight
        );
        expect(result.x).toBeDefined();
        expect(result.y).toBeDefined();
        expect(result.x).toBeGreaterThanOrEqual(0);
        expect(result.y).toBeGreaterThanOrEqual(0);
      });
    });

    test('should return top-left for unknown position', () => {
      const unknownResult = stickerService._calculatePosition(
        'unknown-position',
        videoWidth,
        videoHeight,
        stickerWidth,
        stickerHeight
      );
      const topLeftResult = stickerService._calculatePosition(
        'top-left',
        videoWidth,
        videoHeight,
        stickerWidth,
        stickerHeight
      );
      expect(unknownResult.x).toBe(topLeftResult.x);
      expect(unknownResult.y).toBe(topLeftResult.y);
    });

    test('should handle zero size sticker', () => {
      const result = stickerService._calculatePosition(
        'middle',
        videoWidth,
        videoHeight,
        0,
        0
      );
      expect(result.x).toBe(videoWidth / 2);
      expect(result.y).toBe(videoHeight / 2);
    });
  });

  describe('validateStickerFile', () => {
    test('should return invalid for non-existent file', async () => {
      const result = await stickerService.validateStickerFile('/non/existent/file.png');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('文件不存在');
    });

    test('should validate static image files', async () => {
      const mockMetadata = {
        format: { duration: null, format_name: 'png' },
        streams: [{ codec_type: 'video', width: 200, height: 100 }],
      };

      sandbox.stub(ffmpeg, 'ffprobe').callsFake((path, callback) => {
        callback(null, mockMetadata);
      });

      const stickerPath = path.join(tempDir, 'test.png');
      fs.writeFileSync(stickerPath, 'fake image content');

      const result = await stickerService.validateStickerFile(stickerPath);
      
      expect(result.valid).toBe(true);
      expect(result.type).toBe('static');
      expect(result.isAnimated).toBe(false);
      expect(result.width).toBe(200);
      expect(result.height).toBe(100);
    });

    test('should validate animated GIF files', async () => {
      const mockMetadata = {
        format: { duration: '5.0', format_name: 'gif' },
        streams: [{ codec_type: 'video', width: 300, height: 200 }],
      };

      sandbox.stub(ffmpeg, 'ffprobe').callsFake((path, callback) => {
        callback(null, mockMetadata);
      });

      const stickerPath = path.join(tempDir, 'test.gif');
      fs.writeFileSync(stickerPath, 'fake gif content');

      const result = await stickerService.validateStickerFile(stickerPath);
      
      expect(result.valid).toBe(true);
      expect(result.type).toBe('gif');
      expect(result.isAnimated).toBe(true);
      expect(result.width).toBe(300);
      expect(result.height).toBe(200);
    });

    test('should handle ffprobe errors', async () => {
      sandbox.stub(ffmpeg, 'ffprobe').callsFake((path, callback) => {
        callback(new Error('ffprobe error'));
      });

      const stickerPath = path.join(tempDir, 'test.png');
      fs.writeFileSync(stickerPath, 'fake image content');

      const result = await stickerService.validateStickerFile(stickerPath);
      
      expect(result.valid).toBe(false);
      expect(result.error).toBeDefined();
    });
  });

  describe('addSingleSticker', () => {
    test('should validate sticker options before processing', async () => {
      const videoPath = path.join(tempDir, 'test-video.mp4');
      fs.writeFileSync(videoPath, 'fake video content');

      const mockVideoMetadata = {
        format: { duration: '60.0' },
        streams: [{ codec_type: 'video', width: 1920, height: 1080 }],
      };

      sandbox.stub(ffmpeg, 'ffprobe')
        .onFirstCall().callsFake((path, callback) => callback(null, mockVideoMetadata));

      await expect(
        stickerService.addSingleSticker(videoPath, {
          path: '/non/existent/sticker.png',
        })
      ).rejects.toThrow('贴纸文件不存在');
    });

    test('should validate video exists', async () => {
      const stickerPath = path.join(tempDir, 'sticker.png');
      fs.writeFileSync(stickerPath, 'fake sticker');

      await expect(
        stickerService.addSingleSticker('/non/existent/video.mp4', {
          path: stickerPath,
        })
      ).rejects.toThrow('无法获取视频信息');
    });
  });

  describe('addMultipleStickers', () => {
    test('should throw error when no stickers provided', async () => {
      const videoPath = path.join(tempDir, 'test-video.mp4');
      fs.writeFileSync(videoPath, 'fake video content');

      await expect(
        stickerService.addMultipleStickers(videoPath, [])
      ).rejects.toThrow('没有提供贴纸');

      await expect(
        stickerService.addMultipleStickers(videoPath, null)
      ).rejects.toThrow('没有提供贴纸');
    });

    test('should validate first sticker before ffprobe', async () => {
      const videoPath = path.join(tempDir, 'test-video.mp4');
      fs.writeFileSync(videoPath, 'fake video content');

      const mockVideoMetadata = {
        format: { duration: '60.0' },
        streams: [{ codec_type: 'video', width: 1920, height: 1080 }],
      };

      sandbox.stub(ffmpeg, 'ffprobe')
        .onFirstCall().callsFake((path, callback) => callback(null, mockVideoMetadata));

      await expect(
        stickerService.addMultipleStickers(videoPath, [
          { path: '/non/existent.png', type: 'static' },
        ])
      ).rejects.toThrow('贴纸文件不存在');
    });
  });

  describe('createStaticStickerFromGif', () => {
    test('should throw error when GIF file does not exist', async () => {
      await expect(
        stickerService.createStaticStickerFromGif('/non/existent/animation.gif')
      ).rejects.toThrow('GIF文件不存在');
    });

    test('should throw error when file is not animated', async () => {
      const gifPath = path.join(tempDir, 'test.gif');
      fs.writeFileSync(gifPath, 'fake gif content');

      const mockMetadata = {
        format: { duration: null, format_name: 'png' },
        streams: [{ codec_type: 'video', width: 200, height: 100 }],
      };

      sandbox.stub(ffmpeg, 'ffprobe').callsFake((path, callback) => {
        callback(null, mockMetadata);
      });

      await expect(
        stickerService.createStaticStickerFromGif(gifPath)
      ).rejects.toThrow('文件不是动画GIF');
    });
  });

  describe('getImageInfo', () => {
    test('should get image info successfully', async () => {
      const mockMetadata = {
        format: { duration: '5.0', format_name: 'gif', size: 102400 },
        streams: [
          { codec_type: 'video', width: 300, height: 200 },
        ],
      };

      sandbox.stub(ffmpeg, 'ffprobe').callsFake((path, callback) => {
        callback(null, mockMetadata);
      });

      const imagePath = path.join(tempDir, 'test.gif');
      fs.writeFileSync(imagePath, 'fake image content');

      const result = await stickerService.getImageInfo(imagePath);

      expect(result.width).toBe(300);
      expect(result.height).toBe(200);
      expect(result.duration).toBe(5.0);
      expect(result.isAnimated).toBe(true);
      expect(result.format).toBe('gif');
    });

    test('should handle static images (no duration)', async () => {
      const mockMetadata = {
        format: { duration: null, format_name: 'png' },
        streams: [
          { codec_type: 'video', width: 200, height: 100 },
        ],
      };

      sandbox.stub(ffmpeg, 'ffprobe').callsFake((path, callback) => {
        callback(null, mockMetadata);
      });

      const imagePath = path.join(tempDir, 'test.png');
      fs.writeFileSync(imagePath, 'fake image content');

      const result = await stickerService.getImageInfo(imagePath);

      expect(result.duration).toBeNull();
      expect(result.isAnimated).toBe(false);
    });

    test('should handle ffprobe errors', async () => {
      sandbox.stub(ffmpeg, 'ffprobe').callsFake((path, callback) => {
        callback(new Error('ffprobe failed'));
      });

      const imagePath = path.join(tempDir, 'test.png');
      fs.writeFileSync(imagePath, 'fake image content');

      await expect(
        stickerService.getImageInfo(imagePath)
      ).rejects.toThrow('无法获取图片信息');
    });
  });

  describe('GIF loop count calculation logic', () => {
    test('should correctly identify animated GIFs via getImageInfo', async () => {
      const gifDuration = 3.5;
      const mockMetadata = {
        format: { duration: gifDuration.toString(), format_name: 'gif' },
        streams: [{ codec_type: 'video', width: 200, height: 150 }],
      };

      sandbox.stub(ffmpeg, 'ffprobe').callsFake((path, callback) => {
        callback(null, mockMetadata);
      });

      const gifPath = path.join(tempDir, 'animation.gif');
      fs.writeFileSync(gifPath, 'fake gif content');

      const result = await stickerService.getImageInfo(gifPath);

      expect(result.isAnimated).toBe(true);
      expect(result.duration).toBe(gifDuration);
    });

    test('should correctly identify static images via getImageInfo', async () => {
      const mockMetadata = {
        format: { duration: null, format_name: 'png' },
        streams: [{ codec_type: 'video', width: 200, height: 150 }],
      };

      sandbox.stub(ffmpeg, 'ffprobe').callsFake((path, callback) => {
        callback(null, mockMetadata);
      });

      const imagePath = path.join(tempDir, 'static.png');
      fs.writeFileSync(imagePath, 'fake image content');

      const result = await stickerService.getImageInfo(imagePath);

      expect(result.isAnimated).toBe(false);
      expect(result.duration).toBeNull();
    });

    test('validateStickerFile should correctly identify GIF type', async () => {
      const mockMetadata = {
        format: { duration: '4.0', format_name: 'gif' },
        streams: [{ codec_type: 'video', width: 200, height: 150 }],
      };

      sandbox.stub(ffmpeg, 'ffprobe').callsFake((path, callback) => {
        callback(null, mockMetadata);
      });

      const gifPath = path.join(tempDir, 'animation.gif');
      fs.writeFileSync(gifPath, 'fake gif content');

      const result = await stickerService.validateStickerFile(gifPath);

      expect(result.valid).toBe(true);
      expect(result.type).toBe('gif');
      expect(result.isAnimated).toBe(true);
    });

    test('validateStickerFile should correctly identify static image type', async () => {
      const mockMetadata = {
        format: { duration: null, format_name: 'png' },
        streams: [{ codec_type: 'video', width: 200, height: 150 }],
      };

      sandbox.stub(ffmpeg, 'ffprobe').callsFake((path, callback) => {
        callback(null, mockMetadata);
      });

      const imagePath = path.join(tempDir, 'static.png');
      fs.writeFileSync(imagePath, 'fake image content');

      const result = await stickerService.validateStickerFile(imagePath);

      expect(result.valid).toBe(true);
      expect(result.type).toBe('static');
      expect(result.isAnimated).toBe(false);
    });
  });
});
