import ffmpeg from 'fluent-ffmpeg';
import path from 'path';
import fs from 'fs-extra';
import config from '../config/index.js';
import helpers from '../utils/helpers.js';

ffmpeg.setFfmpegPath(config.ffmpeg.path);
ffmpeg.setFfprobePath(config.ffmpeg.ffprobePath);

class StickerService {
  constructor(options = {}) {
    this.options = {
      outputDir: options.outputDir || config.directories.temp,
      defaultOpacity: options.defaultOpacity || config.sticker.defaultOpacity,
      defaultScale: options.defaultScale || config.sticker.defaultScale,
      defaultPosition: options.defaultPosition || config.sticker.defaultPosition,
      ...options,
    };
  }

  async getImageInfo(imagePath) {
    return new Promise((resolve, reject) => {
      ffmpeg.ffprobe(imagePath, (err, metadata) => {
        if (err) {
          reject(new Error(`无法获取图片信息: ${err.message}`));
          return;
        }

        const videoStream = metadata.streams.find(s => s.codec_type === 'video');

        resolve({
          width: videoStream ? videoStream.width : 0,
          height: videoStream ? videoStream.height : 0,
          duration: metadata.format.duration ? parseFloat(metadata.format.duration) : null,
          isAnimated: metadata.format.duration ? parseFloat(metadata.format.duration) > 0 : false,
          format: metadata.format.format_name,
        });
      });
    });
  }

  _validateStickerOptions(sticker, videoInfo) {
    const {
      path: stickerPath,
      type = 'static',
      position = this.options.defaultPosition,
      scale = this.options.defaultScale,
      opacity = this.options.defaultOpacity,
      startSeconds = 0,
      duration = null,
      x = null,
      y = null,
    } = sticker;

    if (!stickerPath) {
      throw new Error('贴纸路径不能为空');
    }

    if (!fs.existsSync(stickerPath)) {
      throw new Error(`贴纸文件不存在: ${stickerPath}`);
    }

    if (scale <= 0) {
      throw new Error('缩放比例必须大于0');
    }

    if (opacity < 0 || opacity > 1) {
      throw new Error('透明度必须在0到1之间');
    }

    if (startSeconds < 0) {
      throw new Error('开始时间不能为负数');
    }

    if (duration !== null && duration <= 0) {
      throw new Error('持续时间必须大于0');
    }

    const validTypes = ['static', 'gif'];
    if (!validTypes.includes(type)) {
      throw new Error(`不支持的贴纸类型: ${type}，支持的类型: ${validTypes.join(', ')}`);
    }

    return {
      stickerPath,
      type,
      position,
      scale,
      opacity,
      startSeconds,
      duration,
      x,
      y,
    };
  }

  _calculatePosition(position, videoWidth, videoHeight, stickerWidth, stickerHeight, x = null, y = null) {
    if (x !== null && y !== null) {
      return { x, y };
    }

    const xCenter = (videoWidth - stickerWidth) / 2;
    const yCenter = (videoHeight - stickerHeight) / 2;

    const margin = Math.min(videoWidth, videoHeight) * 0.05;

    const positions = {
      'top-left': { x: margin, y: margin },
      'top': { x: xCenter, y: margin },
      'top-right': { x: videoWidth - stickerWidth - margin, y: margin },
      'middle-left': { x: margin, y: yCenter },
      'middle': { x: xCenter, y: yCenter },
      'middle-right': { x: videoWidth - stickerWidth - margin, y: yCenter },
      'bottom-left': { x: margin, y: videoHeight - stickerHeight - margin },
      'bottom': { x: xCenter, y: videoHeight - stickerHeight - margin },
      'bottom-right': { x: videoWidth - stickerWidth - margin, y: videoHeight - stickerHeight - margin },
    };

    return positions[position] || positions['top-left'];
  }

