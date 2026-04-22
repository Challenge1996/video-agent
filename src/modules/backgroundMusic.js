import ffmpeg from 'fluent-ffmpeg';
import path from 'path';
import fs from 'fs-extra';
import config from '../config/index.js';
import helpers from '../utils/helpers.js';

ffmpeg.setFfmpegPath(config.ffmpeg.path);
ffmpeg.setFfprobePath(config.ffmpeg.ffprobePath);

class BackgroundMusicService {
  constructor(options = {}) {
    this.options = {
      outputDir: options.outputDir || config.directories.temp,
      defaultVolume: options.defaultVolume || config.audio.backgroundMusicVolume,
      duckingAmount: options.duckingAmount || config.audio.duckingAmount,
      fadeDuration: options.fadeDuration || config.audio.fadeDuration,
      ...options,
    };
  }

  async getAudioInfo(audioPath) {
    return new Promise((resolve, reject) => {
      ffmpeg.ffprobe(audioPath, (err, metadata) => {
        if (err) {
          reject(new Error(`无法获取音频信息: ${err.message}`));
          return;
        }

        const audioStream = metadata.streams.find(s => s.codec_type === 'audio');

        resolve({
          duration: parseFloat(metadata.format.duration),
          size: metadata.format.size,
          bitrate: metadata.format.bit_rate,
          audio: audioStream ? {
            codec: audioStream.codec_name,
            sampleRate: audioStream.sample_rate,
            channels: audioStream.channels,
          } : null,
        });
      });
    });
  }

  async loopAudioToDuration(audioPath, targetDuration, options = {}) {
    const audioInfo = await this.getAudioInfo(audioPath);
    const outputDir = options.outputDir || this.options.outputDir;
    const outputFileName = options.outputFileName || `bgm_looped_${helpers.generateUniqueId()}.mp3`;
    const outputPath = path.join(outputDir, outputFileName);
    const volume = options.volume ?? this.options.defaultVolume;
    const fadeIn = options.fadeIn ?? this.options.fadeDuration;
    const fadeOut = options.fadeOut ?? this.options.fadeDuration;

    helpers.ensureDirectory(outputDir);

    return new Promise((resolve, reject) => {
      let command = ffmpeg();

      if (audioInfo.duration < targetDuration) {
        const loopCount = Math.ceil(targetDuration / audioInfo.duration);
        for (let i = 0; i < loopCount; i++) {
          command = command.input(audioPath);
        }

        const filterComplex = [];
        for (let i = 0; i < loopCount; i++) {
          filterComplex.push(`[${i}:a]`);
        }
        filterComplex.push(`concat=n=${loopCount}:v=0:a=1[concatenated]`);

        const volumeFilter = `[concatenated]volume=${volume}[volumed]`;
        filterComplex.push(volumeFilter);

        const trimFilter = `[volumed]atrim=0:${targetDuration}[trimmed]`;
        filterComplex.push(trimFilter);

        const fadeFilters = [];
        if (fadeIn > 0) {
          fadeFilters.push(`afade=t=in:ss=0:d=${fadeIn}`);
        }
        if (fadeOut > 0) {
          fadeFilters.push(`afade=t=out:st=${targetDuration - fadeOut}:d=${fadeOut}`);
        }

        if (fadeFilters.length > 0) {
          filterComplex.push(`[trimmed]${fadeFilters.join(',')}[final]`);
          command = command.complexFilter(filterComplex, 'final');
        } else {
          command = command.complexFilter(filterComplex, 'trimmed');
        }
      } else {
        command = command.input(audioPath);

        const filterComplex = [];
        filterComplex.push(`[0:a]volume=${volume},atrim=0:${targetDuration}[trimmed]`);

        const fadeFilters = [];
        if (fadeIn > 0) {
          fadeFilters.push(`afade=t=in:ss=0:d=${fadeIn}`);
        }
        if (fadeOut > 0) {
          fadeFilters.push(`afade=t=out:st=${targetDuration - fadeOut}:d=${fadeOut}`);
        }

        if (fadeFilters.length > 0) {
          filterComplex.push(`[trimmed]${fadeFilters.join(',')}[final]`);
          command = command.complexFilter(filterComplex, 'final');
        } else {
          command = command.complexFilter(filterComplex, 'trimmed');
        }
      }

      command = command.output(outputPath)
        .outputOptions([
          '-c:a', 'libmp3lame',
          '-q:a', '2',
        ]);

      command
        .on('end', () => {
          resolve({
            success: true,
            originalPath: audioPath,
            outputPath: outputPath,
            filename: outputFileName,
            targetDuration: targetDuration,
            actualDuration: targetDuration,
            volume: volume,
          });
        })
        .on('error', (err) => {
          reject(new Error(`音频循环处理失败: ${err.message}`));
        })
        .run();
    });
  }

