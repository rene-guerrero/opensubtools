#!/usr/bin/env python3
"""CLI for subtitle translation.

Translate an English .srt file to Spanish.
"""

import argparse
import sys
from pathlib import Path

from subtitles.core.translator import translate_srt_file
from subtitles.utils.config import load_config
from subtitles.utils.logging_config import get_logger

logger = get_logger()


def main() -> None:
    """Main entry point for SRT translation."""
    parser = argparse.ArgumentParser(
        description="Translate English .srt subtitles to Spanish",
        epilog="Translates only English lines, preserves numbering and timing"
    )
    parser.add_argument("path", help="Path to the input .srt file")
    parser.add_argument(
        "--config",
        help="Optional path to config.yaml file",
        default=None
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file path (default: overwrites input)",
        default=None
    )
    args = parser.parse_args()

    # Load config if specified
    if args.config:
        load_config(args.config)

    input_path = Path(args.path)

    if not input_path.exists():
        logger.error(f"File not found: {input_path}")
        sys.exit(1)

    # Validate file type: only allow .srt subtitle files
    if input_path.suffix.lower() != ".srt":
        logger.error(f"Invalid format: expected .srt, got {input_path.suffix}")
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path

    logger.info(f"Translating: {input_path.name}")

    # Backup original if we're overwriting
    if output_path == input_path:
        backup_path = input_path.with_suffix('.en.srt')
        try:
            input_path.rename(backup_path)
            logger.info(f"Original backed up as: {backup_path.name}")
            input_path = backup_path
        except Exception as e:
            logger.warning(f"Could not backup original: {e}")

    try:
        success = translate_srt_file(input_path, output_path)
        if success:
            logger.info(f"✅ Translation complete: {output_path.name}")
            sys.exit(0)
        else:
            logger.error("Translation failed")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Translation error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
