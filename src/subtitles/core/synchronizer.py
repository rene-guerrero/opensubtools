#!/usr/bin/env python3
"""Core subtitle synchronization logic.

Adjusts subtitle timing by a fixed offset.
"""

import re
from pathlib import Path
from typing import Optional

from subtitles.utils.logging_config import get_logger

logger = get_logger()

TIME_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[.,]\d{3})\s*(?:-+>|-+|>)\s*(?P<end>\d{2}:\d{2}:\d{2}[.,]\d{3})"
)


def time_to_ms(ts: str) -> Optional[int]:
    """Convert timestamp to milliseconds.

    Args:
        ts: Timestamp in format HH:MM:SS,mmm or HH:MM:SS.mmm

    Returns:
        Total milliseconds or None if invalid
    """
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


def synchronize_srt(input_path: Path, offset_ms: int, output_path: Optional[Path] = None) -> Path:
    """Synchronize subtitle timing by offset.

    Args:
        input_path: Path to input SRT file
        offset_ms: Offset in milliseconds
        output_path: Optional output path (defaults to input_path.stem + '.synced.srt')

    Returns:
        Path to synchronized file
    """
    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")

    logger.info(f"Loading: {input_path.name}")
    logger.info(f"Applying offset: {offset_ms} ms")

    try:
        content = input_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        raise IOError(f"Failed to read file: {e}")

    # Process by line to preserve formatting
    lines = content.splitlines(True)
    new_lines = [adjust_line_times(line, offset_ms) for line in lines]

    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}.synced{input_path.suffix}"

    try:
        output_path.write_text("".join(new_lines), encoding='utf-8')
        logger.info(f"Synchronized subtitles saved: {output_path.name}")
        return output_path
    except Exception as e:
        raise IOError(f"Failed to write file: {e}")
