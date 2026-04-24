import { VideoComposer, TTSService, SubtitleGenerator, VideoSplitter, BackgroundMusicService } from './src/lib.js';

async function example1_basicCompose() {
  console.log('=== 示例 1: 基本视频合成 ===');
  
  const composer = new VideoComposer();
  
  try {
    const result = await composer.composeVideo({
      videoPath: './input/video.mp4',
      textContent: '欢迎使用视频剪辑 Agent。这是一个功能强大的工具，可以帮助您自动完成视频剪辑任务。',
      backgroundMusicPath: './input/bgm.mp3',
      outputFileName: 'my_first_video',
      addTTS: true,
      addSubtitles: true,
      addBackgroundMusic: true,
    });
    
    console.log('视频合成成功！');
    console.log('输出文件:', result.outputPath);
  } catch (error) {
    console.error('视频合成失败:', error.message);
  }
}

async function example2_splitVideo() {
  console.log('\n=== 示例 2: 视频分割 ===');
  
  const splitter = new VideoSplitter({
    segmentDuration: 30,
  });
  
  try {
    const result = await splitter.splitVideo('./input/video.mp4');
    
    console.log('视频分割成功！');
    console.log('分割片段数:', result.segmentCount);
    
    result.segments.forEach((segment, index) => {
      console.log(`片段 ${index + 1}: ${segment.filename} (${segment.duration.toFixed(2)}秒)`);
    });
  } catch (error) {
    console.error('视频分割失败:', error.message);
  }
}

async function example3_ttsSynthesis() {
  console.log('\n=== 示例 3: TTS 语音合成 ===');
  
  const ttsService = new TTSService({
    languageCode: 'zh-CN',
    voiceName: 'zh-CN-Wavenet-A',
  });
  
  try {
    const result = await ttsService.synthesizeSpeech(
      '你好，这是 Google 文本转语音服务的测试。现在你可以听到清晰的语音了。'
    );
    
    console.log('TTS 合成成功！');
    console.log('音频文件:', result.audioPath);
    console.log('音频时长:', result.duration.toFixed(2), '秒');
  } catch (error) {
    console.error('TTS 合成失败:', error.message);
  }
}

async function example4_subtitleGeneration() {
  console.log('\n=== 示例 4: 字幕生成 ===');
  
  const subtitleGenerator = new SubtitleGenerator();
  
  try {
    const text = '欢迎使用视频剪辑 Agent。这是一个功能强大的工具。它可以帮助您自动完成视频剪辑任务。包括视频分割、TTS语音合成、字幕添加和背景音乐处理。';
    
    const result = subtitleGenerator.generateSRTFromText(text, {
      totalDuration: 30,
      segmentBySentence: true,
    });
    
    console.log('字幕生成成功！');
    console.log('字幕数量:', result.count);
    console.log('\nSRT 内容预览:');
    console.log(result.srtContent);
    
    await subtitleGenerator.saveSRT(result, './output/subtitle.srt');
    console.log('\n字幕已保存到: ./output/subtitle.srt');
  } catch (error) {
    console.error('字幕生成失败:', error.message);
  }
}

async function example5_backgroundMusic() {
  console.log('\n=== 示例 5: 背景音乐处理 ===');
  
  const bgmService = new BackgroundMusicService({
    defaultVolume: 0.3,
  });
  
  try {
    const result = await bgmService.loopAudioToDuration(
      './input/bgm.mp3',
      60,
      {
        volume: 0.3,
        fadeIn: 2,
        fadeOut: 2,
      }
    );
    
    console.log('背景音乐处理成功！');
    console.log('输出文件:', result.outputPath);
    console.log('目标时长:', result.targetDuration, '秒');
  } catch (error) {
    console.error('背景音乐处理失败:', error.message);
  }
}

async function example6_splitAndCompose() {
  console.log('\n=== 示例 6: 分割后合成 ===');
  
  const composer = new VideoComposer();
  
  try {
    const result = await composer.splitAndCompose({
      videoPath: './input/video.mp4',
      segmentDuration: 30,
      textContent: [
        '第一段的解说文字。',
        '第二段的解说文字。',
        '第三段的解说文字。',
      ],
      backgroundMusicPath: './input/bgm.mp3',
      outputFileName: 'segmented_video',
    });
    
    console.log('分割后合成成功！');
    console.log('输出文件:', result.outputPath);
  } catch (error) {
    console.error('分割后合成失败:', error.message);
  }
}

async function main() {
  console.log('视频剪辑 Agent 使用示例\n');
  console.log('请确保已创建 input 目录并放置测试文件:');
  console.log('  - input/video.mp4 (测试视频)');
  console.log('  - input/bgm.mp3 (测试背景音乐)');
  console.log('\n取消注释以下示例函数来运行:');
  
  // 取消注释以下行来运行示例
  // await example1_basicCompose();
  // await example2_splitVideo();
  // await example3_ttsSynthesis();
  // await example4_subtitleGeneration();
  // await example5_backgroundMusic();
  // await example6_splitAndCompose();
}

main().catch(console.error);