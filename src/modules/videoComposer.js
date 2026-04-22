import ffmpeg from 'fluent-ffmpeg';
import path from 'path';
import fs from 'fs-extra';
import config from '../config/index.js';
import helpers from '../utils/helpers.js';
import VideoSplitter from './videoSplitter.js';
import GoogleTTSService from './ttsService.js';
import MiniMaxTTSService from './miniMaxTTSService.js';
import SubtitleGenerator from './subtitleGenerator.js';
import BackgroundMusicService from './backgroundMusic.js';
import StickerService from './stickerService.js';

ffmpeg.setFfmpegPath(config.ffmpeg.path);
ffmpeg.setFfprobePath(config.ffmpeg.ffprobePath);

class VideoComposer {
  constructor(options = {}) {
    this.options = {
      outputDir: options.outputDir || config.directories.output,
      tempDir: options.tempDir || config.directories.temp,
      ttsProvider: options.ttsProvider || config.tts.provider,
      ...options,
    };

    this.videoSplitter = new VideoSplitter({
      outputDir: this.options.tempDir,
      ...options.videoSplitterOptions,
    });

    this.ttsService = this._createTTSService(options);

    this.subtitleGenerator = new SubtitleGenerator({
      outputDir: this.options.tempDir,
      ...options.subtitleOptions,
    });

    this.backgroundMusicService = new BackgroundMusicService({
      outputDir: this.options.tempDir,
      ...options.backgroundMusicOptions,
    });

    this.stickerService = new StickerService({
      outputDir: this.options.tempDir,
      ...options.stickerOptions,
    });

    helpers.ensureDirectory(this.options.outputDir);
    helpers.ensureDirectory(this.options.tempDir);
  }

  _createTTSService(options = {}) {
    const provider = options.ttsProvider || config.tts.provider;
    
    if (provider === 'minimax') {
      return new MiniMaxTTSService({
        outputDir: this.options.tempDir,
        ...options.ttsOptions,
      });
    } else if (provider === 'google') {
      return new GoogleTTSService({
        outputDir: this.options.tempDir,
        ...options.ttsOptions,
      });
    } else {
      console.warn(`未知的 TTS 提供商: ${provider}，默认使用 MiniMax`);
      return new MiniMaxTTSService({
        outputDir: this.options.tempDir,
        ...options.ttsOptions,
      });
    }
  }

