#!/usr/bin/env python3
"""CLI for subtitle synchronization.

Synchronize subtitles timing in a .srt file by a fixed offset in milliseconds.

Usage:
  python -m subtitles.cli.sync "path/to/subtitles.srt" 3000

Where 3000 moves subtitles forward by 3 seconds; negative values move backward.
"""

import argparse
import sys
from pathlib import Path

from subtitles.core.synchronizer import synchronize_srt
from subtitles.utils.config import load_config
from subtitles.utils.logging_config import get_logger

logger = get_logger()


def main() -> None:
    """Main entry point for subtitle synchronization."""
    parser = argparse.ArgumentParser(
        description="Synchronize subtitle timing by offset (milliseconds)",
        epilog="Positive values move subtitles forward, negative values backward"
    )
    parser.add_argument("path", help="Path to the input .srt file")
    parser.add_argument(
        "offset_ms",
        type=int,
        help="Offset in milliseconds (e.g., 3000 for +3 seconds)"
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

    input_path = Path(args.path)

    try:
        output_path = synchronize_srt(input_path, args.offset_ms)
        logger.info(f"✅ Subtitles synchronized: {output_path.name}")
        sys.exit(0)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Synchronization failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
