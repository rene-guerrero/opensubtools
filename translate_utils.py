#!/usr/bin/env python3
"""Shared utilities for translating English text to Spanish.
Includes helpers for language detection, batch translation, and video analysis.
"""
from pathlib import Path
from typing import List, Dict, Optional
import tempfile
import os

try:
    import ffmpeg
except ImportError:
    ffmpeg = None

# Default delimiter used to join multiple texts for batch translation
DEFAULT_DELIM = "\n|||SUBTITLE_DELIMITER|||\n"

def is_english_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    low = s.lower()
    english_keywords = [
        " the ", " and ", " to ", " of ", " in ",
        " is ", " are ", " was ", " were ", " that ", " this ", " with "
    ]
    if any(k in low for k in english_keywords) and sum(1 for ch in s if ch.isalpha()) / max(len(s), 1) > 0.4:
        return True
    letters = sum(1 for ch in s if ch.isalpha())
    ratio = letters / max(len(s), 1)
    return ratio > 0.6

def translate_batch_text(texts: List[str], translator, max_retries: int = 3, delimiter: str = DEFAULT_DELIM) -> List[str]:
    batch = delimiter.join(texts)
    for attempt in range(max_retries):
        try:
            translated = translator.translate(batch)
            parts = translated.split(delimiter)
            return [p.strip() for p in parts]
        except Exception:
            if attempt == max_retries - 1:
                return texts
            continue
    return texts

def translate_text(text: str, translator, max_retries: int = 3) -> str:
    if not text or not text.strip():
        return text
    for attempt in range(max_retries):
        try:
            return translator.translate(text)
        except Exception:
            if attempt == max_retries - 1:
                return text
            continue
    return text

def batch_by_size(lines: List[str], max_chars: int, delimiter: str = DEFAULT_DELIM) -> List[List[str]]:
    batches: List[List[str]] = []
    current: List[str] = []
    current_len = 0
    for line in lines:
        add_len = len(line)
        if current:
            add_len += len(delimiter)
        if current and (current_len + add_len) > max_chars:
            batches.append(current)
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += add_len
    if current:
        batches.append(current)
    return batches

def has_embedded_subtitles(video_path: Path) -> bool:
    """Check if video has embedded subtitles using ffmpeg."""
    if ffmpeg is None:
        return False
    try:
        probe = ffmpeg.probe(str(video_path))
        streams = probe.get('streams', [])
        for stream in streams:
            if stream.get('codec_type') == 'subtitle':
                return True
        return False
    except Exception:
        return False

def get_subtitle_streams(video_path: Path) -> List[Dict]:
    """Get subtitle streams info from video.

    Returns:
        List of dicts with keys: subtitle_index, codec, language, title
    """
    if ffmpeg is None:
        return []
    try:
        probe = ffmpeg.probe(str(video_path))
        streams = probe.get('streams', [])
        subtitle_streams = []
        for s in streams:
            if s.get('codec_type') == 'subtitle':
                subtitle_index = len(subtitle_streams)
                subtitle_streams.append({
                    'subtitle_index': subtitle_index,
                    'codec': s.get('codec_name', 'unknown'),
                    'language': s.get('tags', {}).get('language', 'unknown'),
                    'title': s.get('tags', {}).get('title', f'Subtítulo {subtitle_index}')
                })
        return subtitle_streams
    except Exception:
        return []

def extract_subtitles(video_path: Path, output_path: Path, stream_index: int = 0) -> bool:
    """Extract subtitles from video using ffmpeg.

    Args:
        video_path: Path to the video file
        output_path: Path where to save the .srt file
        stream_index: Index of the subtitle stream to extract (default: 0)

    Returns:
        True if extraction succeeded, False otherwise
    """
    if ffmpeg is None:
        return False
    try:
        stream = ffmpeg.input(str(video_path))
        stream = ffmpeg.output(stream, str(output_path), map=f'0:s:{stream_index}')
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        return True
    except Exception:
        return False
