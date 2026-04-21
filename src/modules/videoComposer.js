import ffmpeg from 'fluent-ffmpeg';
import path from 'path';
import fs from 'fs-extra';
import config from '../config/index.js';
import helpers from '../utils/helpers.js';
import VideoSplitter from './videoSplitter.js';
import TTSService from './ttsService.js';
import SubtitleGenerator from './subtitleGenerator.js';
import BackgroundMusicService from './backgroundMusic.js';

ffmpeg.setFfmpegPath(config.ffmpeg.path);
ffmpeg.setFfprobePath(config.ffmpeg.ffprobePath);

class VideoComposer {
  constructor(options = {}) {
    this.options = {
      outputDir: options.outputDir || config.directories.output,
      tempDir: options.tempDir || config.directories.temp,
      ...options,
    };

    this.videoSplitter = new VideoSplitter({
      outputDir: this.options.tempDir,
      ...options.videoSplitterOptions,
    });

    this.ttsService = new TTSService({
      outputDir: this.options.tempDir,
      ...options.ttsOptions,
    });

    this.subtitleGenerator = new SubtitleGenerator({
      outputDir: this.options.tempDir,
      ...options.subtitleOptions,
    });

    this.backgroundMusicService = new BackgroundMusicService({
      outputDir: this.options.tempDir,
      ...options.backgroundMusicOptions,
    });

    helpers.ensureDirectory(this.options.outputDir);
    helpers.ensureDirectory(this.options.tempDir);
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
      subtitleOptions = {},
      ttsOptions = {},
      bgmOptions = {},
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
        }));
      audioTracks.push(...ttsAudioTracks);
    }

    if (addBackgroundMusic && backgroundMusicPath) {
      if (!fs.existsSync(backgroundMusicPath)) {
        console.warn(`背景音乐文件不存在: ${backgroundMusicPath}，跳过背景音乐`);
      } else {
        console.log('正在处理背景音乐...');
        const bgmResult = await this._processBackgroundMusic(
          backgroundMusicPath,
          videoInfo.duration,
          audioTracks,
          bgmOptions
        );
        
        audioTracks.push({
          path: bgmResult.outputPath,
          volume: 1.0,
          delay: 0,
        });
      }
    }

    if (audioTracks.length > 0) {
      console.log('正在合并音频轨道...');
      const mergedAudioPath = path.join(this.options.tempDir, `merged_audio_${helpers.generateUniqueId()}.mp3`);
      const mergeResult = await this.backgroundMusicService.mergeAudioTracks(
        audioTracks,
        mergedAudioPath
      );

      console.log('正在将音频添加到视频...');
      const videoWithAudioPath = path.join(this.options.tempDir, `video_with_audio_${helpers.generateUniqueId()}.mp4`);
      currentVideoPath = await this._addAudioToVideo(
        currentVideoPath,
        mergeResult.outputPath,
        videoWithAudioPath
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
      subtitleOptions = {},
      ttsOptions = {},
      bgmOptions = {},
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
      subtitleOptions,
      ttsOptions,
      bgmOptions,
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
      subtitleOptions = {},
      ttsOptions = {},
      bgmOptions = {},
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
      subtitleOptions,
      ttsOptions,
      bgmOptions,
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
}

export default VideoComposer;