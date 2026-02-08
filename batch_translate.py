#!/usr/bin/env python3
"""Batch translate all video files in a folder and subfolders."""
import argparse
import subprocess
import sys
from pathlib import Path
from typing import List

from config import get_config, load_config
from logging_config import get_logger

logger = get_logger()


def find_video_files(folder_path: Path, config) -> List[Path]:
    """Recursively find all video files in folder and subfolders.

    Args:
        folder_path: Root folder to search
        config: Configuration object with video.formats

    Returns:
        List of video file paths
    """
    video_files = []
    supported_formats = tuple(f".{fmt}" for fmt in config.video_formats)

    try:
        for video_file in folder_path.rglob("*"):
            if video_file.is_file() and video_file.suffix.lower() in supported_formats:
                video_files.append(video_file)
    except Exception as e:
        logger.error(f"Error scanning folder: {e}")
        return []

    return sorted(video_files)


def translate_video(video_path: Path) -> bool:
    """Translate a single video file using generate_sub.py.

    Args:
        video_path: Path to video file

    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "generate_sub.py"), str(video_path)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes timeout per video
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout processing: {video_path.name}")
        return False
    except Exception as e:
        logger.error(f"Error processing {video_path.name}: {e}")
        return False


def main() -> None:
    """Main entry point for batch translation."""
    parser = argparse.ArgumentParser(
        description="Batch translate all video files in a folder and subfolders",
        epilog="Recursively processes all supported video formats"
    )
    parser.add_argument(
        "folder",
        help="Folder path to search for video files"
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

    # Validate folder
    folder_path = Path(args.folder)
    if not folder_path.exists():
        logger.error(f"Folder not found: {folder_path}")
        sys.exit(1)

    if not folder_path.is_dir():
        logger.error(f"Not a folder: {folder_path}")
        sys.exit(1)

    # Find all video files
    print(f"\nSearching for video files in: {folder_path}")
    video_files = find_video_files(folder_path, config)

    if not video_files:
        print("No video files found")
        sys.exit(0)

    print(f"Found {len(video_files)} video file(s)\n")

    # Process each video
    successful = 0
    failed = 0

    for idx, video_path in enumerate(video_files, 1):
        print(f"[{idx}/{len(video_files)}] Processing: {video_path.name}")

        if translate_video(video_path):
            successful += 1
        else:
            failed += 1

    # Print summary
    print(f"\n{'='*60}")
    print(f"Batch translation complete!")
    print(f"  Total videos: {len(video_files)}")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"{'='*60}\n")

    if failed > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
