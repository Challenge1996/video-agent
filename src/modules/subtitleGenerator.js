import fs from 'fs-extra';
import path from 'path';
import config from '../config/index.js';
import helpers from '../utils/helpers.js';

class SubtitleGenerator {
  constructor(options = {}) {
    this.options = {
      outputDir: options.outputDir || config.directories.temp,
      defaultDurationPerChar: options.defaultDurationPerChar || 0.15,
      minDuration: options.minDuration || 1.0,
      maxDuration: options.maxDuration || 7.0,
      ...options,
    };
  }

  generateSRTFromText(text, options = {}) {
    const {
      startTime = 0,
      totalDuration = null,
      segmentBySentence = true,
      segmentByLength = false,
      maxCharsPerLine = 40,
    } = options;

    const segments = this._splitText(text, {
      segmentBySentence,
      segmentByLength,
      maxCharsPerLine,
    });

    const subtitles = this._calculateTimings(segments, {
      startTime,
      totalDuration,
    });

    return {
      segments: subtitles,
      srtContent: this._generateSRTContent(subtitles),
      count: subtitles.length,
    };
  }

  generateSRTFromTTSResults(ttsResults, options = {}) {
    const {
      startTime = 0,
      gapBetweenSegments = 0.1,
    } = options;

    const subtitles = [];
    let currentTime = startTime;

    for (let i = 0; i < ttsResults.length; i++) {
      const ttsResult = ttsResults[i];
      const duration = ttsResult.duration || this._estimateDuration(ttsResult.text);

      const subtitle = {
        index: i + 1,
        startTime: currentTime,
        endTime: currentTime + duration,
        duration: duration,
        text: ttsResult.text,
        ttsAudioPath: ttsResult.audioPath,
      };

      subtitles.push(subtitle);
      currentTime += duration + gapBetweenSegments;
    }

    return {
      segments: subtitles,
      srtContent: this._generateSRTContent(subtitles),
      count: subtitles.length,
      totalDuration: currentTime - gapBetweenSegments,
    };
  }

  async saveSRT(subtitleData, outputPath = null) {
    const outputDir = path.dirname(outputPath) || this.options.outputDir;
    const outputFileName = path.basename(outputPath) || `subtitle_${helpers.generateUniqueId()}.srt`;
    const fullOutputPath = path.join(outputDir, outputFileName);

    helpers.ensureDirectory(outputDir);

    let srtContent;
    if (typeof subtitleData === 'string') {
      srtContent = subtitleData;
    } else if (subtitleData.srtContent) {
      srtContent = subtitleData.srtContent;
    } else if (subtitleData.segments) {
      srtContent = this._generateSRTContent(subtitleData.segments);
    } else {
      throw new Error('无效的字幕数据格式');
    }

    fs.writeFileSync(fullOutputPath, srtContent, 'utf-8');

    return {
      success: true,
      path: fullOutputPath,
      filename: outputFileName,
      segmentCount: subtitleData.count || subtitleData.segments?.length || 0,
    };
  }

  parseSRT(srtContent) {
    const segments = [];
    const blocks = srtContent.trim().split(/\n\n+/);

    for (const block of blocks) {
      const lines = block.split('\n');
      if (lines.length < 3) continue;

      const index = parseInt(lines[0]);
      const timeLine = lines[1];
      const textLines = lines.slice(2).join('\n');

      const timeMatch = timeLine.match(/(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})/);
      if (!timeMatch) continue;

      const startTime = helpers.parseTimestamp(timeMatch[1]);
      const endTime = helpers.parseTimestamp(timeMatch[2]);

      segments.push({
        index: index,
        startTime: startTime,
        endTime: endTime,
        duration: endTime - startTime,
        text: textLines,
      });
    }

