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

    expected_srt = output_dir / f"{video_path.stem}.{language}.srt"
    logger.info(f"Looking for: {expected_srt.name}")
    
    if expected_srt.exists():
        final_srt = output_dir / f"{video_path.stem}.srt"
        expected_srt.rename(final_srt)
        logger.info(f"Downloaded: {final_srt.name}")
        return final_srt

    # Check for any srt files
    srt_files = list(output_dir.glob(f"{video_path.stem}*.srt"))
    logger.info(f"Found SRT files: {[f.name for f in srt_files]}")
    
    for srt_file in srt_files:
        if srt_file.name != f"{video_path.stem}.srt":
            final_srt = output_dir / f"{video_path.stem}.srt"
            srt_file.rename(final_srt)
            logger.info(f"Found alternative: {final_srt.name}")
            return final_srt

    logger.info(f"No subtitles found for {language}")
    return None
