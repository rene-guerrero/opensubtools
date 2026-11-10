#!/usr/bin/env python3
"""Core subtitle download logic.

Handles downloading subtitles using subliminal library.
"""

import subprocess
from pathlib import Path
from typing import Optional

from subliminal import ProviderPool, compute_score, region, scan_video
from subliminal.extensions import provider_manager
from subliminal.score import episode_scores, movie_scores
from subliminal.video import Episode, Video
import babelfish
import srt

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


_MAX_CANDIDATES = 5


def _min_score(video: Video) -> int:
    """Score a subtitle needs to be about this video: the series (or movie
    title) must match, plus season and episode, or the file hash."""
    if isinstance(video, Episode):
        return min(episode_scores['hash'],
                   episode_scores['series'] + episode_scores['season'] + episode_scores['episode'])
    return min(movie_scores['hash'], movie_scores['title'])


def _video_duration(video_path: Path) -> Optional[float]:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(video_path)],
            capture_output=True, text=True, timeout=30
        ).stdout.strip()
        return float(out)
    except Exception:
        return None


def _fits_video(subtitle, video_path: Path) -> bool:
    """Reject subtitles whose running time can't belong to this video.

    Mislabelled uploads (another show, a double episode, a movie cut) pass
    the name checks; their length gives them away.
    """
    duration = _video_duration(video_path)
    if not duration:
        return True
    try:
        cues = list(srt.parse(subtitle.text or ''))
    except Exception:
        return True
    if not cues:
        return False
    last = max(c.end for c in cues).total_seconds()
    if last > duration + 180 or last < duration * 0.5:
        logger.warning(
            f"Rejected subtitle from {subtitle.provider_name}: runs {last / 60:.0f} min "
            f"for a {duration / 60:.0f} min video"
        )
        return False
    return True


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

        # Without a floor, a failed download of the right show falls through
        # to anything sharing only season/episode numbers (another series).
        min_score = _min_score(video)
        subtitle = None
        with ProviderPool(providers=_get_providers(),
                          provider_configs=get_config().provider_configs) as pool:
            candidates = [
                (score, s) for s in pool.list_subtitles(video, {lang})
                if (score := compute_score(s, video)) >= min_score
            ]
            candidates.sort(key=lambda pair: pair[0], reverse=True)
            for _, candidate in candidates[:_MAX_CANDIDATES]:
                if pool.download_subtitle(candidate) and _fits_video(candidate, video_path):
                    subtitle = candidate
                    break

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
                # An English file is translated afterwards, so if its words
                # aren't what's spoken, the transcript is the better source.
                auto_synchronize_srt(video_path, final_srt, language=lang_code,
                                     allow_transcript=use_temp)
            except Exception as e:
                logger.warning(f"Auto-sync skipped: {e}")

            return final_srt

        logger.info(f"No subtitles found for {language}")
        return None

    except Exception as e:
        logger.error(f"Subliminal error: {e}")
        return None
