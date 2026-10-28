#!/usr/bin/env python3
"""CLI for subtitle generation.

Generate subtitles for a video file by:
1. Finding local .srt files
2. Extracting embedded subtitles
3. Downloading from online sources
4. Translating if needed

Usage:
  python -m subtitles.cli.generate "path/to/video.mp4"
"""

import argparse
import sys
from pathlib import Path

from subtitles.core.downloader import download_subtitle
from subtitles.core.extractor import (
    extract_english_subtitles,
    extract_subtitles_by_language
)
from subtitles.core.translator import find_and_translate_local_srt, translate_srt_file
from subtitles.utils.config import get_config, load_config, LANGUAGE_CODE_MAP
from subtitles.utils.logging_config import get_logger

logger = get_logger()


def validate_video_path(path_str: str) -> Path:
    """Validate and normalize video file path."""
    path_str = path_str.strip().strip('"\'')
    video_path = Path(path_str)

    # Try to find the file with case-insensitive matching
    if video_path.parent.exists():
        for f in video_path.parent.glob('*'):
            if f.name.lower() == video_path.name.lower():
                return f

    # If nothing worked, check standard methods
    if video_path.exists():
        return video_path

    logger.error(f"File not found: {video_path}")
    sys.exit(1)


def generate_subtitles_for_video(video_path: Path, output_srt: Path, target_lang: str = 'es') -> bool:
    """Try all methods to get subtitles for a video.

    Tries in order:
    1. Find local .srt file
    2. Extract embedded subtitles in target language
    3. Download in target language
    4. Extract embedded subtitles in English and translate
    5. Download in English and translate

    Args:
        video_path: Path to the video file
        output_srt: Path to save the subtitle file
        target_lang: Target language code (default: 'es')

    Returns:
        True if subtitles were generated
    """
    # Case 1: Try to find local .srt file
    logger.info("Case 1: Searching for local .srt file...")
    if find_and_translate_local_srt(video_path, output_srt, target_lang=target_lang):
        logger.info("✅ Found and processed local subtitles")
        return True
        

    # Case 2: Try to extract subtitles in target language
    logger.info(f"Case 2: Attempting to extract {target_lang} subtitles...")
    lang_codes = LANGUAGE_CODE_MAP.get(target_lang, [target_lang])
    if extract_subtitles_by_language(video_path, output_srt, lang_codes):
        logger.info(f"✅ {target_lang} subtitles extracted successfully")
        return True
    logger.warning(f"No {target_lang} subtitles found in video")

    # Case 3: Try to download in target language
    logger.info(f"Case 3: Attempting to download {target_lang} subtitles...")
    downloaded = download_subtitle(video_path, target_lang)
    if downloaded:
        logger.info(f"✅ Subtitles downloaded: {downloaded.name}")
        return True
    logger.warning(f"Could not download {target_lang} subtitles")

    # Case 4: Try to extract English subtitles and translate
    logger.info("Case 4: Attempting to extract English subtitles...")
    temp_srt = video_path.parent / f"{video_path.stem}.temp_extracted.srt"
    try:
        char_count = extract_english_subtitles(video_path, temp_srt)
        if char_count and char_count > 0:
            logger.info(f"English subtitles extracted ({char_count} chars), translating to {target_lang}...")
            if translate_srt_file(temp_srt, output_srt, target_lang=target_lang):
                logger.info("✅ Subtitles extracted and translated")
                temp_srt.unlink(missing_ok=True)
                return True
        logger.warning("No English subtitles found in video")
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
    finally:
        temp_srt.unlink(missing_ok=True)

    # Case 5: Try to download in English and translate
    logger.info("Case 5: Attempting to download English subtitles...")
    downloaded = download_subtitle(video_path, "en", use_temp=True)

    if downloaded:
        logger.info(f"English subtitles downloaded: {downloaded.name}")
        logger.info(f"Translating to {target_lang}...")
        try:
            translate_srt_file(downloaded, output_srt, target_lang=target_lang)
            # Clean up temp files
            if downloaded.exists():
                downloaded.unlink()
            # Clean up any other temp files for this video
            for temp_file in video_path.parent.glob(f"{video_path.stem}.temp.*.srt"):
                temp_file.unlink(missing_ok=True)
            logger.info("✅ Subtitles generated and translated")
            return True
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            if downloaded.exists():
                downloaded.unlink(missing_ok=True)
            return False

    logger.warning("English subtitles not found online")
    return False


def main() -> None:
    """Main entry point for subtitle generation."""
    parser = argparse.ArgumentParser(
        description="Generate subtitles for a video file",
        epilog="Supports: download, extraction, and translation"
    )
    parser.add_argument("path", help="Path to the video file")
    parser.add_argument(
        "--language", "-l",
        help="Target language code (default: 'es'). Supported: es, en, fr, de, it, pt, ru, zh, ja, ko, ar, hi, nl, pl, tr",
        default='es'
    )
    parser.add_argument(
        "--config",
        help="Optional path to config.yaml file",
        default=None
    )
    args = parser.parse_args()

    # Load config if specified
    if args.config:
        load_config(args.config)

    config = get_config()

    # Validate video path
    video_path = validate_video_path(args.path)

    # Check video format
    if video_path.suffix.lower() not in config.video_formats:
        logger.error(f"Unsupported format: {video_path.suffix}")
        logger.info(f"Supported formats: {', '.join(config.video_formats)}")
        sys.exit(1)

    output_srt = video_path.parent / f"{video_path.stem}.srt"

    logger.info(f"Generating subtitles for: {video_path.name}")
    logger.info(f"Target language: {args.language}")

    if generate_subtitles_for_video(video_path, output_srt, target_lang=args.language):
        logger.info("✅ Subtitle generation complete")
        sys.exit(0)
    else:
        logger.error("❌ Could not generate subtitles for this video")
        sys.exit(1)


if __name__ == '__main__':
    main()