  async addSingleSticker(videoPath, sticker, options = {}) {
    const outputDir = options.outputDir || this.options.outputDir;
    const outputFileName = options.outputFileName || `video_with_sticker_${helpers.generateUniqueId()}.mp4`;
    const outputPath = path.join(outputDir, outputFileName);

    helpers.ensureDirectory(outputDir);

    const videoInfo = await new Promise((resolve, reject) => {
      ffmpeg.ffprobe(videoPath, (err, metadata) => {
        if (err) {
          reject(new Error(`无法获取视频信息: ${err.message}`));
          return;
        }
        const videoStream = metadata.streams.find(s => s.codec_type === 'video');
        resolve({
          width: videoStream ? videoStream.width : 1920,
          height: videoStream ? videoStream.height : 1080,
          duration: parseFloat(metadata.format.duration),
        });
      });
    });

    const validatedSticker = this._validateStickerOptions(sticker, videoInfo);
    const stickerInfo = await this.getImageInfo(validatedSticker.stickerPath);

    const scaledWidth = Math.round(stickerInfo.width * validatedSticker.scale);
    const scaledHeight = Math.round(stickerInfo.height * validatedSticker.scale);

    const { x, y } = this._calculatePosition(
      validatedSticker.position,
      videoInfo.width,
      videoInfo.height,
      scaledWidth,
      scaledHeight,
      validatedSticker.x,
      validatedSticker.y
    );

    const endTime = validatedSticker.duration 
      ? validatedSticker.startSeconds + validatedSticker.duration 
      : videoInfo.duration;

    let gifLoopCount = 1;
    let gifActualDuration = stickerInfo.duration || 0;
    if (validatedSticker.type === 'gif' && stickerInfo.isAnimated && gifActualDuration > 0) {
      const displayDuration = endTime - validatedSticker.startSeconds;
      gifLoopCount = Math.ceil(displayDuration / gifActualDuration);
    }

    return new Promise((resolve, reject) => {
      let command = ffmpeg(videoPath);

      if (validatedSticker.type === 'gif' && stickerInfo.isAnimated) {
        command = command.inputOptions('-ignore_loop', '0');
      }

      command = command.input(validatedSticker.stickerPath);

      const filterComplex = [];

      const scaleFilter = `[1:v]scale=${scaledWidth}:${scaledHeight}[scaled_sticker]`;
      filterComplex.push(scaleFilter);

      if (validatedSticker.opacity < 1) {
        const alpha = validatedSticker.opacity;
        const opacityFilter = `[scaled_sticker]colorchannelmixer=aa=${alpha}[transparent_sticker]`;
        filterComplex.push(opacityFilter);
      }

      const stickerInput = validatedSticker.opacity < 1 ? 'transparent_sticker' : 'scaled_sticker';

      let enableOption = '';
      if (validatedSticker.startSeconds > 0 || validatedSticker.duration !== null) {
        const start = validatedSticker.startSeconds;
        const end = endTime;
        enableOption = `:enable='between(t,${start},${end})'`;
      }

      const overlayFilter = `[0:v][${stickerInput}]overlay=x=${x}:y=${y}${enableOption}[out]`;
      filterComplex.push(overlayFilter);

      command.complexFilter(filterComplex, 'out')
        .output(outputPath)
        .outputOptions([
          '-c:v', 'libx264',
          '-preset', 'medium',
          '-crf', '23',
          '-c:a', 'copy',
        ]);

      command
        .on('end', () => {
          resolve({
            success: true,
            originalVideo: videoPath,
            outputPath: outputPath,
            filename: outputFileName,
            sticker: {
              ...validatedSticker,
              scaledWidth,
              scaledHeight,
              x,
              y,
              width: stickerInfo.width,
              height: stickerInfo.height,
              gifDuration: gifActualDuration,
              gifLoopCount: gifLoopCount,
            },
          });
        })
        .on('error', (err) => {
          reject(new Error(`添加贴纸失败: ${err.message}`));
        })
        .run();
    });
  }

