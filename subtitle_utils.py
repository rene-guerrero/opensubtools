#!/usr/bin/env python3
"""Centralized utilities for SRT subtitle file operations.

Provides high-level functions for:
- Loading and detecting language in SRT files
- Translating SRT content
- Finding local SRT files
"""

from pathlib import Path
from typing import Optional, List, Dict
from translate_utils import is_english_line, translate_batch_text, DEFAULT_DELIM
from config import get_config
from deep_translator import GoogleTranslator


def find_local_srt(video_path: Path) -> Optional[Path]:
    """Search for a .srt file with the same base name as video.

    Args:
        video_path: Path to the video file

    Returns:
        Path to .srt file or None if not found
    """
    possible_srt = video_path.parent / f"{video_path.stem}.srt"
    return possible_srt if possible_srt.exists() else None


def detect_language(text: str) -> str:
    """Detect if text is in English or Spanish.

    Args:
        text: Text content to analyze

    Returns:
        Language code: 'en', 'es', or 'unknown'
    """
    config = get_config()
    lines = text.splitlines()

    if not lines:
        return 'unknown'

    # Count English lines
    english_count = sum(1 for line in lines if is_english_line(line))
    total_lines = len([l for l in lines if l.strip()])

    if total_lines == 0:
        return 'unknown'

    ratio = english_count / total_lines
    return 'en' if ratio > 0.3 else 'es' if ratio < 0.1 else 'unknown'


def translate_srt_content(srt_content: str, source_lang: str = 'en',
                         target_lang: str = 'es') -> str:
    """Translate SRT file content from source to target language.

    Args:
        srt_content: SRT file content as string
        source_lang: Source language code (default: 'en')
        target_lang: Target language code (default: 'es')

    Returns:
        Translated SRT content
    """
    config = get_config()
    translator = GoogleTranslator(source=source_lang, target=target_lang)

    lines = srt_content.splitlines(True)

    # Find indices of lines to translate (non-metadata lines)
    eng_indices = [i for i, line in enumerate(lines) if is_english_line(line)]

    if not eng_indices:
        # No English content detected, return as-is
        return srt_content

    translated_lines = list(lines)
    total_english = len(eng_indices)
    translated_so_far = 0

    batch_lines = []
    batch_indices = []
    max_chars = config.max_batch_chars

    for idx in eng_indices:
        line = lines[idx].rstrip("\n")
        current_batch_len = (sum(len(lines[i]) for i in batch_indices) +
                           len(DEFAULT_DELIM) * max(0, len(batch_indices) - 1))

        if batch_indices and (current_batch_len + len(line)) > max_chars:
            # Process full batch
            translated = translate_batch_text(batch_lines, translator)
            for t, pos in zip(translated, batch_indices):
                translated_lines[pos] = t + ("\n" if lines[pos].endswith("\n") else "")
            batch_lines = []
            batch_indices = []
            translated_so_far += len(translated)

        batch_lines.append(line)
        batch_indices.append(idx)

    # Process remaining batch
    if batch_indices:
        translated = translate_batch_text(batch_lines, translator)
        for t, pos in zip(translated, batch_indices):
            translated_lines[pos] = t + ("\n" if lines[pos].endswith("\n") else "")
        translated_so_far += len(translated)

    return "".join(translated_lines)


def validate_srt_format(file_path: Path) -> bool:
    """Validate that a file is a valid SRT subtitle file.

    Args:
        file_path: Path to file to validate

    Returns:
        True if file appears to be valid SRT, False otherwise
    """
    if not file_path.exists():
        return False

    if file_path.suffix.lower() != '.srt':
        return False

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Basic SRT validation: should have numbers, timestamps, and blank lines
            return bool(content) and ('-->' in content)
    except Exception:
        return False
