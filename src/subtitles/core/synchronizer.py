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


def _mono_filter(video_path: Path) -> str:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=channels,channel_layout", "-of", "csv=p=0", str(video_path)],
        capture_output=True, text=True
    ).stdout.strip().split(",")
    channels = int(probe[0]) if probe and probe[0].isdigit() else 2
    layout = probe[1].split("(")[0] if len(probe) > 1 else ""
    if layout in {"3.0", "3.1", "4.0", "5.0", "5.1", "6.0", "6.1", "7.0", "7.1"}:
        return "pan=mono|c0=FC"
    if channels == 1:
        return "anull"
    return "pan=mono|c0=0.5*c0+0.5*c1"


def detect_speech(video_path: Path) -> np.ndarray:
    hop = SAMPLE_RATE * FRAME_MS // 1000
    # Downmix and resample before filtering: filtering first runs on every
    # channel at the source rate, ~5x slower. In surround mixes dialogue sits
    # in the center channel, which also keeps most music and effects out.
    mono = _mono_filter(video_path)
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video_path), "-map", "0:a:0", "-vn",
         "-af", f"{mono},aresample={SAMPLE_RATE},highpass=f=200,lowpass=f=3500",
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


def _correlation(subtitles: List[srt.Subtitle], speech: np.ndarray):
    n = len(speech)
    signal = subtitle_activity(subtitles, n)
    size = 1 << int(np.ceil(np.log2(2 * n)))
    corr = np.fft.irfft(
        np.fft.rfft(speech - speech.mean(), size) * np.conj(np.fft.rfft(signal - signal.mean(), size)),
        size
    )
    max_lag = SEARCH_MS // FRAME_MS
    lags = np.r_[np.arange(0, max_lag), np.arange(-max_lag, 0)]
    return lags, np.r_[corr[:max_lag], corr[-max_lag:]]


def _global_offset(subtitles: List[srt.Subtitle], speech: np.ndarray) -> int:
    lags, scores = _correlation(subtitles, speech)
    return int(lags[scores.argmax()])


def sync_confidence(subtitles: List[srt.Subtitle], speech: np.ndarray) -> float:
    """How clearly the best offset beats any offset 3+ seconds away.

    Near 1.0 the audio fits several offsets about equally (music under the
    dialogue fools the speech detector) and the result is a guess.
    """
    lags, scores = _correlation(subtitles, speech)
    best = scores.argmax()
    far = np.abs(lags - lags[best]) > 3000 // FRAME_MS
    runner_up = scores[far].max() if far.any() else 0.0
    if scores[best] <= 0:
        return 0.0
    return float(scores[best] / runner_up) if runner_up > 0 else float("inf")


CONFIDENT_SYNC = 1.3


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


def subtitle_activity(subtitles: List[srt.Subtitle], frames: int) -> np.ndarray:
    activity = np.zeros(frames, np.float32)
    for sub in subtitles:
        activity[max(_frame(sub.start), 0):max(min(_frame(sub.end), frames), 0)] = 1
    return activity


def _embedded_reference(video_path: Path) -> Optional[List[srt.Subtitle]]:
    """Dialogue timing from the video's own English track, if it has one.

    Those cues were timed against this exact release, so they are a far
    cleaner target than speech detected from audio, which music and
    effects confuse into multi-second false jumps.
    """
    from subtitles.core.extractor import extract_english_subtitles

    temp = video_path.parent / f"{video_path.stem}.temp_reference.srt"
    try:
        if not extract_english_subtitles(video_path, temp):
            return None
        reference = list(srt.parse(temp.read_text(encoding='utf-8', errors='ignore')))
        return reference if len(reference) >= 20 else None
    except Exception as e:
        logger.debug(f"No embedded reference track: {e}")
        return None
    finally:
        temp.unlink(missing_ok=True)