  async composeVideo(options) {
    const {
      videoPath,
      textContent,
      backgroundMusicPath,
      segmentDuration,
      outputFileName,
      addSubtitles = true,
      addBackgroundMusic = true,
      addTTS = true,
      addStickers = true,
      stickers = [],
      subtitleOptions = {},
      ttsOptions = {},
      bgmOptions = {},
      stickerOptions = {},
    } = options;

    if (!videoPath) {
      throw new Error('必须提供视频路径');
    }

    if (!fs.existsSync(videoPath)) {
      throw new Error(`视频文件不存在: ${videoPath}`);
    }

    const videoInfo = await this.videoSplitter.getVideoInfo(videoPath);
    const baseOutputName = outputFileName || `composed_${helpers.generateUniqueId()}`;
    const finalOutputPath = path.join(this.options.outputDir, `${baseOutputName}.mp4`);

    console.log('正在检测视频原声音量...');
    const originalAudioVolume = await this._detectOriginalAudioVolume(videoPath);
    
    const hasTTS = addTTS && textContent;
    const hasBackgroundMusic = addBackgroundMusic && backgroundMusicPath && fs.existsSync(backgroundMusicPath);
    
    const audioPriorityConfig = this._calculateAudioPriority(
      hasTTS,
      hasBackgroundMusic,
      originalAudioVolume,
      videoInfo.audio !== null
    );
    
    console.log(`音频优先级配置:`, {
      hasTTS,
      hasBackgroundMusic,
      hasOriginalAudio: videoInfo.audio !== null,
      originalAudioMeanVolume: originalAudioVolume?.meanVolume,
      isOriginalAudioSilent: audioPriorityConfig.isOriginalAudioSilent,
      useOriginalAudio: audioPriorityConfig.useOriginalAudio,
      originalAudioVolume: audioPriorityConfig.originalAudioVolume,
      backgroundMusicVolume: audioPriorityConfig.backgroundMusicVolume,
    });

    let currentVideoPath = videoPath;
    let audioTracks = [];
    let subtitlePath = null;

    if (addTTS && textContent) {
      console.log('正在生成 TTS 语音...');
      const ttsResults = await this._generateTTS(textContent, ttsOptions);
      
      if (addSubtitles) {
        console.log('正在生成字幕...');
        const subtitleData = this.subtitleGenerator.generateSRTFromTTSResults(
          ttsResults.results.filter(r => r.success),
          subtitleOptions
        );
        const subtitleSaveResult = await this.subtitleGenerator.saveSRT(
          subtitleData,
          path.join(this.options.tempDir, `${baseOutputName}.srt`)
        );
        subtitlePath = subtitleSaveResult.path;
      }

      const ttsAudioTracks = ttsResults.results
        .filter(r => r.success)
        .map(r => ({
          path: r.audioPath,
          volume: config.audio.ttsVolume,
          delay: r.startTime || 0,
          type: 'tts',
        }));
      audioTracks.push(...ttsAudioTracks);
    }

    if (hasBackgroundMusic) {
      console.log('正在处理背景音乐...');
      const bgmResult = await this._processBackgroundMusic(
        backgroundMusicPath,
        videoInfo.duration,
        audioTracks,
        {
          ...bgmOptions,
          volume: audioPriorityConfig.backgroundMusicVolume,
        }
      );
      
      audioTracks.push({
        path: bgmResult.outputPath,
        volume: 1.0,
        delay: 0,
        type: 'bgm',
      });
    }

    if (audioTracks.length > 0 || audioPriorityConfig.useOriginalAudio) {
      console.log('正在将音频添加到视频...');
      const videoWithAudioPath = path.join(this.options.tempDir, `video_with_audio_${helpers.generateUniqueId()}.mp4`);
      
      const hasTTSAudio = hasTTS && audioTracks.some(t => t.type === 'tts');
      const hasBGMAudio = hasBackgroundMusic && audioTracks.some(t => t.type === 'bgm');
      
      currentVideoPath = await this._addMultipleAudioTracksToVideo(
        currentVideoPath,
        audioTracks,
        videoWithAudioPath,
        audioPriorityConfig,
        {
          hasTTSAudio,
          hasBGMAudio,
        }
      );
    }

    if (subtitlePath && fs.existsSync(subtitlePath)) {
      console.log('正在添加字幕...');
      const videoWithSubtitlesPath = path.join(this.options.tempDir, `video_with_subtitles_${helpers.generateUniqueId()}.mp4`);
      currentVideoPath = await this._addSubtitlesToVideo(
        currentVideoPath,
        subtitlePath,
        videoWithSubtitlesPath,
        subtitleOptions
      );
    }

    let stickersAdded = false;
    if (addStickers && stickers && stickers.length > 0) {
      console.log('正在添加贴纸...');
      const videoWithStickersPath = path.join(this.options.tempDir, `video_with_stickers_${helpers.generateUniqueId()}.mp4`);
      const stickerResult = await this.stickerService.addMultipleStickers(
        currentVideoPath,
        stickers,
        {
          outputDir: this.options.tempDir,
          outputFileName: path.basename(videoWithStickersPath),
          ...stickerOptions,
        }
      );
      currentVideoPath = stickerResult.outputPath;
      stickersAdded = true;
    }

    if (currentVideoPath !== finalOutputPath) {
      fs.copyFileSync(currentVideoPath, finalOutputPath);
    }

    if (options.cleanup !== false) {
      this._cleanupTempFiles();
    }

    return {
      success: true,
      outputPath: finalOutputPath,
      filename: path.basename(finalOutputPath),
      originalVideo: videoPath,
      videoInfo: videoInfo,
      ttsAdded: addTTS && textContent,
      subtitlesAdded: addSubtitles && subtitlePath,
      backgroundMusicAdded: addBackgroundMusic && backgroundMusicPath,
      stickersAdded: stickersAdded,
    };
  }

