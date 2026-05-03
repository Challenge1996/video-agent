import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '../../.env') });

const config = {
  tts: {
    provider: process.env.TTS_PROVIDER || 'minimax',
  },
  google: {
    credentials: process.env.GOOGLE_APPLICATION_CREDENTIALS || './credentials/google-cloud-key.json',
    tts: {
      languageCode: process.env.GOOGLE_TTS_LANGUAGE_CODE || 'zh-CN',
      voiceName: process.env.GOOGLE_TTS_VOICE_NAME || 'zh-CN-Wavenet-A',
      speakingRate: parseFloat(process.env.GOOGLE_TTS_SPEAKING_RATE) || 1.0,
      pitch: parseFloat(process.env.GOOGLE_TTS_PITCH) || 0.0,
    },
  },
  minimax: {
    apiKey: process.env.MINIMAX_API_KEY || '',
    groupId: process.env.MINIMAX_GROUP_ID || '',
    baseUrl: process.env.MINIMAX_BASE_URL || 'https://api.minimax.chat/v1/t2a_v2',
    model: process.env.MINIMAX_MODEL || 'speech-2.8-hd',
    tts: {
      voiceId: process.env.MINIMAX_VOICE_ID || 'male-qn-qingse',
      speed: parseFloat(process.env.MINIMAX_SPEED) || 1.0,
      vol: parseFloat(process.env.MINIMAX_VOL) || 1.0,
      pitch: parseFloat(process.env.MINIMAX_PITCH) || 0.0,
      emotion: process.env.MINIMAX_EMOTION || 'happy',
      sampleRate: parseInt(process.env.MINIMAX_SAMPLE_RATE) || 32000,
      bitrate: parseInt(process.env.MINIMAX_BITRATE) || 128000,
      format: process.env.MINIMAX_FORMAT || 'mp3',
      channel: parseInt(process.env.MINIMAX_CHANNEL) || 1,
    },
  },
  ffmpeg: {
    path: process.env.FFMPEG_PATH || 'ffmpeg',
    ffprobePath: process.env.FFPROBE_PATH || 'ffprobe',
  },
  directories: {
    output: process.env.OUTPUT_DIR || './output',
    temp: process.env.TEMP_DIR || './temp',
  },
  video: {
    defaultSegmentDuration: 30,
    defaultResolution: '1920x1080',
    defaultFps: 30,
  },
  audio: {
    backgroundMusicVolume: 0.3,
    ttsVolume: 1.0,
    duckingAmount: 0.15,
    fadeDuration: 1.0,
    videoOriginalVolumeWithTTS: 0.0,
    backgroundMusicVolumeWithTTS: 0.15,
    backgroundMusicVolumeWithoutTTS: 0.2,
    videoOriginalSilenceThreshold: -50,
  },
  subtitle: {
    fontSize: 24,
    fontColor: 'white',
    backgroundColor: 'black@0.5',
    position: 'bottom',
    marginV: 40,
  },
  sticker: {
    defaultOpacity: 1.0,
    defaultScale: 1.0,
    defaultPosition: 'top-left',
  },
};

export default config;