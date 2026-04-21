import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '../../.env') });

const config = {
  google: {
    credentials: process.env.GOOGLE_APPLICATION_CREDENTIALS || './credentials/google-cloud-key.json',
    tts: {
      languageCode: process.env.GOOGLE_TTS_LANGUAGE_CODE || 'zh-CN',
      voiceName: process.env.GOOGLE_TTS_VOICE_NAME || 'zh-CN-Wavenet-A',
      speakingRate: parseFloat(process.env.GOOGLE_TTS_SPEAKING_RATE) || 1.0,
      pitch: parseFloat(process.env.GOOGLE_TTS_PITCH) || 0.0,
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
  },
  subtitle: {
    fontSize: 24,
    fontColor: 'white',
    backgroundColor: 'black@0.5',
    position: 'bottom',
    marginV: 40,
  },
};

export default config;