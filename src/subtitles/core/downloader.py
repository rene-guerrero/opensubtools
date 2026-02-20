#!/usr/bin/env python3
"""Core subtitle download logic.

Handles downloading subtitles using subliminal library.
"""

from pathlib import Path
from typing import Optional

from subliminal import scan_videos, list_subtitles, download_subtitles
import babelfish

from subtitles.utils.logging_config import get_logger

logger = get_logger()


def download_subtitle(video_path: Path, language: str, timeout: int = 30) -> Optional[Path]:
    """Download subtitle using subliminal library.

    Args:
        video_path: Path to video file
        language: Language code (e.g., 'en', 'es')
        timeout: Timeout in seconds for download operation

    Returns:
        Path to downloaded subtitle or None if failed
    """
    output_dir = video_path.parent

    logger.info(f"Attempting to download {language} subtitles...")

    try:
        videos = scan_videos(str(video_path.parent))
        
        if not videos:
            logger.error("No video found")
            return None
        
        video = videos[0]
        lang = babelfish.Language.fromalpha2(language)
        
        subtitles = list_subtitles({video}, {lang})
        
        if video in subtitles and subtitles[video]:
            subtitle = subtitles[video][0]
            
            download_subtitles([subtitle])
            
            if subtitle.content:
                final_srt = output_dir / f"{video_path.stem}.srt"
                
                if isinstance(subtitle.content, bytes):
                    final_srt.write_bytes(subtitle.content)
                else:
                    final_srt.write_text(subtitle.content, encoding='utf-8')
                
                logger.info(f"Downloaded: {final_srt.name}")
                return final_srt
        
        logger.info(f"No subtitles found for {language}")
        return None
        
    except Exception as e:
        logger.error(f"Subliminal error: {e}")
        return None
