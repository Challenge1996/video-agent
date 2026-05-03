import { TextToSpeechClient } from '@google-cloud/text-to-speech';
import fs from 'fs-extra';
import path from 'path';
import config from '../config/index.js';
import helpers from '../utils/helpers.js';
import ffmpeg from 'fluent-ffmpeg';

ffmpeg.setFfmpegPath(config.ffmpeg.path);
ffmpeg.setFfprobePath(config.ffmpeg.ffprobePath);

class TTSService {
  constructor(options = {}) {
    this.client = null;
    this.options = {
      credentials: options.credentials || config.google.credentials,
      languageCode: options.languageCode || config.google.tts.languageCode,
      voiceName: options.voiceName || config.google.tts.voiceName,
      speakingRate: options.speakingRate || config.google.tts.speakingRate,
      pitch: options.pitch || config.google.tts.pitch,
      outputDir: options.outputDir || config.directories.temp,
      ...options,
    };

    this._initClient();
  }

  _initClient() {
    try {
      const credentialsPath = this.options.credentials;
      if (fs.existsSync(credentialsPath)) {
        process.env.GOOGLE_APPLICATION_CREDENTIALS = credentialsPath;
      }
      this.client = new TextToSpeechClient();
    } catch (error) {
      console.warn(`Google TTS 客户端初始化警告: ${error.message}`);
      console.warn('请确保 GOOGLE_APPLICATION_CREDENTIALS 环境变量已正确设置，或配置文件中包含有效的凭证路径');
    }
  }

  async synthesizeSpeech(text, options = {}) {
    if (!this.client) {
      throw new Error('Google TTS 客户端未初始化，请检查凭证配置');
    }

    const outputDir = options.outputDir || this.options.outputDir;
    const outputFileName = options.outputFileName || `tts_${helpers.generateUniqueId()}.mp3`;
    const outputPath = path.join(outputDir, outputFileName);

    helpers.ensureDirectory(outputDir);

    const request = {
      input: {
        text: text,
      },
      voice: {
        languageCode: options.languageCode || this.options.languageCode,
        name: options.voiceName || this.options.voiceName,
      },
      audioConfig: {
        audioEncoding: 'MP3',
        speakingRate: options.speakingRate || this.options.speakingRate,
        pitch: options.pitch || this.options.pitch,
        volumeGainDb: options.volumeGainDb || 0,
        sampleRateHertz: options.sampleRateHertz || 24000,
      },
    };

    try {
      const [response] = await this.client.synthesizeSpeech(request);
      fs.writeFileSync(outputPath, response.audioContent, 'binary');

      const audioInfo = await this._getAudioInfo(outputPath);

      return {
        success: true,
        text: text,
        audioPath: outputPath,
        filename: outputFileName,
        duration: audioInfo.duration,
        format: 'mp3',
      };
    } catch (error) {
      throw new Error(`TTS 合成失败: ${error.message}`);
    }
  }

  async synthesizeSpeechWithSSML(ssml, options = {}) {
    if (!this.client) {
      throw new Error('Google TTS 客户端未初始化，请检查凭证配置');
    }

    const outputDir = options.outputDir || this.options.outputDir;
    const outputFileName = options.outputFileName || `tts_${helpers.generateUniqueId()}.mp3`;
    const outputPath = path.join(outputDir, outputFileName);

    helpers.ensureDirectory(outputDir);

    const request = {
      input: {
        ssml: ssml,
      },
      voice: {
        languageCode: options.languageCode || this.options.languageCode,
        name: options.voiceName || this.options.voiceName,
      },
      audioConfig: {
        audioEncoding: 'MP3',
        speakingRate: options.speakingRate || this.options.speakingRate,
        pitch: options.pitch || this.options.pitch,
        volumeGainDb: options.volumeGainDb || 0,
        sampleRateHertz: options.sampleRateHertz || 24000,
      },
    };

    try {
      const [response] = await this.client.synthesizeSpeech(request);
      fs.writeFileSync(outputPath, response.audioContent, 'binary');

      const audioInfo = await this._getAudioInfo(outputPath);

      return {
        success: true,
        ssml: ssml,
        audioPath: outputPath,
        filename: outputFileName,
        duration: audioInfo.duration,
        format: 'mp3',
      };
    } catch (error) {
      throw new Error(`TTS 合成失败: ${error.message}`);
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

  async listVoices(languageCode = null) {
    if (!this.client) {
      throw new Error('Google TTS 客户端未初始化，请检查凭证配置');
    }

    try {
      const [response] = await this.client.listVoices({
        languageCode: languageCode || this.options.languageCode,
      });

      return {
        voices: response.voices.map(voice => ({
          name: voice.name,
          languageCodes: voice.languageCodes,
          ssmlGender: voice.ssmlGender,
          naturalSampleRateHertz: voice.naturalSampleRateHertz,
        })),
      };
    } catch (error) {
      throw new Error(`获取语音列表失败: ${error.message}`);
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

  createSSML(text, options = {}) {
    const {
      speakingRate = this.options.speakingRate,
      pitch = this.options.pitch,
      volume = 'default',
      breakTimes = [],
    } = options;

    let ssml = '<speak>';

    if (speakingRate !== 1.0 || pitch !== 0.0 || volume !== 'default') {
      const prosodyAttrs = [];
      if (speakingRate !== 1.0) prosodyAttrs.push(`rate="${speakingRate}"`);
      if (pitch !== 0.0) prosodyAttrs.push(`pitch="${pitch > 0 ? '+' : ''}${pitch}st"`);
      if (volume !== 'default') prosodyAttrs.push(`volume="${volume}"`);
      ssml += `<prosody ${prosodyAttrs.join(' ')}>`;
    }

    let processedText = text;
    breakTimes.forEach((breakTime, index) => {
      const placeholder = `__BREAK_${index}__`;
      if (processedText.includes(placeholder)) {
        const breakTag = `<break time="${breakTime}"/>`;
        processedText = processedText.replace(placeholder, breakTag);
      }
    });

    ssml += processedText;

    if (speakingRate !== 1.0 || pitch !== 0.0 || volume !== 'default') {
      ssml += '</prosody>';
    }

    ssml += '</speak>';

    return ssml;
  }
}

export default TTSService;