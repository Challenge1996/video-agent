import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src_py.config.config import config
from src_py.utils.helpers import helpers


@dataclass
class SubtitleSegment:
    index: int
    start_time: float
    end_time: float
    duration: float
    text: str
    tts_audio_path: Optional[str] = None


@dataclass
class SubtitleResult:
    segments: List[SubtitleSegment]
    srt_content: str
    count: int
    total_duration: float = 0.0


class SubtitleGenerator:
    def __init__(self, options: Optional[Dict[str, Any]] = None):
        options = options or {}
        self.options = {
            'output_dir': options.get('output_dir', config.temp_dir),
            'default_duration_per_char': options.get('default_duration_per_char', 0.15),
            'min_duration': options.get('min_duration', 1.0),
            'max_duration': options.get('max_duration', 7.0),
            **options,
        }

    def generate_srt_from_text(self, text: str, options: Optional[Dict[str, Any]] = None) -> SubtitleResult:
        options = options or {}
        start_time = options.get('start_time', 0.0)
        total_duration = options.get('total_duration')
        segment_by_sentence = options.get('segment_by_sentence', True)
        segment_by_length = options.get('segment_by_length', False)
        max_chars_per_line = options.get('max_chars_per_line', 40)

        segments = self._split_text(text, {
            'segment_by_sentence': segment_by_sentence,
            'segment_by_length': segment_by_length,
            'max_chars_per_line': max_chars_per_line,
        })

        subtitles = self._calculate_timings(segments, {
            'start_time': start_time,
            'total_duration': total_duration,
        })

        return SubtitleResult(
            segments=subtitles,
            srt_content=self._generate_srt_content(subtitles),
            count=len(subtitles)
        )

    def generate_srt_from_tts_results(self, tts_results: List[Dict[str, Any]], 
                                        options: Optional[Dict[str, Any]] = None) -> SubtitleResult:
        options = options or {}
        start_time = options.get('start_time', 0.0)
        gap_between_segments = options.get('gap_between_segments', 0.1)

        subtitles = []
        current_time = start_time

        for i, tts_result in enumerate(tts_results):
            duration = tts_result.get('duration') or self._estimate_duration(tts_result.get('text', ''))

            subtitle = SubtitleSegment(
                index=i + 1,
                start_time=current_time,
                end_time=current_time + duration,
                duration=duration,
                text=tts_result.get('text', ''),
                tts_audio_path=tts_result.get('audio_path')
            )

            subtitles.append(subtitle)
            current_time += duration + gap_between_segments

        total_duration = current_time - gap_between_segments if subtitles else 0.0

        return SubtitleResult(
            segments=subtitles,
            srt_content=self._generate_srt_content(subtitles),
            count=len(subtitles),
            total_duration=total_duration
        )

    def save_srt(self, subtitle_data, output_path: Optional[str] = None) -> Dict[str, Any]:
        output_dir = os.path.dirname(output_path) if output_path else self.options['output_dir']
        output_filename = os.path.basename(output_path) if output_path else f"subtitle_{helpers.generate_unique_id()}.srt"
        full_output_path = os.path.join(output_dir, output_filename)

        helpers.ensure_directory(output_dir)

        srt_content = ''
        if isinstance(subtitle_data, str):
            srt_content = subtitle_data
        elif isinstance(subtitle_data, SubtitleResult):
            srt_content = subtitle_data.srt_content
        elif isinstance(subtitle_data, dict):
            if 'srt_content' in subtitle_data:
                srt_content = subtitle_data['srt_content']
            elif 'segments' in subtitle_data:
                srt_content = self._generate_srt_content(subtitle_data['segments'])

        if not srt_content:
            raise Exception('无效的字幕数据格式')

        with open(full_output_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)

        segment_count = 0
        if isinstance(subtitle_data, SubtitleResult):
            segment_count = subtitle_data.count
        elif isinstance(subtitle_data, dict):
            segment_count = subtitle_data.get('count', 0) or len(subtitle_data.get('segments', []))

        return {
            'success': True,
            'path': full_output_path,
            'filename': output_filename,
            'segment_count': segment_count
        }

    def parse_srt(self, srt_content: str) -> SubtitleResult:
        segments = []
        blocks = srt_content.strip().split('\n\n')

        for block in blocks:
            lines = block.split('\n')
            if len(lines) < 3:
                continue

            try:
                index = int(lines[0])
            except ValueError:
                continue

            time_line = lines[1]
            text_lines = '\n'.join(lines[2:])

            time_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', time_line)
            if not time_match:
                continue

            start_time = helpers.parse_timestamp(time_match.group(1))
            end_time = helpers.parse_timestamp(time_match.group(2))

            segments.append(SubtitleSegment(
                index=index,
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                text=text_lines
            ))

        total_duration = segments[-1].end_time if segments else 0.0

        return SubtitleResult(
            segments=segments,
            srt_content=self._generate_srt_content(segments),
            count=len(segments),
            total_duration=total_duration
        )

    def parse_srt_file(self, file_path: str) -> SubtitleResult:
        if not os.path.exists(file_path):
            raise Exception(f'SRT 文件不存在: {file_path}')

        with open(file_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()

        return self.parse_srt(srt_content)

    def merge_subtitles(self, subtitle_groups: List, options: Optional[Dict[str, Any]] = None) -> SubtitleResult:
        options = options or {}
        time_offset = options.get('time_offset', 0.0)
        gap_between_groups = options.get('gap_between_groups', 0.0)

        all_segments = []
        current_index = 1
        current_time = time_offset

        for group_index, group in enumerate(subtitle_groups):
            segments = []
            if isinstance(group, SubtitleResult):
                segments = group.segments
            elif isinstance(group, dict) and 'segments' in group:
                segments = group['segments']
            elif isinstance(group, list):
                segments = group

            if group_index > 0 and gap_between_groups > 0:
                current_time += gap_between_groups

            for segment in segments:
                new_segment = SubtitleSegment(
                    index=current_index,
                    start_time=current_time,
                    end_time=current_time + segment.duration,
                    duration=segment.duration,
                    text=segment.text,
                    tts_audio_path=getattr(segment, 'tts_audio_path', None)
                )
                all_segments.append(new_segment)
                current_time = new_segment.end_time
                current_index += 1

        total_duration = current_time if all_segments else 0.0

        return SubtitleResult(
            segments=all_segments,
            srt_content=self._generate_srt_content(all_segments),
            count=len(all_segments),
            total_duration=total_duration
        )

    def adjust_timing(self, subtitle_data, options: Optional[Dict[str, Any]] = None) -> SubtitleResult:
        options = options or {}
        offset = options.get('offset', 0.0)
        speed_factor = options.get('speed_factor', 1.0)
        new_start_time = options.get('new_start_time')

        segments = []
        if isinstance(subtitle_data, SubtitleResult):
            segments = subtitle_data.segments
        elif isinstance(subtitle_data, dict) and 'segments' in subtitle_data:
            segments = subtitle_data['segments']
        elif isinstance(subtitle_data, list):
            segments = subtitle_data

        adjusted_segments = []

        base_offset = offset
        if new_start_time is not None and segments:
            base_offset = new_start_time - segments[0].start_time * speed_factor

        for segment in segments:
            adjusted_start_time = segment.start_time * speed_factor + base_offset
            adjusted_duration = segment.duration * speed_factor

            adjusted_segments.append(SubtitleSegment(
                index=segment.index,
                start_time=adjusted_start_time,
                end_time=adjusted_start_time + adjusted_duration,
                duration=adjusted_duration,
                text=segment.text,
                tts_audio_path=getattr(segment, 'tts_audio_path', None)
            ))

        total_duration = adjusted_segments[-1].end_time if adjusted_segments else 0.0

        return SubtitleResult(
            segments=adjusted_segments,
            srt_content=self._generate_srt_content(adjusted_segments),
            count=len(adjusted_segments),
            total_duration=total_duration
        )

    def _split_text(self, text: str, options: Dict[str, Any]) -> List[str]:
        segment_by_sentence = options.get('segment_by_sentence', True)
        segment_by_length = options.get('segment_by_length', False)
        max_chars_per_line = options.get('max_chars_per_line', 40)

        segments = []

        if segment_by_sentence:
            sentence_endings = re.compile(r'([。！？.!?]+)')
            parts = sentence_endings.split(text)

            sentences = []
            endings = []

            for i in range(0, len(parts) - 1, 2):
                sentences.append(parts[i].strip())
                endings.append(parts[i + 1])

            if len(parts) % 2 == 1 and parts[-1].strip():
                sentences.append(parts[-1].strip())
                endings.append('')

            for i, sentence in enumerate(sentences):
                if not sentence:
                    continue
                sentence_with_ending = sentence + (endings[i] if i < len(endings) else '')
                if segment_by_length and len(sentence_with_ending) > max_chars_per_line:
                    sub_segments = self._split_by_length(sentence_with_ending, max_chars_per_line)
                    segments.extend(sub_segments)
                else:
                    segments.append(sentence_with_ending)
        elif segment_by_length:
            segments = self._split_by_length(text, max_chars_per_line)
        else:
            segments = [text]

        return segments

    def _split_by_length(self, text: str, max_length: int) -> List[str]:
        segments = []
        remaining = text

        while len(remaining) > 0:
            if len(remaining) <= max_length:
                segments.append(remaining)
                break

            split_index = max_length
            last_space = remaining[:max_length].rfind(' ')
            last_chinese_break = remaining[:max_length].rfind('，')

            if last_chinese_break > max_length * 0.5:
                split_index = last_chinese_break + 1
            elif last_space > max_length * 0.5:
                split_index = last_space + 1

            segments.append(remaining[:split_index].strip())
            remaining = remaining[split_index:].strip()

        return segments

    def _calculate_timings(self, segments: List[str], options: Dict[str, Any]) -> List[SubtitleSegment]:
        start_time = options.get('start_time', 0.0)
        total_duration = options.get('total_duration')

        subtitles = []
        current_time = start_time

        total_chars = sum(len(s) for s in segments)
        calculated_durations = []

        if total_duration:
            duration_per_char = total_duration / total_chars
            for s in segments:
                dur = max(
                    self.options['min_duration'],
                    min(self.options['max_duration'], len(s) * duration_per_char)
                )
                calculated_durations.append(dur)
        else:
            for s in segments:
                dur = max(
                    self.options['min_duration'],
                    min(self.options['max_duration'], len(s) * self.options['default_duration_per_char'])
                )
                calculated_durations.append(dur)

        for i, segment in enumerate(segments):
            duration = calculated_durations[i]
            subtitles.append(SubtitleSegment(
                index=i + 1,
                start_time=current_time,
                end_time=current_time + duration,
                duration=duration,
                text=segment
            ))
            current_time += duration

        return subtitles

    def _estimate_duration(self, text: str) -> float:
        return max(
            self.options['min_duration'],
            min(self.options['max_duration'], len(text) * self.options['default_duration_per_char'])
        )

    def _generate_srt_content(self, segments: List[SubtitleSegment]) -> str:
        lines = []
        for segment in segments:
            start_time_str = helpers.format_timestamp(segment.start_time)
            end_time_str = helpers.format_timestamp(segment.end_time)
            lines.append(f"{segment.index}\n{start_time_str} --> {end_time_str}\n{segment.text}\n")
        return '\n'.join(lines)