    return {
      segments: segments,
      count: segments.length,
      totalDuration: segments.length > 0 ? segments[segments.length - 1].endTime : 0,
    };
  }

  parseSRTFile(filePath) {
    if (!fs.existsSync(filePath)) {
      throw new Error(`SRT 文件不存在: ${filePath}`);
    }

    const srtContent = fs.readFileSync(filePath, 'utf-8');
    return this.parseSRT(srtContent);
  }

  mergeSubtitles(subtitleGroups, options = {}) {
    const {
      timeOffset = 0,
      gapBetweenGroups = 0,
    } = options;

    const allSegments = [];
    let currentIndex = 1;
    let currentTime = timeOffset;

    for (let groupIndex = 0; groupIndex < subtitleGroups.length; groupIndex++) {
      const group = subtitleGroups[groupIndex];
      const segments = group.segments || group;

      if (groupIndex > 0 && gapBetweenGroups > 0) {
        currentTime += gapBetweenGroups;
      }

      for (const segment of segments) {
        const newSegment = {
          ...segment,
          index: currentIndex,
          startTime: currentTime,
          endTime: currentTime + segment.duration,
        };
        allSegments.push(newSegment);
        currentTime = newSegment.endTime;
        currentIndex++;
      }
    }

    return {
      segments: allSegments,
      srtContent: this._generateSRTContent(allSegments),
      count: allSegments.length,
      totalDuration: currentTime,
    };
  }

  adjustTiming(subtitleData, options = {}) {
    const {
      offset = 0,
      speedFactor = 1.0,
      newStartTime = null,
    } = options;

    const segments = subtitleData.segments || subtitleData;
    const adjustedSegments = [];

    let baseOffset = offset;
    if (newStartTime !== null && segments.length > 0) {
      baseOffset = newStartTime - segments[0].startTime;
    }

    for (const segment of segments) {
      const adjustedStartTime = (segment.startTime + baseOffset) * speedFactor;
      const adjustedDuration = segment.duration * speedFactor;

      adjustedSegments.push({
        ...segment,
        startTime: adjustedStartTime,
        endTime: adjustedStartTime + adjustedDuration,
        duration: adjustedDuration,
      });
    }

    return {
      segments: adjustedSegments,
      srtContent: this._generateSRTContent(adjustedSegments),
      count: adjustedSegments.length,
      totalDuration: adjustedSegments.length > 0 ? adjustedSegments[adjustedSegments.length - 1].endTime : 0,
    };
  }

  _splitText(text, options = {}) {
    const {
      segmentBySentence = true,
      segmentByLength = false,
      maxCharsPerLine = 40,
    } = options;

    let segments = [];

    if (segmentBySentence) {
      const sentenceEndings = /[。！？.!?]+/g;
      const sentences = text.split(sentenceEndings).filter(s => s.trim());
      const endings = text.match(sentenceEndings) || [];

      for (let i = 0; i < sentences.length; i++) {
        const sentence = sentences[i].trim() + (endings[i] || '');
        if (sentence) {
          if (segmentByLength && sentence.length > maxCharsPerLine) {
            const subSegments = this._splitByLength(sentence, maxCharsPerLine);
            segments.push(...subSegments);
          } else {
            segments.push(sentence);
          }
        }
      }
    } else if (segmentByLength) {
      segments = this._splitByLength(text, maxCharsPerLine);
    } else {
      segments = [text];
    }

    return segments;
  }

  _splitByLength(text, maxLength) {
    const segments = [];
    let remaining = text;

    while (remaining.length > 0) {
      if (remaining.length <= maxLength) {
        segments.push(remaining);
        break;
      }

      let splitIndex = maxLength;
      const lastSpace = remaining.substring(0, maxLength).lastIndexOf(' ');
      const lastChineseBreak = remaining.substring(0, maxLength).lastIndexOf('，');

      if (lastChineseBreak > maxLength * 0.5) {
        splitIndex = lastChineseBreak + 1;
      } else if (lastSpace > maxLength * 0.5) {
        splitIndex = lastSpace + 1;
      }

      segments.push(remaining.substring(0, splitIndex).trim());
      remaining = remaining.substring(splitIndex).trim();
    }

    return segments;
  }

  _calculateTimings(segments, options = {}) {
    const {
      startTime = 0,
      totalDuration = null,
    } = options;

    const subtitles = [];
    let currentTime = startTime;

    const totalChars = segments.reduce((sum, s) => sum + s.length, 0);
    let calculatedDurations;

    if (totalDuration) {
      const durationPerChar = totalDuration / totalChars;
      calculatedDurations = segments.map(s => Math.max(
        this.options.minDuration,
        Math.min(this.options.maxDuration, s.length * durationPerChar)
      ));
    } else {
      calculatedDurations = segments.map(s => Math.max(
        this.options.minDuration,
        Math.min(this.options.maxDuration, s.length * this.options.defaultDurationPerChar)
      ));
    }

    for (let i = 0; i < segments.length; i++) {
      const duration = calculatedDurations[i];
      subtitles.push({
        index: i + 1,
        startTime: currentTime,
        endTime: currentTime + duration,
        duration: duration,
        text: segments[i],
      });
      currentTime += duration;
    }

    return subtitles;
  }

  _estimateDuration(text) {
    return Math.max(
      this.options.minDuration,
      Math.min(this.options.maxDuration, text.length * this.options.defaultDurationPerChar)
    );
  }

  _generateSRTContent(segments) {
    return segments
      .map(segment => {
        const startTimeStr = helpers.formatTimestamp(segment.startTime);
        const endTimeStr = helpers.formatTimestamp(segment.endTime);
        return `${segment.index}\n${startTimeStr} --> ${endTimeStr}\n${segment.text}\n`;
      })
      .join('\n');
  }
}

export default SubtitleGenerator;