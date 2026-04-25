import helpers from '../../src/utils/helpers.js';
import testHelpers from '../testHelpers.js';
import fs from 'fs-extra';
import path from 'path';

describe('helpers', () => {
  describe('ensureDirectory', () => {
    let tempDir;

    beforeEach(() => {
      tempDir = testHelpers.createTempDir();
    });

    afterEach(() => {
      testHelpers.cleanupTempDir(tempDir);
    });

    test('should create directory if it does not exist', () => {
      const newDir = path.join(tempDir, 'new-subdir');
      expect(fs.existsSync(newDir)).toBe(false);
      
      const result = helpers.ensureDirectory(newDir);
      
      expect(fs.existsSync(newDir)).toBe(true);
      expect(result).toBe(newDir);
    });

    test('should return directory path if it already exists', () => {
      const existingDir = path.join(tempDir, 'existing');
      fs.mkdirSync(existingDir);
      
      const result = helpers.ensureDirectory(existingDir);
      
      expect(result).toBe(existingDir);
    });

    test('should create nested directories', () => {
      const nestedDir = path.join(tempDir, 'level1', 'level2', 'level3');
      
      helpers.ensureDirectory(nestedDir);
      
      expect(fs.existsSync(nestedDir)).toBe(true);
    });
  });

  describe('generateUniqueId', () => {
    test('should generate unique IDs', () => {
      const id1 = helpers.generateUniqueId();
      const id2 = helpers.generateUniqueId();
      
      expect(id1).not.toBe(id2);
    });

    test('should generate IDs with timestamp and random part', () => {
      const id = helpers.generateUniqueId();
      
      expect(typeof id).toBe('string');
      expect(id).toMatch(/^\d+-\w+$/);
    });
  });

  describe('formatTimestamp', () => {
    test('should format seconds to SRT timestamp format', () => {
      expect(helpers.formatTimestamp(0)).toBe('00:00:00,000');
      expect(helpers.formatTimestamp(1.5)).toBe('00:00:01,500');
      expect(helpers.formatTimestamp(65.123)).toBe('00:01:05,123');
      expect(helpers.formatTimestamp(3661.999)).toBe('01:01:01,999');
    });

    test('should handle large durations', () => {
      expect(helpers.formatTimestamp(3600 * 25)).toBe('25:00:00,000');
    });
  });

  describe('parseTimestamp', () => {
    test('should parse SRT timestamp to seconds', () => {
      expect(helpers.parseTimestamp('00:00:00,000')).toBe(0);
      expect(helpers.parseTimestamp('00:00:01,500')).toBe(1.5);
      expect(helpers.parseTimestamp('00:01:05,123')).toBe(65.123);
      expect(helpers.parseTimestamp('01:01:01,999')).toBe(3661.999);
    });

    test('should return 0 for invalid timestamp', () => {
      expect(helpers.parseTimestamp('invalid')).toBe(0);
      expect(helpers.parseTimestamp('')).toBe(0);
    });
  });

  describe('getFileExtension', () => {
    test('should get file extension', () => {
      expect(helpers.getFileExtension('video.mp4')).toBe('.mp4');
      expect(helpers.getFileExtension('audio.MP3')).toBe('.mp3');
      expect(helpers.getFileExtension('subtitle.SRT')).toBe('.srt');
      expect(helpers.getFileExtension('document.pdf')).toBe('.pdf');
    });

    test('should handle files with no extension', () => {
      expect(helpers.getFileExtension('README')).toBe('');
    });

    test('should handle hidden files', () => {
      expect(helpers.getFileExtension('.gitignore')).toBe('');
      expect(helpers.getFileExtension('.bashrc')).toBe('');
    });

    test('should handle files with multiple dots', () => {
      expect(helpers.getFileExtension('archive.tar.gz')).toBe('.gz');
      expect(helpers.getFileExtension('video.part1.mp4')).toBe('.mp4');
    });
  });

  describe('getFileNameWithoutExtension', () => {
    test('should get filename without extension', () => {
      expect(helpers.getFileNameWithoutExtension('video.mp4')).toBe('video');
      expect(helpers.getFileNameWithoutExtension('audio.mp3')).toBe('audio');
      expect(helpers.getFileNameWithoutExtension('/path/to/subtitle.srt')).toBe('subtitle');
    });

    test('should handle files with no extension', () => {
      expect(helpers.getFileNameWithoutExtension('README')).toBe('README');
    });

    test('should handle files with multiple dots', () => {
      expect(helpers.getFileNameWithoutExtension('archive.tar.gz')).toBe('archive.tar');
    });
  });

  describe('sanitizeFilename', () => {
    test('should sanitize invalid characters', () => {
      expect(helpers.sanitizeFilename('video:file.mp4')).toBe('video_file.mp4');
      expect(helpers.sanitizeFilename('file/with/slashes')).toBe('file_with_slashes');
      expect(helpers.sanitizeFilename('file<with>special:chars')).toBe('file_with_special_chars');
    });

    test('should replace spaces with underscores', () => {
      expect(helpers.sanitizeFilename('my video file.mp4')).toBe('my_video_file.mp4');
    });

    test('should convert to lowercase', () => {
      expect(helpers.sanitizeFilename('VIDEO.MP4')).toBe('video.mp4');
    });
  });

  describe('calculateVideoSegments', () => {
    test('should calculate segments for exact duration', () => {
      const segments = helpers.calculateVideoSegments(120, 30);
      
      expect(segments.length).toBe(4);
      expect(segments[0]).toEqual({
        index: 0,
        startTime: 0,
        endTime: 30,
        duration: 30,
      });
      expect(segments[3]).toEqual({
        index: 3,
        startTime: 90,
        endTime: 120,
        duration: 30,
      });
    });

    test('should handle duration that is not exact multiple', () => {
      const segments = helpers.calculateVideoSegments(100, 30);
      
      expect(segments.length).toBe(4);
      expect(segments[0].duration).toBe(30);
      expect(segments[1].duration).toBe(30);
      expect(segments[2].duration).toBe(30);
      expect(segments[3].duration).toBe(10);
    });

    test('should handle zero duration', () => {
      const segments = helpers.calculateVideoSegments(0, 30);
      expect(segments.length).toBe(0);
    });
  });

  describe('formatDuration', () => {
    test('should format duration with minutes and seconds', () => {
      expect(helpers.formatDuration(65)).toBe('1:05');
      expect(helpers.formatDuration(120)).toBe('2:00');
      expect(helpers.formatDuration(59)).toBe('0:59');
    });

    test('should format duration with hours', () => {
      expect(helpers.formatDuration(3661)).toBe('1:01:01');
      expect(helpers.formatDuration(7200)).toBe('2:00:00');
    });

    test('should handle zero duration', () => {
      expect(helpers.formatDuration(0)).toBe('0:00');
    });
  });

  describe('sleep', () => {
    test('should sleep for specified milliseconds', async () => {
      const startTime = Date.now();
      await helpers.sleep(100);
      const endTime = Date.now();
      
      expect(endTime - startTime).toBeGreaterThanOrEqual(100);
    });
  });
});