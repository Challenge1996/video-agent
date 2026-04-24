import os
import re
import time
import random
import string
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


def ensure_directory(dir_path: str) -> str:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    return dir_path


def generate_unique_id() -> str:
    timestamp = int(time.time() * 1000)
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=9))
    return f"{timestamp}-{random_str}"


def format_timestamp(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    hrs = total_ms // 3600000
    remaining = total_ms % 3600000
    mins = remaining // 60000
    remaining_after_mins = remaining % 60000
    secs = remaining_after_mins // 1000
    ms = remaining_after_mins % 1000

    return f"{str(hrs).zfill(2)}:{str(mins).zfill(2)}:{str(secs).zfill(2)},{str(ms).zfill(3)}"


def parse_timestamp(timestamp: str) -> float:
    match = re.match(r'(\d+):(\d+):(\d+),(\d+)', timestamp)
    if not match:
        return 0.0

    hrs, mins, secs, ms = map(int, match.groups())
    return hrs * 3600 + mins * 60 + secs + ms / 1000.0


def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def get_file_name_without_extension(filename: str) -> str:
    return Path(filename).stem


def sanitize_filename(filename: str) -> str:
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    sanitized = re.sub(r'\s+', '_', sanitized)
    return sanitized.lower()


def calculate_video_segments(total_duration: float, segment_duration: float) -> List[Dict[str, Any]]:
    segments = []
    current_time = 0.0
    segment_index = 0

    while current_time < total_duration:
        end_time = min(current_time + segment_duration, total_duration)
        segments.append({
            'index': segment_index,
            'start_time': current_time,
            'end_time': end_time,
            'duration': end_time - current_time,
        })
        current_time = end_time
        segment_index += 1

    return segments


def format_duration(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hrs > 0:
        return f"{hrs}:{str(mins).zfill(2)}:{str(secs).zfill(2)}"
    return f"{mins}:{str(secs).zfill(2)}"


def sleep(ms: int):
    time.sleep(ms / 1000.0)


def split_text_for_tts(text: str, max_chars_per_segment: int = 500, split_by_sentence: bool = True) -> List[str]:
    if not split_by_sentence:
        segments = []
        for i in range(0, len(text), max_chars_per_segment):
            segments.append(text[i:i + max_chars_per_segment])
        return [s for s in segments if s]

    sentence_endings = re.compile(r'([。！？.!?]+)')
    parts = sentence_endings.split(text)

    segments = []
    current_segment = ''

    for i in range(0, len(parts) - 1, 2):
        sentence = parts[i].strip()
        ending = parts[i + 1]

        if not sentence:
            continue

        if len(current_segment) + len(sentence) + len(ending) > max_chars_per_segment and current_segment:
            segments.append(current_segment.strip())
            current_segment = sentence + ending
        else:
            current_segment += sentence + ending

    if current_segment.strip():
        segments.append(current_segment.strip())

    return [s for s in segments if s]


class Helpers:
    ensure_directory = staticmethod(ensure_directory)
    generate_unique_id = staticmethod(generate_unique_id)
    format_timestamp = staticmethod(format_timestamp)
    parse_timestamp = staticmethod(parse_timestamp)
    get_file_extension = staticmethod(get_file_extension)
    get_file_name_without_extension = staticmethod(get_file_name_without_extension)
    sanitize_filename = staticmethod(sanitize_filename)
    calculate_video_segments = staticmethod(calculate_video_segments)
    format_duration = staticmethod(format_duration)
    sleep = staticmethod(sleep)
    split_text_for_tts = staticmethod(split_text_for_tts)


helpers = Helpers()
