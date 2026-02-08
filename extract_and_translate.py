#!/usr/bin/env python3
"""
Batch extract embedded subtitles from videos, translate from English to Spanish,
and save as .srt files.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

import ffmpeg
import srt
from deep_translator import GoogleTranslator

from translate_utils import (
    translate_batch_text,
    translate_text,
    DEFAULT_DELIM,
    has_embedded_subtitles,
    get_subtitle_streams,
    extract_subtitles
)
from config import get_config, load_config
from logging_config import get_logger

logger = get_logger()


def get_video_files(folder_path: str | Path) -> List[Path]:
    """Get all video files from a folder recursively.

    Args:
        folder_path: Path to folder to search

    Returns:
        Sorted list of video file paths
    """
    config = get_config()
    folder = Path(folder_path)

    if not folder.exists():
        logger.error(f"Folder not found: {folder_path}")
        sys.exit(1)

    # Recursively collect video files in subdirectories
    video_files = [
        f for f in folder.rglob('*')
        if f.is_file() and f.suffix.lower() in config.video_formats
    ]
    # Sort by path string for deterministic order across OS
    return sorted(video_files, key=lambda p: str(p).lower())


def translate_srt_file(input_path: Path, output_path: Path, translator: GoogleTranslator,
                      batch_size: int = 50) -> bool:
    """Translate an SRT file from English to Spanish using batches.

    Args:
        input_path: Path to input .srt file
        output_path: Path to save translated .srt file
        translator: GoogleTranslator instance
        batch_size: Number of subtitles per batch

    Returns:
        True if successful, False otherwise
    """
    config = get_config()
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()

        # Parse subtitles
        try:
            subtitles = list(srt.parse(srt_content))
        except Exception as e:
            logger.warning(f"Could not parse SRT: {e}")
            # Try to clean content
            srt_content = re.sub(r'\r\n', '\n', srt_content)
            srt_content = re.sub(r'\r', '\n', srt_content)
            subtitles = list(srt.parse(srt_content))

        if not subtitles:
            logger.warning("No subtitles found in file")
            return False

        total_subtitles = len(subtitles)
        logger.info(f"Translating {total_subtitles} subtitles...")

        # Process in batches
        all_translated_texts = []
        for batch_start in range(0, total_subtitles, batch_size):
            batch_end = min(batch_start + batch_size, total_subtitles)
            batch_subtitles = subtitles[batch_start:batch_end]

            # Extract texts from batch
            batch_texts = [subtitle.content for subtitle in batch_subtitles]

            logger.debug(f"Batch {batch_start//batch_size + 1}/{(total_subtitles + batch_size - 1)//batch_size}")

            # Translate batch
            batch_translated = translate_batch_text(batch_texts, translator)
            all_translated_texts.extend(batch_translated)

        # Reconstruct subtitles with translated text
        translated_subtitles = []
        for i, subtitle in enumerate(subtitles):
            translated_content = (
                all_translated_texts[i] if i < len(all_translated_texts)
                else subtitle.content
            )
            translated_subtitle = srt.Subtitle(
                index=subtitle.index,
                start=subtitle.start,
                end=subtitle.end,
                content=translated_content
            )
            translated_subtitles.append(translated_subtitle)

        # Write translated file
        translated_srt = srt.compose(translated_subtitles)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(translated_srt)

        logger.info("Translation completed")
        return True

    except Exception as e:
        logger.error(f"Translation error: {e}")
        return False


def process_video(video_path: Path, translator: GoogleTranslator, overwrite: bool = False) -> bool:
    """Process a video: extract subtitles and translate them.

    Args:
        video_path: Path to video file
        translator: GoogleTranslator instance
        overwrite: Whether to overwrite existing translations

    Returns:
        True if successful, False otherwise
    """
    config = get_config()
    output_srt = video_path.with_suffix('.es.srt')
    temp_srt = video_path.with_suffix('.temp.srt')

    # Check if already translated
    if output_srt.exists() and not overwrite:
        logger.info(f"Skipping (already has subtitles): {video_path.name}")
        return False

    logger.info(f"Processing: {video_path.name}")

    # Check for embedded subtitles
    if not has_embedded_subtitles(video_path):
        logger.debug("No embedded subtitles found")
        return False

    # Get subtitle streams
    subtitle_streams = get_subtitle_streams(video_path)
    if not subtitle_streams:
        logger.warning("Could not detect subtitle streams")
        return False

    logger.debug(f"Found {len(subtitle_streams)} subtitle stream(s)")

    # Look for English subtitles (prefer longest stream)
    english_streams = [
        s for s in subtitle_streams
        if str(s['language']).lower() in config.english_codes
    ]

    if not english_streams:
        logger.debug("No English subtitles found")
        return False

    # Use first English stream
    target_stream = english_streams[0]['subtitle_index']
    logger.info(f"Using English subtitle stream {target_stream}")

    # Extract subtitles
    logger.debug("Extracting subtitles...")
    if not extract_subtitles(video_path, temp_srt, target_stream):
        return False

    # Translate subtitles
    logger.info("Translating to Spanish...")
    if translate_srt_file(temp_srt, output_srt, translator):
        logger.info(f"Saved: {output_srt.name}")
        success = True
    else:
        logger.error("Translation failed")
        success = False

    # Clean up temp file
    if temp_srt.exists():
        try:
            temp_srt.unlink()
        except Exception:
            pass

    return success


def main() -> None:
    """Main entry point for batch processing."""
    parser = argparse.ArgumentParser(
        description="Batch extract and translate subtitles from videos",
        epilog="Processes all videos in a folder recursively"
    )
    parser.add_argument(
        "folder",
        help="Folder containing videos"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing translations"
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

    # Verify ffmpeg is installed
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=5)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        logger.error("FFmpeg not found or not in PATH")
        logger.info("Install ffmpeg: winget install Gyan.FFmpeg")
        sys.exit(1)

    # Initialize translator
    logger.info("Initializing translator...")
    translator = GoogleTranslator(source='en', target='es')

    # Get video files
    logger.info(f"Scanning: {args.folder}")
    video_files = get_video_files(args.folder)

    if not video_files:
        logger.error("No video files found")
        sys.exit(1)

    logger.info(f"Found {len(video_files)} video file(s)")

    # Process each video
    success_count = 0
    for video_file in video_files:
        if process_video(video_file, translator, args.overwrite):
            success_count += 1

    logger.info(f"✅ Completed: {success_count}/{len(video_files)} videos processed")


if __name__ == '__main__':
    main()
