#!/usr/bin/env python3
"""Core subtitle download logic.

Handles downloading subtitles using subliminal library.
"""

from pathlib import Path
from typing import Optional

from subliminal import download_best_subtitles, region, scan_video
from subliminal.extensions import provider_manager
from subliminal.video import Video
import babelfish

from subtitles.core.synchronizer import auto_synchronize_srt
from subtitles.utils.config import get_config
from subtitles.utils.logging_config import get_logger

logger = get_logger()

# Subliminal providers (addic7ed, tvsubtitles, opensubtitles.com, ...) cache
# lookups through this dogpile region; it must be configured once per process.
try:
    region.configure('dogpile.cache.memory', replace_existing_backend=True)
except Exception as e:  # pragma: no cover - already configured
    logger.debug(f"Cache region already configured: {e}")


def _get_providers() -> Optional[list]:
    """Providers to query, from config, filtered to those subliminal knows."""
    wanted = get_config().download_providers
    available = set(provider_manager.names())
    providers = [p for p in wanted if p in available]
    return providers or None


def download_subtitle(video_path: Path, language: str, timeout: int = 30, use_temp: bool = False) -> Optional[Path]:
    """Download subtitle using subliminal library.

    Args:
        video_path: Path to video file
        language: Language code (e.g., 'en', 'es')
        timeout: Timeout in seconds for download operation
        use_temp: If True, use temp filename for download

    Returns:
        Path to downloaded subtitle or None if failed
    """
    output_dir = video_path.parent

    logger.info(f"Attempting to download {language} subtitles for {video_path.name}...")

    try:
        try:
            # name= guesses from the filename only, so folder names in the
            # path can't pollute the title/season/episode detection
            video = scan_video(str(video_path), name=video_path.name)
        except ValueError:
            # Unrecognized/too small file: fall back to name-based guessing
            video = Video.fromname(video_path.name)

        # Normalize Google-style codes (e.g. 'zh-CN', legacy 'iw') to ISO alpha2
        lang_code = language.split('-')[0].lower()
        if lang_code == 'iw':
            lang_code = 'he'
        lang = babelfish.Language.fromalpha2(lang_code)

        best = download_best_subtitles({video}, {lang}, providers=_get_providers())
        subtitles = best.get(video) or []
        subtitle = next((s for s in subtitles if s.content), None)

        if subtitle:
            if use_temp:
                final_srt = output_dir / f"{video_path.stem}.temp.{language}.srt"
            else:
                final_srt = output_dir / f"{video_path.stem}.srt"

            text = subtitle.text
            if text:
                final_srt.write_text(text, encoding='utf-8')
            elif isinstance(subtitle.content, bytes):
                final_srt.write_bytes(subtitle.content)
            else:
                final_srt.write_text(subtitle.content, encoding='utf-8')

            logger.info(f"Downloaded from {subtitle.provider_name}: {final_srt.name}")

            try:
                auto_synchronize_srt(video_path, final_srt)
            except Exception as e:
                logger.warning(f"Auto-sync skipped: {e}")

            return final_srt

        logger.info(f"No subtitles found for {language}")
        return None

    except Exception as e:
        logger.error(f"Subliminal error: {e}")
        return None
