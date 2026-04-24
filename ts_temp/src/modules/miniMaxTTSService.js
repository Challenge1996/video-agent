import fs from 'fs-extra';
import path from 'path';
import config from '../config/index.js';
import helpers from '../utils/helpers.js';
import ffmpeg from 'fluent-ffmpeg';

ffmpeg.setFfmpegPath(config.ffmpeg.path);
ffmpeg.setFfprobePath(config.ffmpeg.ffprobePath);

class MiniMaxTTSService {
  constructor(options = {}) {
    this.options = {
      apiKey: options.apiKey || config.minimax.apiKey,
      groupId: options.groupId || config.minimax.groupId,
      baseUrl: options.baseUrl || config.minimax.baseUrl,
      model: options.model || config.minimax.model,
      voiceId: options.voiceId || config.minimax.tts.voiceId,
      speed: options.speed || config.minimax.tts.speed,
      vol: options.vol || config.minimax.tts.vol,
      pitch: options.pitch || config.minimax.tts.pitch,
      emotion: options.emotion || config.minimax.tts.emotion,
      sampleRate: options.sampleRate || config.minimax.tts.sampleRate,
      bitrate: options.bitrate || config.minimax.tts.bitrate,
      format: options.format || config.minimax.tts.format,
      channel: options.channel || config.minimax.tts.channel,
      outputDir: options.outputDir || config.directories.temp,
      ...options,
    };
  }

  _getBaseUrl() {
    return this.options.baseUrl;
  }

  async synthesizeSpeech(text, options = {}) {
    const outputDir = options.outputDir || this.options.outputDir;
    const outputFileName = options.outputFileName || `tts_${helpers.generateUniqueId()}.mp3`;
    const outputPath = path.join(outputDir, outputFileName);

    helpers.ensureDirectory(outputDir);

    const requestBody = {
      model: options.model || this.options.model,
      text: text,
      stream: false,
      output_format: 'url',
      voice_setting: {
        voice_id: options.voiceId || this.options.voiceId,
        speed: options.speed || this.options.speed,
        vol: options.vol || this.options.vol,
        pitch: options.pitch || this.options.pitch,
        emotion: options.emotion || this.options.emotion,
      },
      audio_setting: {
        sample_rate: options.sampleRate || this.options.sampleRate,
        bitrate: options.bitrate || this.options.bitrate,
        format: options.format || this.options.format,
        channel: options.channel || this.options.channel,
      },
      subtitle_enable: false,
    };

    if (options.pronunciationDict) {
      requestBody.pronunciation_dict = options.pronunciationDict;
    }

    try {
      const baseUrl = this._getBaseUrl();
      const response = await fetch(baseUrl, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.options.apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`MiniMax API 请求失败: ${response.status} - ${errorText}`);
      }

      const data = await response.json();

      if (data.base_resp?.status_code !== 0) {
        const errorMsg = data.base_resp?.status_msg || '未知错误';
        throw new Error(`MiniMax TTS 合成失败: ${errorMsg}`);
      }

      const audioContent = data.data?.audio;
      if (!audioContent) {
        throw new Error('MiniMax API 未返回音频数据');
      }

      if (audioContent.startsWith('http://') || audioContent.startsWith('https://')) {
        await this._downloadAudioFromUrl(audioContent, outputPath);
      } else {
        const audioBuffer = Buffer.from(audioContent, 'base64');
        fs.writeFileSync(outputPath, audioBuffer);
      }

      const audioInfo = await this._getAudioInfo(outputPath);

      return {
        success: true,
        text: text,
        audioPath: outputPath,
        filename: outputFileName,
        duration: audioInfo.duration,
        format: this.options.format,
      };
    } catch (error) {
      throw new Error(`MiniMax TTS 合成失败: ${error.message}`);
    }
  }

  async synthesizeBatch(texts, options = {}) {
    const results = [];
    const outputDir = options.outputDir || this.options.outputDir;

    for (let i = 0; i < texts.length; i++) {
      const textItem = texts[i];
      const text = typeof textItem === 'string' ? textItem : textItem.text;
      const itemOptions = typeof textItem === 'object' ? { ...textItem, ...options } : options;
      const outputFileName = itemOptions.outputFileName || `tts_${String(i).padStart(3, '0')}_${helpers.generateUniqueId()}.mp3`;

      try {
        const result = await this.synthesizeSpeech(text, {
          ...itemOptions,
          outputDir,
          outputFileName,
        });
        results.push({
          ...result,
          index: i,
          text: text,
        });
      } catch (error) {
        results.push({
          success: false,
          index: i,
          text: text,
          error: error.message,
        });
      }
    }

    return {
      success: results.every(r => r.success),
      results: results,
      successfulCount: results.filter(r => r.success).length,
      failedCount: results.filter(r => !r.success).length,
    };
  }

  async _downloadAudioFromUrl(url, outputPath) {
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`下载音频失败: ${response.status}`);
      }
      const arrayBuffer = await response.arrayBuffer();
      const buffer = Buffer.from(arrayBuffer);
      fs.writeFileSync(outputPath, buffer);
    } catch (error) {
      throw new Error(`从 URL 下载音频失败: ${error.message}`);
    }
  }

  _getAudioInfo(audioPath) {
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
}

export default MiniMaxTTSService;
