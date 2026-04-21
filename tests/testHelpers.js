import tmp from 'tmp';
import fs from 'fs-extra';
import path from 'path';

export function createTempDir() {
  return tmp.dirSync({ unsafeCleanup: true }).name;
}

export function createTempFile(content = '', extension = '.txt') {
  const tmpObj = tmp.fileSync({ postfix: extension });
  if (content) {
    fs.writeFileSync(tmpObj.name, content);
  }
  return tmpObj.name;
}

export function cleanupTempDir(dirPath) {
  if (dirPath && fs.existsSync(dirPath)) {
    fs.removeSync(dirPath);
  }
}

export function mockFfmpegCommand(sinon, mockResponses = {}) {
  const mockCommand = {
    input: sinon.stub().returnsThis(),
    setStartTime: sinon.stub().returnsThis(),
    setDuration: sinon.stub().returnsThis(),
    output: sinon.stub().returnsThis(),
    outputOptions: sinon.stub().returnsThis(),
    videoFilter: sinon.stub().returnsThis(),
    audioFilter: sinon.stub().returnsThis(),
    complexFilter: sinon.stub().returnsThis(),
    on: sinon.stub().returnsThis(),
    run: sinon.stub().callsFake(() => {
      if (mockResponses.error) {
        const errorCallbacks = mockCommand.on.getCalls().filter(c => c.args[0] === 'error');
        errorCallbacks.forEach(call => call.args[1](mockResponses.error));
      } else {
        const endCallbacks = mockCommand.on.getCalls().filter(c => c.args[0] === 'end');
        endCallbacks.forEach(call => call.args[1]());
      }
    }),
  };
  return mockCommand;
}

export function mockFfprobe(sinon, mockMetadata = {}) {
  return sinon.stub().callsFake((path, callback) => {
    if (mockMetadata.error) {
      callback(mockMetadata.error);
    } else {
      callback(null, mockMetadata);
    }
  });
}

export function createMockVideoMetadata(overrides = {}) {
  return {
    format: {
      duration: '120.5',
      size: 104857600,
      bit_rate: 5000000,
      ...overrides.format,
    },
    streams: [
      {
        codec_type: 'video',
        codec_name: 'h264',
        width: 1920,
        height: 1080,
        avg_frame_rate: '30/1',
        ...overrides.videoStream,
      },
      {
        codec_type: 'audio',
        codec_name: 'aac',
        sample_rate: 48000,
        channels: 2,
        ...overrides.audioStream,
      },
    ],
    ...overrides,
  };
}

export function createMockAudioMetadata(overrides = {}) {
  return {
    format: {
      duration: '60.0',
      size: 5242880,
      bit_rate: 128000,
      ...overrides.format,
    },
    streams: [
      {
        codec_type: 'audio',
        codec_name: 'mp3',
        sample_rate: 44100,
        channels: 2,
        ...overrides.audioStream,
      },
    ],
    ...overrides,
  };
}

export function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export default {
  createTempDir,
  createTempFile,
  cleanupTempDir,
  mockFfmpegCommand,
  mockFfprobe,
  createMockVideoMetadata,
  createMockAudioMetadata,
  sleep,
};