  async applyDucking(backgroundAudioPath, voiceSegments, options = {}) {
    const bgmInfo = await this.getAudioInfo(backgroundAudioPath);
    const outputDir = options.outputDir || this.options.outputDir;
    const outputFileName = options.outputFileName || `bgm_ducked_${helpers.generateUniqueId()}.mp3`;
    const outputPath = path.join(outputDir, outputFileName);
    const duckingAmount = options.duckingAmount ?? this.options.duckingAmount;
    const fadeDuration = options.fadeDuration ?? 0.5;

    helpers.ensureDirectory(outputDir);

    return new Promise((resolve, reject) => {
      if (voiceSegments.length === 0) {
        fs.copyFileSync(backgroundAudioPath, outputPath);
        resolve({
          success: true,
          originalPath: backgroundAudioPath,
          outputPath: outputPath,
          filename: outputFileName,
          duckingApplied: false,
          reason: '没有语音片段需要闪避',
        });
        return;
      }

      const filterComplex = [];
      let currentStream = '0:a';

      for (let i = 0; i < voiceSegments.length; i++) {
        const segment = voiceSegments[i];
        const startTime = segment.startTime;
        const endTime = segment.endTime;
        const duration = endTime - startTime;

        const duckStartTime = Math.max(0, startTime - fadeDuration);
        const duckEndTime = endTime + fadeDuration;
        const duckDuration = duckEndTime - duckStartTime;

        const filterName = `duck_${i}`;
        const volumeExpression = this._createDuckingVolumeExpression(
          startTime,
          endTime,
          duckingAmount,
          fadeDuration
        );

        filterComplex.push(`[${currentStream}]volume=${volumeExpression}[${filterName}]`);
        currentStream = filterName;
      }

      const command = ffmpeg(backgroundAudioPath)
        .complexFilter(filterComplex, currentStream)
        .output(outputPath)
        .outputOptions([
          '-c:a', 'libmp3lame',
          '-q:a', '2',
        ]);

      command
        .on('end', () => {
          resolve({
            success: true,
            originalPath: backgroundAudioPath,
            outputPath: outputPath,
            filename: outputFileName,
            duckingApplied: true,
            duckedSegments: voiceSegments.length,
            duckingAmount: duckingAmount,
          });
        })
        .on('error', (err) => {
          reject(new Error(`闪避效果处理失败: ${err.message}`));
        })
        .run();
    });
  }

  _createDuckingVolumeExpression(startTime, endTime, duckingAmount, fadeDuration) {
    const fadeInStart = startTime - fadeDuration;
    const fadeInEnd = startTime;
    const fadeOutStart = endTime;
    const fadeOutEnd = endTime + fadeDuration;

    const volumeReduction = 1 - duckingAmount;

    const fadeInExpr = fadeInStart >= 0 
      ? `(1-${volumeReduction})*(t-${fadeInStart})/${fadeDuration}+${volumeReduction}`
      : `(1-${volumeReduction})*(t+${Math.abs(fadeInStart)})/${fadeDuration}+${volumeReduction}`;

    const fadeOutExpr = `(1-${volumeReduction})*(${fadeOutEnd}-t)/${fadeDuration}+${volumeReduction}`;

    return `if(between(t,${fadeInStart},${fadeInEnd}),` +
           `${fadeInExpr},` +
           `if(between(t,${fadeInEnd},${fadeOutStart}),` +
           `${volumeReduction},` +
           `if(between(t,${fadeOutStart},${fadeOutEnd}),` +
           `${fadeOutExpr},` +
           `1)))`;
  }

