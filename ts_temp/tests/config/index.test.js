import config from '../../src/config/index.js';

describe('config', () => {
  describe('module structure', () => {
    test('should export config object', () => {
      expect(typeof config).toBe('object');
      expect(config).not.toBeNull();
    });

    test('should have google configuration', () => {
      expect(typeof config.google).toBe('object');
      expect(typeof config.google.credentials).toBe('string');
      expect(typeof config.google.tts).toBe('object');
    });

    test('should have tts configuration', () => {
      expect(typeof config.google.tts.languageCode).toBe('string');
      expect(typeof config.google.tts.voiceName).toBe('string');
      expect(typeof config.google.tts.speakingRate).toBe('number');
      expect(typeof config.google.tts.pitch).toBe('number');
    });

    test('should have ffmpeg configuration', () => {
      expect(typeof config.ffmpeg).toBe('object');
      expect(typeof config.ffmpeg.path).toBe('string');
      expect(typeof config.ffmpeg.ffprobePath).toBe('string');
    });

    test('should have directories configuration', () => {
      expect(typeof config.directories).toBe('object');
      expect(typeof config.directories.output).toBe('string');
      expect(typeof config.directories.temp).toBe('string');
    });

    test('should have video configuration', () => {
      expect(typeof config.video).toBe('object');
      expect(typeof config.video.defaultSegmentDuration).toBe('number');
      expect(typeof config.video.defaultResolution).toBe('string');
      expect(typeof config.video.defaultFps).toBe('number');
    });

    test('should have audio configuration', () => {
      expect(typeof config.audio).toBe('object');
      expect(typeof config.audio.backgroundMusicVolume).toBe('number');
      expect(typeof config.audio.ttsVolume).toBe('number');
      expect(typeof config.audio.duckingAmount).toBe('number');
      expect(typeof config.audio.fadeDuration).toBe('number');
    });

    test('should have subtitle configuration', () => {
      expect(typeof config.subtitle).toBe('object');
      expect(typeof config.subtitle.fontSize).toBe('number');
      expect(typeof config.subtitle.fontColor).toBe('string');
      expect(typeof config.subtitle.backgroundColor).toBe('string');
      expect(typeof config.subtitle.position).toBe('string');
      expect(typeof config.subtitle.marginV).toBe('number');
    });
  });

  describe('default values', () => {
    test('should have reasonable default values', () => {
      expect(config.video.defaultSegmentDuration).toBeGreaterThan(0);
      expect(config.video.defaultFps).toBeGreaterThan(0);
      expect(config.audio.backgroundMusicVolume).toBeGreaterThanOrEqual(0);
      expect(config.audio.backgroundMusicVolume).toBeLessThanOrEqual(1);
      expect(config.audio.ttsVolume).toBeGreaterThanOrEqual(0);
      expect(config.audio.ttsVolume).toBeLessThanOrEqual(2);
      expect(config.subtitle.fontSize).toBeGreaterThan(0);
    });

    test('should have valid default language', () => {
      expect(config.google.tts.languageCode).toMatch(/^[a-z]{2}-[A-Z]{2}$/);
    });

    test('should have valid default resolution', () => {
      expect(config.video.defaultResolution).toMatch(/^\d+x\d+$/);
    });
  });
});