#!/usr/bin/env python3
"""Core subtitle extraction logic.

Handles subtitle extraction from video files using FFmpeg.
"""

from pathlib import Path
from typing import List, Dict, Optional

try:
    import ffmpeg
except ImportError:
    ffmpeg = None

from subtitles.utils.config import get_config
from subtitles.utils.logging_config import get_logger

logger = get_logger()


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


def extract_english_subtitles(video_path: Path, temp_path: Path) -> Optional[int]:
    """Extract English subtitles from video.

    Args:
        video_path: Path to the video file
        temp_path: Temporary path to save the extracted subtitles

    Returns:
        Character count if successful, None otherwise
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
    
    # Try each English stream, preferring the one with most content
    best_stream = None
    best_char_count = 0
    
    for stream in english_streams:
        stream_idx = stream['subtitle_index']
        
        if extract_subtitles(video_path, temp_path, stream_idx):
            try:
                content = temp_path.read_text(encoding="utf-8", errors="ignore")
                char_count = len(content)
                logger.debug(f"Stream {stream_idx}: {char_count} characters")
                
                if char_count > best_char_count:
                    best_char_count = char_count
                    best_stream = stream_idx
                    
            except Exception:
                pass
    
    return best_char_count if best_char_count > 0 else None


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
        stream_idx = spanish_streams[0]['subtitle_index']
        logger.info(f"Found Spanish subtitle stream (index {stream_idx})")
        return extract_subtitles(video_path, output_path, stream_idx)
    
    return False