  async mergeAudioTracks(audioTracks, outputPath, options = {}) {
    if (audioTracks.length === 0) {
      throw new Error('没有提供要合并的音频轨道');
    }

    const outputDir = path.dirname(outputPath) || this.options.outputDir;
    helpers.ensureDirectory(outputDir);

    return new Promise((resolve, reject) => {
      let command = ffmpeg();

      for (const track of audioTracks) {
        command = command.input(track.path);
      }

      const filterComplex = [];
      const amixInputs = [];

      for (let i = 0; i < audioTracks.length; i++) {
        const track = audioTracks[i];
        const volume = track.volume ?? 1.0;
        const delay = track.delay ?? 0;

        if (volume !== 1.0 || delay > 0) {
          const filters = [];
          if (volume !== 1.0) {
            filters.push(`volume=${volume}`);
          }
          if (delay > 0) {
            filters.push(`adelay=${delay * 1000}|${delay * 1000}`);
          }

          const filterName = `track_${i}`;
          filterComplex.push(`[${i}:a]${filters.join(',')}[${filterName}]`);
          amixInputs.push(`[${filterName}]`);
        } else {
          amixInputs.push(`[${i}:a]`);
        }
      }

      const mixFilter = `${amixInputs.join('')}amix=inputs=${audioTracks.length}:duration=longest[out]`;
      filterComplex.push(mixFilter);

      command = command.complexFilter(filterComplex, 'out')
        .output(outputPath)
        .outputOptions([
          '-c:a', 'libmp3lame',
          '-q:a', '2',
        ]);

      command
        .on('end', () => {
          resolve({
            success: true,
            outputPath: outputPath,
            tracksMerged: audioTracks.length,
          });
        })
        .on('error', (err) => {
          reject(new Error(`音频合并失败: ${err.message}`));
        })
        .run();
    });
  }

  async adjustVolume(audioPath, volume, options = {}) {
    const outputDir = options.outputDir || this.options.outputDir;
    const outputFileName = options.outputFileName || `audio_vol_${helpers.generateUniqueId()}.mp3`;
    const outputPath = path.join(outputDir, outputFileName);

    helpers.ensureDirectory(outputDir);

    return new Promise((resolve, reject) => {
      const command = ffmpeg(audioPath)
        .audioFilter(`volume=${volume}`)
        .output(outputPath)
        .outputOptions([
          '-c:a', 'libmp3lame',
          '-q:a', '2',
        ]);

      command
        .on('end', () => {
          resolve({
            success: true,
            originalPath: audioPath,
            outputPath: outputPath,
            filename: outputFileName,
            volume: volume,
          });
        })
        .on('error', (err) => {
          reject(new Error(`音量调整失败: ${err.message}`));
        })
        .run();
    });
  }

  async addFadeEffects(audioPath, options = {}) {
    const audioInfo = await this.getAudioInfo(audioPath);
    const outputDir = options.outputDir || this.options.outputDir;
    const outputFileName = options.outputFileName || `audio_fade_${helpers.generateUniqueId()}.mp3`;
    const outputPath = path.join(outputDir, outputFileName);
    const fadeIn = options.fadeIn ?? this.options.fadeDuration;
    const fadeOut = options.fadeOut ?? this.options.fadeDuration;

    helpers.ensureDirectory(outputDir);

    return new Promise((resolve, reject) => {
      const filters = [];

      if (fadeIn > 0) {
        filters.push(`afade=t=in:ss=0:d=${fadeIn}`);
      }

      if (fadeOut > 0) {
        const fadeOutStart = audioInfo.duration - fadeOut;
        if (fadeOutStart > 0) {
          filters.push(`afade=t=out:st=${fadeOutStart}:d=${fadeOut}`);
        }
      }

      if (filters.length === 0) {
        fs.copyFileSync(audioPath, outputPath);
        resolve({
          success: true,
          originalPath: audioPath,
          outputPath: outputPath,
          filename: outputFileName,
          fadeApplied: false,
          reason: '没有指定淡入淡出效果',
        });
        return;
      }

      const command = ffmpeg(audioPath)
        .audioFilter(filters.join(','))
        .output(outputPath)
        .outputOptions([
          '-c:a', 'libmp3lame',
          '-q:a', '2',
        ]);

      command
        .on('end', () => {
          resolve({
            success: true,
            originalPath: audioPath,
            outputPath: outputPath,
            filename: outputFileName,
            fadeIn: fadeIn,
            fadeOut: fadeOut,
          });
        })
        .on('error', (err) => {
          reject(new Error(`淡入淡出效果处理失败: ${err.message}`));
        })
        .run();
    });
  }
}

export default BackgroundMusicService;