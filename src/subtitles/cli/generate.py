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
import ctypes
import os
import subprocess
import sys
from pathlib import Path

from subtitles.core.downloader import (
    download_english_subtitle,
    download_spanish_subtitle
)
from subtitles.core.extractor import (
    extract_english_subtitles,
    extract_spanish_subtitles,
    extract_subtitles_by_language
)
from subtitles.core.translator import find_and_translate_local_srt, translate_srt_file
from subtitles.utils.config import get_config, load_config
from subtitles.utils.logging_config import get_logger
from subtitles.utils.translate import is_srt_spanish

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
    1. Find and translate local .srt
    2. Extract Spanish embedded subtitles
    3. Extract English embedded subtitles and translate
    4. Download Spanish subtitles
    5. Download English subtitles and translate

    Args:
        video_path: Path to the video file
        output_srt: Path to save the subtitle file
        target_lang: Target language code (default: 'es' for Spanish)

    Returns:
        True if subtitles were generated
    """
    config = get_config()

    # Case 1: Try to find and translate local .srt file
    logger.info("Case 1: Searching for local .srt file...")
    if find_and_translate_local_srt(video_path, output_srt, target_lang=target_lang):
        logger.info("✅ Found and processed local subtitles")
        return True

    # Case 2: Try to extract subtitles in target language if available
    if target_lang != 'es':
        logger.info(f"Case 2: Attempting to extract {target_lang} subtitles...")
        # Try common language codes for the target language
        language_code_map = {
            'es': ['es', 'spa'],
            'en': ['en', 'eng'],
            'fr': ['fr', 'fra'],
            'de': ['de', 'deu'],
            'it': ['it', 'ita'],
            'pt': ['pt', 'por'],
            'ru': ['ru', 'rus'],
            'zh': ['zh', 'zho', 'chi'],
            'ja': ['ja', 'jpn'],
            'ko': ['ko', 'kor'],
            'ar': ['ar', 'ara'],
            'hi': ['hi', 'hin'],
            'nl': ['nl', 'nld'],
            'pl': ['pl', 'pol'],
            'tr': ['tr', 'tur']
        }
        lang_codes = language_code_map.get(target_lang, [target_lang])
        if extract_subtitles_by_language(video_path, output_srt, lang_codes):
            logger.info(f"✅ {target_lang} subtitles extracted successfully")
            return True

    # Case 3: Try to extract Spanish subtitles embedded in video
    logger.info("Case 3: Attempting to extract Spanish subtitles...")
    if extract_spanish_subtitles(video_path, output_srt):
        if target_lang == 'es':
            logger.info("✅ Spanish subtitles extracted successfully")
            return True
        else:
            # Spanish found but need different language, translate it
            logger.info(f"Spanish subtitles found, translating to {target_lang}...")
            temp_srt = video_path.parent / f"{video_path.stem}.temp_spanish.srt"
            output_srt.rename(temp_srt)
            if translate_srt_file(temp_srt, output_srt, target_lang=target_lang):
                temp_srt.unlink(missing_ok=True)
                logger.info("✅ Spanish subtitles translated")
                return True
            else:
                temp_srt.rename(output_srt)

    # Case 4: Try to extract English subtitles and translate
    logger.info("Case 4: Attempting to extract and translate English subtitles...")
    temp_srt = video_path.parent / f"{video_path.stem}.temp_extracted.srt"
    try:
        char_count = extract_english_subtitles(video_path, temp_srt)
        if char_count and char_count > 0:
            logger.info(f"English subtitles extracted, translating to {target_lang}...")
            if translate_srt_file(temp_srt, output_srt, target_lang=target_lang):
                logger.info("✅ Subtitles extracted and translated")
                temp_srt.unlink(missing_ok=True)
                return True
    except Exception as e:
        logger.debug(f"Extraction failed: {e}")
    finally:
        temp_srt.unlink(missing_ok=True)

    # Case 5: Try to download Spanish subtitles
    logger.info("Case 5: Attempting to download Spanish subtitles...")
    spanish_srt = download_spanish_subtitle(video_path)
    if spanish_srt:
        logger.info(f"Spanish subtitles downloaded: {spanish_srt.name}")
        if spanish_srt != output_srt:
            if target_lang == 'es':
                spanish_srt.rename(output_srt)
                logger.info("✅ Subtitles generated successfully")
                return True
            else:
                # Spanish found but need different language, translate it
                logger.info(f"Translating to {target_lang}...")
                if translate_srt_file(spanish_srt, output_srt, target_lang=target_lang):
                    spanish_srt.unlink(missing_ok=True)
                    logger.info("✅ Subtitles generated and translated")
                    return True
                else:
                    spanish_srt.unlink(missing_ok=True)
        else:
            logger.info("✅ Subtitles generated successfully")
            return True

    logger.warning("Spanish subtitles not found online")

    # Case 6: Try to download English subtitles
    logger.info("Case 6: Attempting to download English subtitles...")
    english_srt = download_english_subtitle(video_path)

    if english_srt:
        logger.info(f"English subtitles downloaded: {english_srt.name}")
        logger.info(f"Translating to {target_lang}...")
        try:
            translate_srt_file(english_srt, output_srt, target_lang=target_lang)
            english_srt.unlink(missing_ok=True)
            logger.info("✅ Subtitles generated and translated")
            return True
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            english_srt.unlink(missing_ok=True)
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
        help="Target language code (default: 'es' for Spanish). Supported: es, en, fr, de, it, pt, ru, zh, ja, ko, ar, hi, nl, pl, tr",
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

    # Check if already has subtitles in target language
    if output_srt.exists():
        if args.language == 'es' and is_srt_spanish(output_srt):
            logger.info("✅ Video already has Spanish subtitles")
            sys.exit(0)
        else:
            logger.warning("Existing subtitles found")

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
