import ffmpeg from 'fluent-ffmpeg';
import path from 'path';
import fs from 'fs-extra';
import config from '../config/index.js';
import helpers from '../utils/helpers.js';

ffmpeg.setFfmpegPath(config.ffmpeg.path);
ffmpeg.setFfprobePath(config.ffmpeg.ffprobePath);

class VideoSplitter {
  constructor(options = {}) {
    this.options = {
      segmentDuration: options.segmentDuration || config.video.defaultSegmentDuration,
      outputDir: options.outputDir || config.directories.temp,
      ...options,
    };
  }

  async getVideoInfo(videoPath) {
    return new Promise((resolve, reject) => {
      ffmpeg.ffprobe(videoPath, (err, metadata) => {
        if (err) {
          reject(new Error(`无法获取视频信息: ${err.message}`));
          return;
        }

        const videoStream = metadata.streams.find(s => s.codec_type === 'video');
        const audioStream = metadata.streams.find(s => s.codec_type === 'audio');

        resolve({
          duration: parseFloat(metadata.format.duration),
          size: metadata.format.size,
          bitrate: metadata.format.bit_rate,
          video: {
            codec: videoStream?.codec_name,
            width: videoStream?.width,
            height: videoStream?.height,
            fps: videoStream?.avg_frame_rate ? eval(videoStream.avg_frame_rate) : config.video.defaultFps,
          },
          audio: audioStream ? {
            codec: audioStream.codec_name,
            sampleRate: audioStream.sample_rate,
            channels: audioStream.channels,
          } : null,
        });
      });
    });
  }

  async splitVideo(videoPath, options = {}) {
    const videoInfo = await this.getVideoInfo(videoPath);
    const segmentDuration = options.segmentDuration || this.options.segmentDuration;
    const outputDir = options.outputDir || this.options.outputDir;
    const baseName = helpers.getFileNameWithoutExtension(videoPath);

    helpers.ensureDirectory(outputDir);

    const segments = helpers.calculateVideoSegments(videoInfo.duration, segmentDuration);
    const outputFiles = [];

    for (const segment of segments) {
      const outputFileName = `${baseName}_segment_${String(segment.index).padStart(3, '0')}.mp4`;
      const outputPath = path.join(outputDir, outputFileName);

      await this._extractSegment(videoPath, outputPath, segment.startTime, segment.duration);

      outputFiles.push({
        ...segment,
        path: outputPath,
        filename: outputFileName,
      });
    }

    return {
      originalVideo: videoPath,
      originalInfo: videoInfo,
      segments: outputFiles,
      segmentCount: outputFiles.length,
    };
  }

  _extractSegment(inputPath, outputPath, startTime, duration) {
    return new Promise((resolve, reject) => {
      const command = ffmpeg(inputPath)
        .setStartTime(startTime)
        .setDuration(duration)
        .output(outputPath)
        .outputOptions([
          '-c:v', 'copy',
          '-c:a', 'copy',
          '-avoid_negative_ts', 'make_zero',
        ]);

      command
        .on('end', () => {
          resolve(outputPath);
        })
        .on('error', (err) => {
          reject(new Error(`视频分割失败: ${err.message}`));
        })
        .run();
    });
  }

  async splitByCustomIntervals(videoPath, intervals, outputDir = null) {
    const videoInfo = await this.getVideoInfo(videoPath);
    const outputDirectory = outputDir || this.options.outputDir;
    const baseName = helpers.getFileNameWithoutExtension(videoPath);

    helpers.ensureDirectory(outputDirectory);

    const outputFiles = [];

    for (let i = 0; i < intervals.length; i++) {
      const interval = intervals[i];
      const startTime = interval.startTime;
      const duration = interval.endTime - interval.startTime;

      const outputFileName = `${baseName}_segment_${String(i).padStart(3, '0')}.mp4`;
      const outputPath = path.join(outputDirectory, outputFileName);

      if (startTime < 0 || startTime + duration > videoInfo.duration) {
        throw new Error(`时间区间超出视频范围: 开始 ${startTime}, 时长 ${duration}, 视频总长 ${videoInfo.duration}`);
      }

      await this._extractSegment(videoPath, outputPath, startTime, duration);

      outputFiles.push({
        index: i,
        startTime,
        endTime: interval.endTime,
        duration,
        path: outputPath,
        filename: outputFileName,
      });
    }

    return {
      originalVideo: videoPath,
      originalInfo: videoInfo,
      segments: outputFiles,
      segmentCount: outputFiles.length,
    };
  }

  async mergeVideos(videoPaths, outputPath, options = {}) {
    return new Promise((resolve, reject) => {
      if (videoPaths.length === 0) {
        reject(new Error('没有提供要合并的视频文件'));
        return;
      }

      const concatFile = this._createConcatFile(videoPaths);

      const command = ffmpeg()
        .input(concatFile)
        .inputOptions(['-f', 'concat', '-safe', '0'])
        .output(outputPath)
        .outputOptions([
          '-c:v', 'copy',
          '-c:a', 'copy',
        ]);

      if (options.videoCodec && options.videoCodec !== 'copy') {
        command.outputOptions('-c:v', options.videoCodec);
      }
      if (options.audioCodec && options.audioCodec !== 'copy') {
        command.outputOptions('-c:a', options.audioCodec);
      }

      command
        .on('end', () => {
          fs.unlinkSync(concatFile);
          resolve(outputPath);
        })
        .on('error', (err) => {
          if (fs.existsSync(concatFile)) {
            fs.unlinkSync(concatFile);
          }
          reject(new Error(`视频合并失败: ${err.message}`));
        })
        .run();
    });
  }

  _createConcatFile(videoPaths) {
    const tempDir = config.directories.temp;
    helpers.ensureDirectory(tempDir);

    const concatFilePath = path.join(tempDir, `concat_${helpers.generateUniqueId()}.txt`);
    const content = videoPaths.map(p => `file '${p.replace(/'/g, "'\\''")}'`).join('\n');

    fs.writeFileSync(concatFilePath, content, 'utf-8');
    return concatFilePath;
  }

  async getAudioVolume(videoPath) {
    return new Promise((resolve, reject) => {
      const command = ffmpeg(videoPath)
        .outputOptions([
          '-af', 'volumedetect',
          '-f', 'null',
          '-vn',
        ])
        .output('-');

      let stderrOutput = '';

      command
        .on('stderr', (stderrLine) => {
          stderrOutput += stderrLine + '\n';
        })
        .on('end', () => {
          const meanVolumeMatch = stderrOutput.match(/mean_volume:\s*(-?[\d.]+)/);
          const maxVolumeMatch = stderrOutput.match(/max_volume:\s*(-?[\d.]+)/);
          
          const meanVolume = meanVolumeMatch ? parseFloat(meanVolumeMatch[1]) : null;
          const maxVolume = maxVolumeMatch ? parseFloat(maxVolumeMatch[1]) : null;

          resolve({
            meanVolume,
            maxVolume,
            hasAudio: meanVolume !== null,
          });
        })
        .on('error', (err) => {
          reject(new Error(`检测音频音量失败: ${err.message}`));
        })
        .run();
    });
  }
}

export default VideoSplitter;