#!/usr/bin/env python3
"""Shared utilities for translating English text to Spanish.
Includes helpers for language detection, batch translation, and video analysis.
"""
from pathlib import Path
from typing import List, Dict, Optional
import tempfile
import os
import re
import logging

try:
    import ffmpeg
except ImportError:
    ffmpeg = None

# Get logger for this module
logger = logging.getLogger(__name__)

# Default delimiter used to join multiple texts for batch translation
DEFAULT_DELIM = "\n|||SUBTITLE_DELIMITER|||\n"

def is_english_line_enhanced(line: str) -> bool:
    """Detect if a line is English using 4-tier enhanced detection.

    Tiers:
    1. Definitely NOT English (timestamps, metadata, numbers)
    2. Common English patterns (keywords, pronouns, quoted dialogue, names)
    3. Language analysis (vowel ratio, accents)
    4. Capitalization heuristics
    """
    s = line.strip()
    if not s or len(s) < 2:
        return False

    # TIER 1: Definitely NOT English (timestamps, numbers, metadata)
    if ':' in s and '-->' in s:  # SRT timestamps like "00:00:01,000 --> 00:00:05,000"
        return False
    if s.isdigit():  # Pure numbers (sequence numbers)
        return False
    if s and s[0].isdigit() and not any(c.isalpha() for c in s):  # Just numbers with some chars
        return False

    # TIER 2: Common English patterns (HIGH confidence)
    tier2_patterns = [
        r'\b(the|and|to|of|in|is|are|was|were|be|been|being)\b',  # Keywords
        r'\b(he|she|it|we|they|you|i|me|us|him|her|my|our|your)\b',     # Pronouns
        r'\b(a|an|as|from|on|at|by|with|for|not|can|will|have|has|had|do|does|did)\b',  # Aux + prepositions
        r"['\"].*['\"]",  # Quoted dialogue
        r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b',  # Names (Thomas Jefferson)
    ]
    for pattern in tier2_patterns:
        if re.search(pattern, s, re.IGNORECASE):
            return True

    # TIER 3: Language detection via character analysis
    # English: 25-45% vowels, 0-2 accents
    # Spanish: 35-50% vowels, 2+ accents
    vowels = len([c for c in s.lower() if c in 'aeiou'])
    vowel_ratio = vowels / max(len(s), 1)
    accents = len([c for c in s if c in 'áéíóúñü'])

    if vowel_ratio > 0.25 and accents < 2:
        return True

    # TIER 4: Last resort - check if starts with capital letter and has enough letters
    first_alpha = next((c for c in s if c.isalpha()), None)
    if first_alpha and first_alpha.isupper():  # Likely dialogue start
        alpha_ratio = sum(1 for c in s if c.isalpha()) / max(len(s), 1)
        if alpha_ratio > 0.5:
            return True

    return False


# Keep old implementation as backup
def is_english_line(line: str) -> bool:
    """Original English line detection (simple version, kept for compatibility)."""
    s = line.strip()
    if not s:
        return False
    low = s.lower()
    english_keywords = [
        " the ", " and ", " to ", " of ", " in ",
        " is ", " are ", " was ", " were ", " that ", " this ", " with "
    ]
    if any(k in low for k in english_keywords) and sum(1 for ch in s if ch.isalpha()) / max(len(s), 1) > 0.4:
        return True
    letters = sum(1 for ch in s if ch.isalpha())
    ratio = letters / max(len(s), 1)
    return ratio > 0.6

def translate_batch_text(texts: List[str], translator, max_retries: int = 3, delimiter: str = DEFAULT_DELIM) -> List[str]:
    """Translate batch of text with detailed error logging and exponential backoff.

    Falls back to returning original texts if all retries exhausted.
    """
    import time
    import requests

    batch = delimiter.join(texts)
    logger.debug(f"Batch translation: {len(texts)} lines, {len(batch)} chars")

    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempt {attempt + 1}/{max_retries} - Translating {len(texts)} lines ({len(batch)} chars)")
            translated = translator.translate(batch)

            # Validate delimiter wasn't lost in translation
            if delimiter not in translated:
                logger.warning(f"Delimiter possibly lost in translation output")

            # Split by delimiter
            parts = translated.split(delimiter)
            if len(parts) != len(texts):
                logger.warning(f"Expected {len(texts)} parts after split, got {len(parts)}")

            result = [p.strip() for p in parts]
            logger.debug(f"✅ Batch translation SUCCESS: {len(texts)} lines translated")
            return result

        except requests.exceptions.Timeout as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries} timeout: {str(e)[:100]}")
            if attempt == max_retries - 1:
                logger.error(f"❌ Batch translation FAILED after {max_retries} attempts (timeout) - returning original")
                return texts

        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries} connection error: {str(e)[:100]}")
            if attempt == max_retries - 1:
                logger.error(f"❌ Batch translation FAILED (connection error) - returning original")
                return texts

        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries} error ({type(e).__name__}): {str(e)[:100]}")
            if attempt == max_retries - 1:
                logger.error(f"❌ Batch translation FAILED: {len(texts)} lines returned untranslated")
                return texts

        # Exponential backoff: 1s, 2s, 4s
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt
            logger.debug(f"Waiting {wait_time}s before retry...")
            time.sleep(wait_time)

    return texts

def translate_text(text: str, translator, max_retries: int = 3) -> str:
    """Translate single text with retry logic and logging."""
    import time
    import requests

    if not text or not text.strip():
        return text

    for attempt in range(max_retries):
        try:
            logger.debug(f"Single translation attempt {attempt + 1}/{max_retries}: {len(text)} chars")
            result = translator.translate(text)
            logger.debug(f"✅ Single translation SUCCESS")
            return result

        except requests.exceptions.Timeout:
            logger.warning(f"Attr {attempt + 1}/{max_retries} timeout on single text")
            if attempt == max_retries - 1:
                logger.error(f"❌ Single translation FAILED (timeout)")
                return text

        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries} error on single text: {str(e)[:100]}")
            if attempt == max_retries - 1:
                logger.error(f"❌ Single translation FAILED")
                return text

        # Exponential backoff
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt
            time.sleep(wait_time)

    return text