def _speech_sync(video_path: Path, subtitles: List[srt.Subtitle], output_path: Path,
                 allow_transcript: bool) -> Optional[Path]:
    """Time cues by matching their words to a Whisper transcript.

    Returns None when the transcript can't be used, so the caller keeps the
    energy-based result.
    """
    from subtitles.core import speech

    try:
        words = speech.transcribe(video_path)
    except Exception as e:
        logger.warning(f"Transcription failed: {e}")
        return None
    if not words:
        return None

    offsets, ratio = speech.align(subtitles, words)
    if ratio >= speech.MIN_MATCH_RATIO:
        aligned = speech.apply_alignment(subtitles, offsets)
        logger.info(f"  matched {ratio:.0%} of cues to the speech; "
                    f"dropped {len(subtitles) - len(aligned)} not in this video")
        output_path.write_text(srt.compose(aligned, reindex=True), encoding='utf-8')
        return output_path

    if allow_transcript:
        logger.warning(f"  only {ratio:.0%} of cues are spoken in this video (different script); "
                       "using the transcript instead")
        cues = speech.transcript_to_subtitles(words)
        output_path.write_text(srt.compose(cues, reindex=True), encoding='utf-8')
        return output_path

    logger.warning(f"  only {ratio:.0%} of cues matched the speech; keeping audio-energy timing")
    return None


def auto_synchronize_srt(video_path: Path, srt_path: Path, output_path: Optional[Path] = None,
                         language: Optional[str] = None, allow_transcript: bool = False) -> Path:
    """Align a subtitle to this video.

    Args:
        language: The subtitle's language. When it matches the audio and the
            energy-based sync is unsure, the cues are timed against a speech
            transcript instead.
        allow_transcript: If the subtitle's words mostly aren't spoken in the
            video, replace it with the transcript (only sensible before
            translating; it rewrites the text).
    """
    if output_path is None:
        output_path = srt_path

    subtitles = list(srt.parse(srt_path.read_text(encoding='utf-8-sig', errors='ignore')))
    if not subtitles:
        raise ValueError(f"No subtitles in {srt_path.name}")

    reference = _embedded_reference(video_path)
    if reference:
        logger.info(f"Auto-synchronizing {srt_path.name} against embedded subtitles of {video_path.name}")
        last = max(max(s.end for s in reference), max(s.end for s in subtitles))
        activity = subtitle_activity(reference, _frame(last) + SEARCH_MS // FRAME_MS)
    else:
        logger.info(f"Auto-synchronizing {srt_path.name} against audio of {video_path.name}")
        activity = detect_speech(video_path)
        confidence = sync_confidence(subtitles, activity)
        if confidence < CONFIDENT_SYNC and language:
            from subtitles.core import speech
            if language.split('-')[0] == 'en' and speech.can_transcribe(video_path):
                logger.info(f"  audio sync unsure (confidence {confidence:.2f}); matching against speech")
                try:
                    done = _speech_sync(video_path, subtitles, output_path, allow_transcript)
                except Exception as e:
                    logger.warning(f"  speech matching failed ({e}); keeping audio-energy timing")
                    done = None
                if done:
                    return done
    offsets = compute_offsets(subtitles, activity)

    previous = None
    for sub, offset in zip(subtitles, offsets):
        if offset != previous:
            logger.info(f"  from {str(sub.start)[:8]}: {offset:+d} ms")
            previous = offset
        shift = timedelta(milliseconds=offset)
        sub.start = sub.start + shift
        sub.end = sub.end + shift

    # Cues pushed before the start belong to material this release cut
    # (a "previously on" recap, a cold-open narration); clamping them to
    # 0:00 would stack them over the opening.
    kept = [sub for sub in subtitles if sub.start >= timedelta(0)]
    if len(kept) < len(subtitles):
        logger.info(f"  dropped {len(subtitles) - len(kept)} cues not present in this video")
    subtitles = kept or subtitles
    for sub in subtitles:
        sub.start = max(timedelta(0), sub.start)
        sub.end = max(sub.start, sub.end)

    for current, following in zip(subtitles, subtitles[1:]):
        if current.end > following.start:
            current.end = max(current.start, following.start)

    output_path.write_text(srt.compose(subtitles, reindex=True), encoding='utf-8')
    logger.info(f"Synchronized subtitles saved: {output_path.name}")
    return output_path
