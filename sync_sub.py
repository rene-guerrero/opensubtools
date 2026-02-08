#!/usr/bin/env python3
"""
Synchronize subtitles timing in a .srt file by a fixed offset in milliseconds.

Usage:
  python sync_sub.py "path/to/subtitles.srt" 3000

Where 3000 moves subtitles forward by 3 seconds; negative values move backward.
Produces a new file with the same name but with .synced before the extension.
"""

import argparse
import re
from pathlib import Path

from config import get_config, load_config
from logging_config import get_logger

logger = get_logger()

TIME_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[.,]\d{3})\s*(?:-+>|-+|>)\s*(?P<end>\d{2}:\d{2}:\d{2}[.,]\d{3})"
)


def time_to_ms(ts: str) -> int | None:
    """Convert timestamp to milliseconds.

    Args:
        ts: Timestamp in format HH:MM:SS,mmm or HH:MM:SS.mmm

    Returns:
        Total milliseconds or None if invalid
    """
    # accept 00:00:00,000 or 00:00:00.000
    sep = ',' if ',' in ts else '.'
    ts_clean = ts.replace(',', '.')
    try:
        h, m, rest = ts_clean.split(':', 2)
        s, ms = rest.split('.', 1)
        total = int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms[:3].ljust(3, '0'))
        return total
    except Exception:
        return None


def ms_to_time(ms: int) -> str:
    """Convert milliseconds to timestamp string.

    Args:
        ms: Total milliseconds

    Returns:
        Timestamp in format HH:MM:SS,mmm
    """
    if ms < 0:
        ms = 0
    h = ms // 3600000
    ms -= h * 3600000
    m = ms // 60000
    ms -= m * 60000
    s = ms // 1000
    ms = ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def adjust_line_times(line: str, offset_ms: int) -> str:
    """Adjust start and end times in a subtitle line.

    Args:
        line: Single line that may contain timestamps
        offset_ms: Offset in milliseconds (positive or negative)

    Returns:
        Line with adjusted times or original if no times found
    """
    def repl(match):
        start = match.group('start')
        end = match.group('end')
        ms_start = time_to_ms(start)
        ms_end = time_to_ms(end)
        if ms_start is None or ms_end is None:
            return match.group(0)
        new_start = max(0, ms_start + offset_ms)
        new_end = max(0, ms_end + offset_ms)
        return f"{ms_to_time(new_start)} --> {ms_to_time(new_end)}"

    return TIME_RE.sub(repl, line)


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

    if not input_path.exists():
        logger.error(f"File not found: {input_path}")
        raise SystemExit(1)

    logger.info(f"Loading: {input_path.name}")
    logger.info(f"Applying offset: {args.offset_ms} ms")

    try:
        content = input_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        raise SystemExit(1)

    # Process by line to preserve formatting
    lines = content.splitlines(True)
    new_lines = [adjust_line_times(line, args.offset_ms) for line in lines]

    out_path = input_path.parent / f"{input_path.stem}.synced{input_path.suffix}"

    try:
        out_path.write_text("".join(new_lines), encoding='utf-8')
        logger.info(f"Synchronized subtitles saved: {out_path.name}")
    except Exception as e:
        logger.error(f"Failed to write file: {e}")
        raise SystemExit(1)

    raise SystemExit(0)


if __name__ == '__main__':
    main()