def batch_by_size(lines: List[str], max_chars: int, delimiter: str = DEFAULT_DELIM) -> List[List[str]]:
    batches: List[List[str]] = []
    current: List[str] = []
    current_len = 0
    for line in lines:
        add_len = len(line)
        if current:
            add_len += len(delimiter)
        if current and (current_len + add_len) > max_chars:
            batches.append(current)
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += add_len
    if current:
        batches.append(current)
    return batches


def optimize_batch_size(lines_to_translate: List[str]) -> int:
    """Determine optimal batch size based on content characteristics.

    Returns:
        int: Optimal batch character limit (3000-8000)
    """
    if not lines_to_translate:
        return 5000

    avg_line_len = sum(len(l) for l in lines_to_translate) / len(lines_to_translate)

    # Adaptive batching:
    # - Short lines (avg <50 chars): batch up to 8000 chars
    # - Medium lines (50-100 chars): batch up to 6000 chars
    # - Long lines (>100 chars): batch up to 3000 chars
    if avg_line_len < 50:
        logger.debug(f"Short lines detected (avg {avg_line_len:.1f} chars) → using 8000 char batches")
        return 8000
    elif avg_line_len < 100:
        logger.debug(f"Medium lines detected (avg {avg_line_len:.1f} chars) → using 6000 char batches")
        return 6000
    else:
        logger.debug(f"Long lines detected (avg {avg_line_len:.1f} chars) → using 3000 char batches")
        return 3000


def create_smart_batches(lines: List[str], target_batch_chars: int = 5000) -> List[List[str]]:
    """Create batches with intelligent sizing - no sentence splitting.

    Ensures lines aren't split across batches using delimiter logic.
    """
    batches = []
    current_batch = []
    current_size = 0

    for line in lines:
        line_len = len(line)

        # If adding this line exceeds limit, finalize current batch
        if current_batch and (current_size + line_len) > target_batch_chars:
            batches.append(current_batch)
            current_batch = [line]
            current_size = line_len
        else:
            current_batch.append(line)
            current_size += line_len

    if current_batch:
        batches.append(current_batch)

    logger.debug(f"Created {len(batches)} smart batches (max {target_batch_chars} chars each)")
    return batches


def translate_batches_parallel(batches: List[List[str]], translator,
                               max_workers: int = 2) -> List[List[str]]:
    """Translate multiple batches in parallel using ThreadPoolExecutor.

    Args:
        batches: List of line batches to translate
        translator: Translation object with translate() method
        max_workers: Number of parallel workers (default 2, max recommended 3)

    Returns:
        List of translated batches (same structure as input)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not batches:
        return []

    if len(batches) == 1:
        # Single batch - no need for parallelization
        translated = translate_batch_text(batches[0], translator)
        return [translated]

    logger.info(f"Starting parallel translation of {len(batches)} batches with {max_workers} workers")
    translated_batches = [None] * len(batches)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all batches
        futures = {
            executor.submit(translate_batch_text, batch, translator): idx
            for idx, batch in enumerate(batches)
        }

        completed = 0
        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result()
                translated_batches[idx] = result
                completed += 1
                logger.debug(f"Batch {idx + 1}/{len(batches)} completed ({completed}/{len(batches)})")
            except Exception as e:
                logger.error(f"Batch {idx} failed in parallel processing: {e}")
                translated_batches[idx] = batches[idx]  # Fallback to original

    logger.info(f"Parallel translation complete: {completed}/{len(batches)} batches")
    return translated_batches

def has_embedded_subtitles(video_path: Path) -> bool:
    """Check if video has embedded subtitles using ffmpeg."""
    if ffmpeg is None:
        return False
    try:
        probe = ffmpeg.probe(str(video_path))
        streams = probe.get('streams', [])
        for stream in streams:
            if stream.get('codec_type') == 'subtitle':
                return True
        return False
    except Exception:
        return False

def get_subtitle_streams(video_path: Path) -> List[Dict]:
    """Get subtitle streams info from video.

    Returns:
        List of dicts with keys: subtitle_index, codec, language, title
    """
    if ffmpeg is None:
        return []
    try:
        probe = ffmpeg.probe(str(video_path))
        streams = probe.get('streams', [])
        subtitle_streams = []
        for s in streams:
            if s.get('codec_type') == 'subtitle':
                subtitle_index = len(subtitle_streams)
                subtitle_streams.append({
                    'subtitle_index': subtitle_index,
                    'codec': s.get('codec_name', 'unknown'),
                    'language': s.get('tags', {}).get('language', 'unknown'),
                    'title': s.get('tags', {}).get('title', f'Subtítulo {subtitle_index}')
                })
        return subtitle_streams
    except Exception:
        return []

def extract_subtitles(video_path: Path, output_path: Path, stream_index: int = 0) -> bool:
    """Extract subtitles from video using ffmpeg.

    Args:
        video_path: Path to the video file
        output_path: Path where to save the .srt file
        stream_index: Index of the subtitle stream to extract (default: 0)

    Returns:
        True if extraction succeeded, False otherwise
    """
    if ffmpeg is None:
        return False
    try:
        stream = ffmpeg.input(str(video_path))
        stream = ffmpeg.output(stream, str(output_path), map=f'0:s:{stream_index}')
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        return True
    except Exception:
        return False