  async addMultipleStickers(videoPath, stickers, options = {}) {
    if (!stickers || stickers.length === 0) {
      throw new Error('没有提供贴纸');
    }

    const outputDir = options.outputDir || this.options.outputDir;
    const outputFileName = options.outputFileName || `video_with_stickers_${helpers.generateUniqueId()}.mp4`;
    const outputPath = path.join(outputDir, outputFileName);

    helpers.ensureDirectory(outputDir);

    const videoInfo = await new Promise((resolve, reject) => {
      ffmpeg.ffprobe(videoPath, (err, metadata) => {
        if (err) {
          reject(new Error(`无法获取视频信息: ${err.message}`));
          return;
        }
        const videoStream = metadata.streams.find(s => s.codec_type === 'video');
        resolve({
          width: videoStream ? videoStream.width : 1920,
          height: videoStream ? videoStream.height : 1080,
          duration: parseFloat(metadata.format.duration),
        });
      });
    });

    const validatedStickers = [];
    const stickersInfo = [];
    const hasGifStickers = [];

    for (const sticker of stickers) {
      const validated = this._validateStickerOptions(sticker, videoInfo);
      const info = await this.getImageInfo(validated.stickerPath);
      validatedStickers.push(validated);
      stickersInfo.push(info);
      hasGifStickers.push(validated.type === 'gif' && info.isAnimated);
    }

    const hasAnyGif = hasGifStickers.some(isGif => isGif);

    return new Promise((resolve, reject) => {
      let command = ffmpeg(videoPath);

      if (hasAnyGif) {
        command = command.inputOptions('-ignore_loop', '0');
      }

      for (const sticker of validatedStickers) {
        command = command.input(sticker.stickerPath);
      }

      const filterComplex = [];
      let currentVideo = '0:v';

      for (let i = 0; i < validatedStickers.length; i++) {
        const sticker = validatedStickers[i];
        const stickerInfo = stickersInfo[i];
        const inputIndex = i + 1;

        const scaledWidth = Math.round(stickerInfo.width * sticker.scale);
        const scaledHeight = Math.round(stickerInfo.height * sticker.scale);

        const { x, y } = this._calculatePosition(
          sticker.position,
          videoInfo.width,
          videoInfo.height,
          scaledWidth,
          scaledHeight,
          sticker.x,
          sticker.y
        );

        const endTime = sticker.duration 
          ? sticker.startSeconds + sticker.duration 
          : videoInfo.duration;

        let gifLoopCount = 1;
        let gifActualDuration = stickerInfo.duration || 0;
        if (sticker.type === 'gif' && stickerInfo.isAnimated && gifActualDuration > 0) {
          const displayDuration = endTime - sticker.startSeconds;
          gifLoopCount = Math.ceil(displayDuration / gifActualDuration);
        }

        const scaledLabel = `scaled_${i}`;
        const scaleFilter = `[${inputIndex}:v]scale=${scaledWidth}:${scaledHeight}[${scaledLabel}]`;
        filterComplex.push(scaleFilter);

        let stickerLabel = scaledLabel;

        if (sticker.opacity < 1) {
          const alpha = sticker.opacity;
          const transparentLabel = `transparent_${i}`;
          const opacityFilter = `[${scaledLabel}]colorchannelmixer=aa=${alpha}[${transparentLabel}]`;
          filterComplex.push(opacityFilter);
          stickerLabel = transparentLabel;
        }

        let enableOption = '';
        if (sticker.startSeconds > 0 || sticker.duration !== null) {
          const start = sticker.startSeconds;
          const end = endTime;
          enableOption = `:enable='between(t,${start},${end})'`;
        }

        const outputLabel = `layer_${i}`;
        const overlayFilter = `[${currentVideo}][${stickerLabel}]overlay=x=${x}:y=${y}${enableOption}[${outputLabel}]`;
        filterComplex.push(overlayFilter);

        currentVideo = outputLabel;

        validatedStickers[i] = {
          ...sticker,
          scaledWidth,
          scaledHeight,
          x,
          y,
          width: stickerInfo.width,
          height: stickerInfo.height,
          gifDuration: gifActualDuration,
          gifLoopCount: gifLoopCount,
        };
      }

      command.complexFilter(filterComplex, currentVideo)
        .output(outputPath)
        .outputOptions([
          '-c:v', 'libx264',
          '-preset', 'medium',
          '-crf', '23',
          '-c:a', 'copy',
        ]);

      command
        .on('end', () => {
          resolve({
            success: true,
            originalVideo: videoPath,
            outputPath: outputPath,
            filename: outputFileName,
            stickers: validatedStickers,
            stickersCount: validatedStickers.length,
          });
        })
        .on('error', (err) => {
          reject(new Error(`添加多个贴纸失败: ${err.message}`));
        })
        .run();
    });
  }

  async createStaticStickerFromGif(gifPath, frameIndex = 0, options = {}) {
    const outputDir = options.outputDir || this.options.outputDir;
    const outputFileName = options.outputFileName || `static_from_gif_${helpers.generateUniqueId()}.png`;
    const outputPath = path.join(outputDir, outputFileName);

    helpers.ensureDirectory(outputDir);

    if (!fs.existsSync(gifPath)) {
      throw new Error(`GIF文件不存在: ${gifPath}`);
    }

    const gifInfo = await this.getImageInfo(gifPath);
    if (!gifInfo.isAnimated) {
      throw new Error('文件不是动画GIF');
    }

    return new Promise((resolve, reject) => {
      const command = ffmpeg(gifPath)
        .outputOptions([
          `-vf`, `select=eq(n\\,${frameIndex})`,
          '-vframes', '1',
        ])
        .output(outputPath);

      command
        .on('end', () => {
          resolve({
            success: true,
            originalGif: gifPath,
            outputPath: outputPath,
            filename: outputFileName,
            frameIndex: frameIndex,
          });
        })
        .on('error', (err) => {
          reject(new Error(`从GIF创建静态贴纸失败: ${err.message}`));
        })
        .run();
    });
  }

  async validateStickerFile(stickerPath) {
    if (!fs.existsSync(stickerPath)) {
      return {
        valid: false,
        error: `文件不存在: ${stickerPath}`,
      };
    }

    try {
      const info = await this.getImageInfo(stickerPath);
      
      const validFormats = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'];
      const formatValid = info.format && validFormats.some(f => info.format.toLowerCase().includes(f));

      return {
        valid: formatValid,
        type: info.isAnimated ? 'gif' : 'static',
        width: info.width,
        height: info.height,
        isAnimated: info.isAnimated,
        format: info.format,
      };
    } catch (error) {
      return {
        valid: false,
        error: `无法读取文件: ${error.message}`,
      };
    }
  }
}

export default StickerService;
