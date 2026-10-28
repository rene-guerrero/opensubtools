#!/usr/bin/env python3
"""Core subtitle synchronization logic.

Adjusts subtitle timing by a fixed offset.
"""

import re
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import List, Optional

import numpy as np
import srt

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


SAMPLE_RATE = 16000
FRAME_MS = 10
SEARCH_MS = 60000
SEGMENT_SPAN_MS = 20000
MAX_JUMP_MS = 4000
JUMP_PENALTY = 300.0


def detect_speech(video_path: Path) -> np.ndarray:
    hop = SAMPLE_RATE * FRAME_MS // 1000
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video_path), "-vn", "-ac", "1",
         "-ar", str(SAMPLE_RATE), "-af", "highpass=f=200,lowpass=f=3500",
         "-f", "s16le", "-"],
        capture_output=True, check=True
    ).stdout
    audio = np.frombuffer(raw, np.int16).astype(np.float32)
    frames = len(audio) // hop
    energy = np.log10((audio[:frames * hop].reshape(frames, hop) ** 2).mean(1) + 1e-3)
    step, radius = 50, 300
    floor = np.array([
        np.percentile(energy[max(0, i - radius):i + radius], 20)
        for i in range(0, frames, step)
    ])
    floor = np.repeat(floor, step)[:frames]
    return (energy > floor + 0.6).astype(np.float32)


def _frame(td: timedelta) -> int:
    return int(td.total_seconds() * 1000) // FRAME_MS


def _global_offset(subtitles: List[srt.Subtitle], speech: np.ndarray) -> int:
    n = len(speech)
    signal = np.zeros(n, np.float32)
    for sub in subtitles:
        signal[max(_frame(sub.start), 0):max(min(_frame(sub.end), n), 0)] = 1
    size = 1 << int(np.ceil(np.log2(2 * n)))
    corr = np.fft.irfft(
        np.fft.rfft(speech - speech.mean(), size) * np.conj(np.fft.rfft(signal - signal.mean(), size)),
        size
    )
    max_lag = SEARCH_MS // FRAME_MS
    lags = np.r_[np.arange(0, max_lag), np.arange(-max_lag, 0)]
    return int(lags[np.r_[corr[:max_lag], corr[-max_lag:]].argmax()])


def _window_max(values: np.ndarray, radius: int):
    size = len(values)
    padded = np.full(size + 2 * radius, -np.inf)
    padded[radius:radius + size] = values
    windows = np.lib.stride_tricks.sliding_window_view(padded, 2 * radius + 1)
    best = windows.argmax(1)
    return windows[np.arange(size), best], np.clip(np.arange(size) + best - radius, 0, size - 1)


def compute_offsets(subtitles: List[srt.Subtitle], speech: np.ndarray) -> List[int]:
    n = len(speech)
    center = _global_offset(subtitles, speech)
    span = SEGMENT_SPAN_MS // FRAME_MS
    offsets = np.arange(center - span, center + span + 1)
    cumulative = np.concatenate([[0], np.cumsum(speech - speech.mean())])
    jump = MAX_JUMP_MS // FRAME_MS
    states = np.arange(len(offsets))
    back = np.zeros((len(subtitles), len(offsets)), np.int32)
    score = None

    for i, sub in enumerate(subtitles):
        start = np.clip(_frame(sub.start) + offsets, 0, n)
        end = np.clip(_frame(sub.end) + offsets, 0, n)
        gain = cumulative[end] - cumulative[start]
        if score is None:
            back[i] = states
            score = gain
            continue
        best, origin = _window_max(score, jump)
        stay = score >= best - JUMP_PENALTY
        back[i] = np.where(stay, states, origin)
        score = np.where(stay, score, best - JUMP_PENALTY) + gain

    state = int(score.argmax())
    result = [0] * len(subtitles)
    for i in range(len(subtitles) - 1, -1, -1):
        result[i] = int(offsets[state]) * FRAME_MS
        state = back[i][state]
    return result


def auto_synchronize_srt(video_path: Path, srt_path: Path, output_path: Optional[Path] = None) -> Path:
    if output_path is None:
        output_path = srt_path

    logger.info(f"Auto-synchronizing {srt_path.name} against audio of {video_path.name}")
    subtitles = list(srt.parse(srt_path.read_text(encoding='utf-8', errors='ignore')))
    if not subtitles:
        raise ValueError(f"No subtitles in {srt_path.name}")

    speech = detect_speech(video_path)
    offsets = compute_offsets(subtitles, speech)

    previous = None
    for sub, offset in zip(subtitles, offsets):
        if offset != previous:
            logger.info(f"  from {str(sub.start)[:8]}: {offset:+d} ms")
            previous = offset
        shift = timedelta(milliseconds=offset)
        sub.start = max(timedelta(0), sub.start + shift)
        sub.end = max(sub.start, sub.end + shift)

    for current, following in zip(subtitles, subtitles[1:]):
        if current.end > following.start:
            current.end = max(current.start, following.start)

    output_path.write_text(srt.compose(subtitles, reindex=True), encoding='utf-8')
    logger.info(f"Synchronized subtitles saved: {output_path.name}")
    return output_path
