#!/usr/bin/env python3
"""Cleanup helpers for subtitles converted from ASS by FFmpeg.

Typeset fansub tracks (signs, karaoke) convert into thousands of
near-duplicate SRT entries wrapped in <font> tags. These helpers strip
that markup and collapse the duplicates so translation and playback
work on the real dialogue only.
"""

import re
from datetime import timedelta
from pathlib import Path
from typing import List

import srt

from subtitles.utils.logging_config import get_logger

logger = get_logger()

_TAG_RE = re.compile(r'<[^>]+>')
_BRACE_RE = re.compile(r'\{[^}]*\}')

# ASS vector drawings ({\p1} shapes) survive tag stripping as bare path
# commands like "m 45 34.5 b 36 34,5 36 49,5 ..." — not real dialogue.
# They always begin with a move command: "m <x> <y>".
_DRAWING_RE = re.compile(r'^m\s+-?[\d.]+[\s\d.,mnlbspc-]*$', re.IGNORECASE)

# Frame-by-frame animations produce contiguous cues with identical text;
# a small gap tolerance lets runs split by timestamp rounding still merge.
_MERGE_MAX_GAP = timedelta(seconds=1)

# Simultaneous animated signs interleave their frames in time order, so a
# repeated cue is not always adjacent to its predecessor; look back this
# many merged cues when searching for the one to extend.
_MERGE_LOOKBACK = 20


def clean_subtitle_text(text: str) -> str:
    """Strip font/style tags and {...} editor comments, collapse whitespace."""
    text = _TAG_RE.sub('', text)
    text = _BRACE_RE.sub('', text)
    lines = [' '.join(line.split()) for line in text.splitlines()]
    return '\n'.join(line for line in lines if line and not _DRAWING_RE.match(line))


def clean_and_merge_subtitles(subtitles: List[srt.Subtitle]) -> List[srt.Subtitle]:
    """Clean markup and merge consecutive cues repeating the same text."""
    subtitles = sorted(subtitles, key=lambda s: (s.start, s.end))
    merged: List[srt.Subtitle] = []
    for sub in subtitles:
        text = clean_subtitle_text(sub.content)
        if not text:
            continue
        for prev in reversed(merged[-_MERGE_LOOKBACK:]):
            if prev.content == text and sub.start - prev.end <= _MERGE_MAX_GAP:
                prev.end = max(prev.end, sub.end)
                break
        else:
            sub.content = text
            merged.append(sub)
    return merged


def unique_text_score(srt_content: str) -> int:
    """Amount of distinct dialogue text in an SRT document.

    Raw character counts are dominated by markup and repeated animation
    frames, so streams are compared by their unique cleaned text instead.
    """
    try:
        subtitles = srt.parse(srt_content)
        unique = {clean_subtitle_text(s.content) for s in subtitles}
    except Exception:
        return 0
    unique.discard('')
    return sum(len(t) for t in unique)


def clean_srt_file(path: Path) -> bool:
    """Clean and deduplicate an SRT file in place.

    Returns:
        True if the file was rewritten, False if it was left untouched.
    """
    try:
        subtitles = list(srt.parse(path.read_text(encoding='utf-8', errors='ignore')))
        cleaned = clean_and_merge_subtitles(subtitles)
        if not cleaned:
            return False
        if len(cleaned) < len(subtitles):
            logger.info(f"Cleaned {path.name}: {len(subtitles)} -> {len(cleaned)} entries")
        path.write_text(srt.compose(cleaned), encoding='utf-8')
        return True
    except Exception as e:
        logger.warning(f"Could not clean {path.name}: {e}")
        return False