  async composeFromSegments(options) {
    const {
      videoSegments,
      textContents,
      backgroundMusicPath,
      outputFileName,
      addSubtitles = true,
      addBackgroundMusic = true,
      addTTS = true,
      addStickers = true,
      stickers = [],
      subtitleOptions = {},
      ttsOptions = {},
      bgmOptions = {},
      stickerOptions = {},
    } = options;

    if (!videoSegments || videoSegments.length === 0) {
      throw new Error('必须提供视频片段');
    }

    const baseOutputName = outputFileName || `composed_segments_${helpers.generateUniqueId()}`;
    const finalOutputPath = path.join(this.options.outputDir, `${baseOutputName}.mp4`);

    let mergedVideoPath = videoSegments[0].path;
    if (videoSegments.length > 1) {
      console.log('正在合并视频片段...');
      mergedVideoPath = path.join(this.options.tempDir, `merged_video_${helpers.generateUniqueId()}.mp4`);
      await this.videoSplitter.mergeVideos(
        videoSegments.map(s => s.path),
        mergedVideoPath
      );
    }

    return this.composeVideo({
      videoPath: mergedVideoPath,
      textContent: textContents,
      backgroundMusicPath: backgroundMusicPath,
      outputFileName: baseOutputName,
      addSubtitles,
      addBackgroundMusic,
      addTTS,
      addStickers,
      stickers,
      subtitleOptions,
      ttsOptions,
      bgmOptions,
      stickerOptions,
      cleanup: true,
    });
  }

  async splitAndCompose(options) {
    const {
      videoPath,
      segmentDuration,
      textContents,
      backgroundMusicPath,
      outputFileName,
      addSubtitles = true,
      addBackgroundMusic = true,
      addTTS = true,
      addStickers = true,
      stickers = [],
      subtitleOptions = {},
      ttsOptions = {},
      bgmOptions = {},
      stickerOptions = {},
    } = options;

    if (!videoPath) {
      throw new Error('必须提供视频路径');
    }

    if (!fs.existsSync(videoPath)) {
      throw new Error(`视频文件不存在: ${videoPath}`);
    }

    console.log('正在分割视频...');
    const splitResult = await this.videoSplitter.splitVideo(videoPath, {
      segmentDuration,
    });

    let segmentsWithText = splitResult.segments;
    
    if (textContents && Array.isArray(textContents)) {
      segmentsWithText = splitResult.segments.map((segment, index) => ({
        ...segment,
        text: textContents[index] || '',
      }));
    }

    const combinedText = segmentsWithText.map(s => s.text || '').join(' ');

    return this.composeVideo({
      videoPath: videoPath,
      textContent: combinedText,
      backgroundMusicPath: backgroundMusicPath,
      outputFileName: outputFileName,
      addSubtitles,
      addBackgroundMusic,
      addTTS,
      addStickers,
      stickers,
      subtitleOptions,
      ttsOptions,
      bgmOptions,
      stickerOptions,
      cleanup: true,
    });
  }

  async _generateTTS(textContent, options = {}) {
    let texts;
    if (typeof textContent === 'string') {
      texts = this._splitTextForTTS(textContent, options);
    } else if (Array.isArray(textContent)) {
      texts = textContent;
    } else {
      throw new Error('textContent 必须是字符串或数组');
    }

    return this.ttsService.synthesizeBatch(texts, {
      outputDir: this.options.tempDir,
      ...options,
    });
  }

  _splitTextForTTS(text, options = {}) {
    const {
      maxCharsPerSegment = 500,
      splitBySentence = true,
    } = options;

    const segments = [];

    if (splitBySentence) {
      const sentenceEndings = /([。！？.!?]+)/g;
      const sentences = text.split(sentenceEndings).filter(s => s.trim());
      
      let currentSegment = '';
      for (let i = 0; i < sentences.length; i++) {
        const sentence = sentences[i].trim();
        if (sentence.match(sentenceEndings)) {
          currentSegment += sentence;
          continue;
        }

        if (currentSegment.length + sentence.length > maxCharsPerSegment && currentSegment.length > 0) {
          segments.push(currentSegment.trim());
          currentSegment = sentence;
        } else {
          currentSegment += sentence;
        }
      }

      if (currentSegment.trim()) {
        segments.push(currentSegment.trim());
      }
    } else {
      for (let i = 0; i < text.length; i += maxCharsPerSegment) {
        segments.push(text.substring(i, i + maxCharsPerSegment));
      }
    }

    return segments.filter(s => s.length > 0);
  }

