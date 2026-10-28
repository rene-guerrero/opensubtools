#!/usr/bin/env python3
"""CLI for batch subtitle extraction.

Batch extract embedded subtitles from videos and translate from English to Spanish.

Usage:
  python -m subtitles.cli.extract "path/to/videos/folder"
"""

import argparse
import subprocess
import sys
from pathlib import Path

from deep_translator import GoogleTranslator

from subtitles.core.extractor import (
    has_embedded_subtitles,
    get_subtitle_streams,
    extract_subtitles
)
from subtitles.core.translator import translate_srt_file
from subtitles.utils.config import get_config, load_config
from subtitles.utils.logging_config import get_logger
from subtitles.utils.paths import sort_paths_naturally

logger = get_logger()


def get_video_files(folder_path: Path) -> list[Path]:
    """Get all video files from a folder recursively."""
    config = get_config()

    if not folder_path.exists():
        logger.error(f"Folder not found: {folder_path}")
        sys.exit(1)

    # Recursively collect video files in subdirectories
    video_files = [
        f for f in folder_path.rglob('*')
        if f.is_file() and f.suffix.lower() in config.video_formats
    ]
    # Sort by path string for deterministic order across OS
    return sort_paths_naturally(video_files)


def process_video(video_path: Path, translator: GoogleTranslator, overwrite: bool = False) -> bool:
    """Process a video: extract subtitles and translate them."""
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
    if translate_srt_file(temp_srt, output_srt):
        logger.info(f"Saved: {output_srt.name}")
        success = True
    else:
        logger.error("Translation failed")
        success = False

    # Clean up temp file
    temp_srt.unlink(missing_ok=True)

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
    video_files = get_video_files(Path(args.folder))

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
