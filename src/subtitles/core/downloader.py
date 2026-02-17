#!/usr/bin/env python3
"""Core subtitle download logic.

Handles downloading subtitles using external tools like subliminal.
"""

import subprocess
from pathlib import Path
from typing import Optional

from subtitles.utils.logging_config import get_logger

logger = get_logger()


def download_subtitle(video_path: Path, language: str, timeout: int = 30) -> Optional[Path]:
    """Download subtitle using subliminal.

    Args:
        video_path: Path to video file
        language: Language code (e.g., 'en', 'es')
        timeout: Timeout in seconds for download operation

    Returns:
        Path to downloaded subtitle or None if failed
    """
    output_dir = video_path.parent

    cmd = [
        "subliminal",
        "download",
        "-l", language,
        "-v",
        str(video_path)
    ]

    logger.info(f"Attempting to download {language} subtitles...")

    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            cwd=output_dir, 
            timeout=timeout
        )
        logger.debug(f"Subliminal output: {result.stdout}")
    except subprocess.TimeoutExpired:
        logger.error(f"Subliminal timeout for language {language}")
        return None
    except FileNotFoundError:
        logger.error("Subliminal not found. Install with: pip install subliminal")
        return None
    except Exception as e:
        logger.debug(f"Subliminal error: {e}")
        return None

    # Subliminal typically names the file with .lang.srt extension
    expected_srt = output_dir / f"{video_path.stem}.{language}.srt"
    if expected_srt.exists():
        logger.info(f"Downloaded: {expected_srt.name}")
        return expected_srt

    # Fallback: look for any .srt file with similar name
    for srt_file in output_dir.glob(f"{video_path.stem}*.srt"):
        if srt_file != expected_srt:
            logger.info(f"Found alternative: {srt_file.name}")
        return srt_file

    logger.debug(f"No subtitles found for {language}")
    return None


def download_english_subtitle(video_path: Path) -> Optional[Path]:
    """Download English subtitles for video.

    Args:
        video_path: Path to video file

    Returns:
        Path to downloaded subtitle or None if failed
    """
    return download_subtitle(video_path, "en")


def download_spanish_subtitle(video_path: Path) -> Optional[Path]:
    """Download Spanish subtitles for video.

    Args:
        video_path: Path to video file

    Returns:
        Path to downloaded subtitle or None if failed
    """
    return download_subtitle(video_path, "es")