  async _processBackgroundMusic(backgroundMusicPath, targetDuration, voiceSegments, options = {}) {
    const {
      volume = config.audio.backgroundMusicVolume,
      applyDucking = true,
      fadeIn = config.audio.fadeDuration,
      fadeOut = config.audio.fadeDuration,
    } = options;

    console.log('正在循环播放背景音乐到目标时长...');
    const loopedBgm = await this.backgroundMusicService.loopAudioToDuration(
      backgroundMusicPath,
      targetDuration,
      {
        outputDir: this.options.tempDir,
        volume,
        fadeIn,
        fadeOut,
      }
    );

    if (applyDucking && voiceSegments.length > 0) {
      console.log('正在应用闪避效果...');
      const duckedBgm = await this.backgroundMusicService.applyDucking(
        loopedBgm.outputPath,
        voiceSegments.map((v, i) => ({
          startTime: v.delay || i * 0.1,
          endTime: (v.delay || i * 0.1) + 10,
        })),
        {
          outputDir: this.options.tempDir,
          duckingAmount: config.audio.duckingAmount,
        }
      );
      return duckedBgm;
    }

    return loopedBgm;
  }

  async _addAudioToVideo(videoPath, audioPath, outputPath) {
    return new Promise((resolve, reject) => {
      const command = ffmpeg(videoPath)
        .input(audioPath)
        .output(outputPath)
        .outputOptions([
          '-c:v', 'copy',
          '-c:a', 'aac',
          '-map', '0:v:0',
          '-map', '1:a:0',
          '-shortest',
        ]);

      command
        .on('end', () => {
          resolve(outputPath);
        })
        .on('error', (err) => {
          reject(new Error(`添加音频到视频失败: ${err.message}`));
        })
        .run();
    });
  }

  async _addSubtitlesToVideo(videoPath, subtitlePath, outputPath, options = {}) {
    const {
      fontSize = config.subtitle.fontSize,
      fontColor = config.subtitle.fontColor,
      backgroundColor = config.subtitle.backgroundColor,
      position = config.subtitle.position,
      marginV = config.subtitle.marginV,
    } = options;

    return new Promise((resolve, reject) => {
      const subtitlePathEscaped = subtitlePath.replace(/\\/g, '/').replace(/:/g, '\\:');
      
      const vfFilters = [
        `subtitles='${subtitlePathEscaped}':` +
        `force_style='FontSize=${fontSize},` +
        `PrimaryColour=&H${this._colorToHex(fontColor)}&,` +
        `BackColour=&H${this._colorToHex(backgroundColor)}&,` +
        `Alignment=${this._positionToAlignment(position)},` +
        `MarginV=${marginV}'`,
      ];

      const command = ffmpeg(videoPath)
        .videoFilters(vfFilters)
        .output(outputPath)
        .outputOptions([
          '-c:a', 'copy',
        ]);

      command
        .on('end', () => {
          resolve(outputPath);
        })
        .on('error', (err) => {
          reject(new Error(`添加字幕到视频失败: ${err.message}`));
        })
        .run();
    });
  }

  _colorToHex(color) {
    const colorMap = {
      'white': 'ffffff',
      'black': '000000',
      'red': '0000ff',
      'green': '00ff00',
      'blue': 'ff0000',
      'yellow': '00ffff',
      'cyan': 'ffff00',
      'magenta': 'ff00ff',
    };

    if (colorMap[color.toLowerCase()]) {
      return colorMap[color.toLowerCase()];
    }

    if (color.startsWith('#')) {
      return color.substring(1).padStart(6, '0');
    }

    const alphaMatch = color.match(/^(\w+)@([\d.]+)$/);
    if (alphaMatch) {
      const baseColor = alphaMatch[1];
      const alpha = parseFloat(alphaMatch[2]);
      const alphaHex = Math.round(alpha * 255).toString(16).padStart(2, '0');
      const baseHex = colorMap[baseColor.toLowerCase()] || 'ffffff';
      return alphaHex + baseHex.substring(2);
    }

    return 'ffffff';
  }

