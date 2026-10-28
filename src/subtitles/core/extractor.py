#!/usr/bin/env python3
"""Core subtitle extraction logic.

Handles subtitle extraction from video files using FFmpeg.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Optional

try:
    import ffmpeg
except ImportError:
    ffmpeg = None

if sys.platform == 'win32':
    # ffmpeg-python spawns ffmpeg/ffprobe without CREATE_NO_WINDOW and does
    # not expose creationflags, so each call flashes a console window in the
    # GUI exe. Patch Popen so every child process starts windowless.
    _CREATE_NO_WINDOW = 0x08000000
    _orig_popen_init = subprocess.Popen.__init__

    def _no_window_popen_init(self, *args, **kwargs):
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | _CREATE_NO_WINDOW
        _orig_popen_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _no_window_popen_init

from subtitles.core.cleaner import clean_srt_file, unique_text_score
from subtitles.utils.config import get_config
from subtitles.utils.logging_config import get_logger

logger = get_logger()


def _is_typesetting_track(stream: Dict) -> bool:
    """Signs/karaoke tracks carry almost no dialogue, only styled overlays."""
    title = str(stream.get('title', '')).lower()
    return 'sign' in title or 'song' in title


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
                    'title': s.get('tags', {}).get('title', f'Subtitle {subtitle_index}')
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


def extract_subtitles_by_language(video_path: Path, output_path: Path, language_codes: List[str]) -> bool:
    """Extract subtitles in a specific language from video.

    Args:
        video_path: Path to the video file
        output_path: Path to save the extracted subtitles
        language_codes: List of language codes to search for (e.g., ['es', 'spa'])

    Returns:
        True if extraction succeeded, False otherwise
    """
    if not has_embedded_subtitles(video_path):
        return False
    
    subtitle_streams = get_subtitle_streams(video_path)
    if not subtitle_streams:
        return False
    
    # Find streams matching the language codes
    matching_streams = [
        s for s in subtitle_streams
        if str(s['language']).lower() in [code.lower() for code in language_codes]
    ]
    
    if matching_streams:
        preferred = [s for s in matching_streams if not _is_typesetting_track(s)] or matching_streams
        stream_idx = preferred[0]['subtitle_index']
        logger.info(f"Found subtitle stream in target language (index {stream_idx})")
        if extract_subtitles(video_path, output_path, stream_idx):
            if output_path.suffix.lower() == '.srt':
                clean_srt_file(output_path)
            return True

    return False


def extract_english_subtitles(video_path: Path, temp_path: Path) -> Optional[int]:
    """Extract English subtitles from video.

    Args:
        video_path: Path to the video file
        temp_path: Temporary path to save the extracted subtitles

    Returns:
        Unique dialogue character count if successful, None otherwise
    """
    config = get_config()

    if not has_embedded_subtitles(video_path):
        return None

    subtitle_streams = get_subtitle_streams(video_path)
    if not subtitle_streams:
        return None

    english_streams = [
        s for s in subtitle_streams
        if str(s['language']).lower() in config.english_codes
    ]

    if not english_streams:
        return None

    # Only fall back to signs/karaoke tracks when no dialogue track exists
    candidates = [s for s in english_streams if not _is_typesetting_track(s)] or english_streams

    # Try each candidate stream, preferring the one with most unique dialogue
    best_content = None
    best_score = 0

    for stream in candidates:
        stream_idx = stream['subtitle_index']

        if extract_subtitles(video_path, temp_path, stream_idx):
            try:
                content = temp_path.read_text(encoding="utf-8", errors="ignore")
                score = unique_text_score(content)
                logger.debug(f"Stream {stream_idx}: {score} unique dialogue characters")

                if score > best_score:
                    best_score = score
                    best_content = content

            except Exception:
                pass

    if best_content is None:
        return None

    # The loop leaves the last extracted stream on disk; restore the best one
    temp_path.write_text(best_content, encoding='utf-8')
    return best_score


def extract_spanish_subtitles(video_path: Path, output_path: Path) -> bool:
    """Extract Spanish subtitles from video if available.

    Args:
        video_path: Path to the video file
        output_path: Path to save the Spanish subtitles

    Returns:
        True if extraction succeeded, False otherwise
    """
    config = get_config()
    
    if not has_embedded_subtitles(video_path):
        return False
    
    subtitle_streams = get_subtitle_streams(video_path)
    if not subtitle_streams:
        return False
    
    spanish_streams = [
        s for s in subtitle_streams
        if str(s['language']).lower() in config.spanish_codes
    ]
    
    if spanish_streams:
        preferred = [s for s in spanish_streams if not _is_typesetting_track(s)] or spanish_streams
        stream_idx = preferred[0]['subtitle_index']
        logger.info(f"Found Spanish subtitle stream (index {stream_idx})")
        if extract_subtitles(video_path, output_path, stream_idx):
            if output_path.suffix.lower() == '.srt':
                clean_srt_file(output_path)
            return True

    return False
