#!/usr/bin/env python3
"""CLI for batch subtitle processing.

Process all video files in a folder and subfolders to generate subtitles.

Usage:
  python -m subtitles.cli.batch "path/to/videos/folder"
"""

import argparse
import sys
from pathlib import Path
from threading import Lock

from subtitles.cli.generate import generate_subtitles_for_video
from subtitles.utils.config import get_config, load_config
from subtitles.utils.logging_config import get_logger
from subtitles.utils.translate import is_srt_spanish

logger = get_logger()

# Global lock for synchronized output
output_lock = Lock()


def find_video_files(folder_path: Path, config) -> list[Path]:
    """Recursively find all video files in folder and subfolders.

    Args:
        folder_path: Root folder to search
        config: Configuration object with video.formats

    Returns:
        List of video file paths
    """
    video_files = []

    # Ensure formats have dots
    formats = [f if f.startswith('.') else f'.{f}' for f in config.video_formats]
    supported_formats = tuple(formats)

    try:
        for video_file in folder_path.rglob("*"):
            if video_file.is_file() and video_file.suffix.lower() in supported_formats:
                video_files.append(video_file)

    except Exception as e:
        logger.error(f"Error scanning folder: {e}")
        return []

    return sorted(video_files)


def process_single_video(video_path: Path) -> tuple[bool, bool]:
    """Process a single video file.

    Args:
        video_path: Path to video file

    Returns:
        Tuple of (success: bool, skipped: bool)
        - success: True if subtitles were generated/available
        - skipped: True if video was skipped (already has Spanish SRT)
    """
    try:
        # Check if SRT already exists and is in Spanish
        output_srt = video_path.parent / f"{video_path.stem}.srt"
        if output_srt.exists():
            # Check if it's in Spanish using enhanced detection
            if is_srt_spanish(output_srt):
                # Already has Spanish SRT - skip processing
                return (True, True)

        result = generate_subtitles_for_video(video_path, output_srt)
        return (result, False)
    except Exception as e:
        logger.error(f"Error processing {video_path.name}: {e}")
        return (False, False)


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
        print(f"ERROR: Folder not found: {folder_path}")
        sys.exit(1)

    if not folder_path.is_dir():
        print(f"ERROR: Not a folder: {folder_path}")
        sys.exit(1)

    # Find all video files
    print(f"\nSearching for video files in: {folder_path}")
    video_files = find_video_files(folder_path, config)

    if not video_files:
        print("No video files found")
        sys.exit(0)

    print(f"Found {len(video_files)} video(s)\n")

    # Process each video
    successful = 0
    skipped = 0
    failed = 0

    for idx, video_path in enumerate(video_files, 1):
        percent = (idx / len(video_files)) * 100
        print(f"[{idx}/{len(video_files)}] {percent:3.0f}% - {video_path.name}", end=" ")
        sys.stdout.flush()

        success, is_skipped = process_single_video(video_path)
        if is_skipped:
            skipped += 1
            print("[SKIPPED - Already has Spanish SRT]")
        elif success:
            successful += 1
            print("[OK]")
        else:
            failed += 1
            print("[FAILED]")

    # Print summary
    print(f"\n{'='*60}")
    print(f"Batch processing completed!")
    print(f"  Total: {len(video_files)}")
    print(f"  Successful: {successful}")
    print(f"  Skipped: {skipped} (already had Spanish SRT)")
    print(f"  Failed: {failed}")
    print(f"{'='*60}\n")

    if failed > 0:
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"ERROR: {e}")
        print(f"{'='*60}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nPress Enter to close...")
        input()