  _positionToAlignment(position) {
    const positionMap = {
      'top': 8,
      'top-left': 7,
      'top-right': 9,
      'middle': 5,
      'middle-left': 4,
      'middle-right': 6,
      'bottom': 2,
      'bottom-left': 1,
      'bottom-right': 3,
    };
    return positionMap[position.toLowerCase()] || 2;
  }

  _cleanupTempFiles() {
    try {
      const tempFiles = fs.readdirSync(this.options.tempDir);
      tempFiles.forEach(file => {
        const filePath = path.join(this.options.tempDir, file);
        if (fs.statSync(filePath).isFile()) {
          fs.unlinkSync(filePath);
        }
      });
      console.log('临时文件已清理');
    } catch (error) {
      console.warn(`清理临时文件时出错: ${error.message}`);
    }
  }

  async _detectOriginalAudioVolume(videoPath) {
    try {
      const volumeInfo = await this.videoSplitter.getAudioVolume(videoPath);
      return volumeInfo;
    } catch (error) {
      console.warn(`检测视频原声音量失败: ${error.message}`);
      return {
        meanVolume: null,
        maxVolume: null,
        hasAudio: false,
      };
    }
  }

  _calculateAudioPriority(hasTTS, hasBackgroundMusic, originalAudioVolume, hasOriginalAudio) {
    const threshold = config.audio.videoOriginalSilenceThreshold;
    const isOriginalAudioSilent = !hasOriginalAudio || 
      originalAudioVolume.meanVolume === null || 
      originalAudioVolume.meanVolume <= threshold;

    let useOriginalAudio = false;
    let originalAudioVolumeFactor = 1.0;
    let backgroundMusicVolumeFactor = config.audio.backgroundMusicVolume;

    if (hasTTS) {
      useOriginalAudio = false;
      originalAudioVolumeFactor = config.audio.videoOriginalVolumeWithTTS;
      
      if (isOriginalAudioSilent) {
        backgroundMusicVolumeFactor = config.audio.backgroundMusicVolume;
      } else {
        backgroundMusicVolumeFactor = config.audio.backgroundMusicVolumeWithTTS;
      }
    } else {
      useOriginalAudio = hasOriginalAudio && !isOriginalAudioSilent;
      originalAudioVolumeFactor = 1.0;
      
      if (isOriginalAudioSilent) {
        backgroundMusicVolumeFactor = config.audio.backgroundMusicVolume;
      } else {
        backgroundMusicVolumeFactor = config.audio.backgroundMusicVolumeWithoutTTS;
      }
    }

    return {
      hasTTS,
      hasBackgroundMusic,
      hasOriginalAudio,
      isOriginalAudioSilent,
      useOriginalAudio,
      originalAudioVolume: originalAudioVolumeFactor,
      backgroundMusicVolume: backgroundMusicVolumeFactor,
    };
  }

  async _addAudioToVideoWithPriority(videoPath, audioPath, outputPath, audioPriorityConfig) {
    return new Promise((resolve, reject) => {
      const { useOriginalAudio, originalAudioVolume, hasTTS, hasBackgroundMusic } = audioPriorityConfig;

      let command = ffmpeg(videoPath);

      const outputOptions = [
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-shortest',
      ];

      const mapOptions = ['-map', '0:v:0'];

      if (useOriginalAudio && originalAudioVolume > 0) {
        if (originalAudioVolume !== 1.0) {
          mapOptions.push('-map', '0:a:0');
          outputOptions.push('-metadata:s:a:0', `title=原声`);
          outputOptions.push(`-filter:a:0`, `volume=${originalAudioVolume}`);
        } else {
          mapOptions.push('-map', '0:a:0');
          outputOptions.push('-metadata:s:a:0', `title=原声`);
        }
      }

      if (audioPath) {
        command = command.input(audioPath);
        
        if (hasTTS) {
          if (useOriginalAudio && originalAudioVolume > 0) {
            outputOptions.push('-metadata:s:a:1', `title=配音`);
          } else {
            outputOptions.push('-metadata:s:a:0', `title=配音`);
          }
        } else if (hasBackgroundMusic) {
          if (useOriginalAudio && originalAudioVolume > 0) {
            outputOptions.push('-metadata:s:a:1', `title=背景音乐`);
          } else {
            outputOptions.push('-metadata:s:a:0', `title=背景音乐`);
          }
        }
        
        mapOptions.push('-map', '1:a:0');
      }

      command = command.outputOptions([...mapOptions, ...outputOptions]);

      command
        .on('end', () => {
          resolve(outputPath);
        })
        .on('error', (err) => {
          reject(new Error(`添加音频到视频失败: ${err.message}`));
        })
        .output(outputPath)
        .run();
    });
  }

  async _adjustVideoOriginalAudioVolume(videoPath, outputPath, volume) {
    return new Promise((resolve, reject) => {
      const command = ffmpeg(videoPath)
        .output(outputPath)
        .outputOptions([
          '-c:v', 'copy',
          '-c:a', 'aac',
          '-af', `volume=${volume}`,
        ]);

      command
        .on('end', () => {
          resolve(outputPath);
        })
        .on('error', (err) => {
          reject(new Error(`调整视频原声音量失败: ${err.message}`));
        })
        .run();
    });
  }

  async _addMultipleAudioTracksToVideo(videoPath, audioTracks, outputPath, audioPriorityConfig, audioTypeInfo) {
    return new Promise((resolve, reject) => {
      const { useOriginalAudio, originalAudioVolume } = audioPriorityConfig;
      const { hasTTSAudio, hasBGMAudio } = audioTypeInfo;

      let command = ffmpeg(videoPath);
      
      let audioTrackIndex = 1;
      let audioMetadataIndex = 0;
      
      const outputOptions = [
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-shortest',
      ];

      const mapOptions = ['-map', '0:v:0'];

      if (useOriginalAudio && originalAudioVolume > 0) {
        mapOptions.push('-map', '0:a:0');
        outputOptions.push('-metadata:s:a:0', `title=原声`);
        
        if (originalAudioVolume !== 1.0) {
          outputOptions.push('-filter:a:0', `volume=${originalAudioVolume}`);
        }
        
        audioMetadataIndex = 1;
      }

      if (hasTTSAudio) {
        const ttsTracks = audioTracks.filter(t => t.type === 'tts');
        
        for (const track of ttsTracks) {
          command = command.input(track.path);
          mapOptions.push('-map', `${audioTrackIndex}:a:0`);
          outputOptions.push('-metadata:s:a:' + audioMetadataIndex, `title=配音`);
          
          if (track.volume !== 1.0 || track.delay > 0) {
            const filters = [];
            if (track.volume !== 1.0) {
              filters.push(`volume=${track.volume}`);
            }
            if (track.delay > 0) {
              filters.push(`adelay=${track.delay * 1000}`);
            }
            if (filters.length > 0) {
              outputOptions.push(`-filter:a:${audioMetadataIndex}`, filters.join(','));
            }
          }
          
          audioTrackIndex++;
          audioMetadataIndex++;
        }
      }

      if (hasBGMAudio) {
        const bgmTracks = audioTracks.filter(t => t.type === 'bgm');
        
        for (const track of bgmTracks) {
          command = command.input(track.path);
          mapOptions.push('-map', `${audioTrackIndex}:a:0`);
          outputOptions.push('-metadata:s:a:' + audioMetadataIndex, `title=背景音乐`);
          
          if (track.volume !== 1.0 || track.delay > 0) {
            const filters = [];
            if (track.volume !== 1.0) {
              filters.push(`volume=${track.volume}`);
            }
            if (track.delay > 0) {
              filters.push(`adelay=${track.delay * 1000}`);
            }
            if (filters.length > 0) {
              outputOptions.push(`-filter:a:${audioMetadataIndex}`, filters.join(','));
            }
          }
          
          audioTrackIndex++;
          audioMetadataIndex++;
        }
      }

      command = command.outputOptions([...mapOptions, ...outputOptions]);

      command
        .on('end', () => {
          resolve(outputPath);
        })
        .on('error', (err) => {
          reject(new Error(`添加多音轨到视频失败: ${err.message}`));
        })
        .output(outputPath)
        .run();
    });
  }
}

export default VideoComposer;