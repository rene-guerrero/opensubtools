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


def clean_subtitle_text(text: str) -> str:
    """Remove XML/HTML tags and SSA/ASS formatting from subtitle text.
    
    Examples:
        {\\an5}<font face="Paper Johnny Eins" size="36" color="#ffb504"></font>ge
        -> ge
        
        <i>Hello</i> <b>world</b>
        -> Hello world
    """
    # Remove SSA/ASS tags like {\an5}, {\pos(100,100)}, etc.
    text = re.sub(r'\{[^}]*\}', '', text)
    
    # Remove XML/HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    return text


def is_srt_spanish(srt_path: Path) -> bool:
    """Check if an SRT file is in Spanish (not English).
    
    Returns True if the file is determined to be in Spanish.
    Uses multiple heuristics:
    - Presence of Spanish accents (áéíóúñ)
    - Common Spanish words
    - Absence of clear English indicators
    
    IMPORTANT: Strips XML/HTML tags before analysis to avoid false positives
    from English attribute names like face="Arial", color="#fff", etc.
    """
    try:
        text = srt_path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        
        spanish_indicators = 0
        english_indicators = 0
        total_text_lines = 0
        
        # Spanish-specific patterns
        spanish_words = [
            ' el ', ' la ', ' los ', ' las ', ' un ', ' una ', ' es ', ' son ',
            ' está ', ' están ', ' fue ', ' fueron ', ' con ', ' por ', ' para ',
            ' que ', ' quien ', ' donde ', ' cuando ', ' como ', ' pero ', ' más ',
            ' muy ', ' bien ', ' aquí ', ' allí ', ' ahora ', ' después ', ' antes',
            ' este ', ' esta ', ' estos ', ' estas ', ' ese ', ' esa ', ' eso ',
            ' había ', ' tenía ', ' puede ', ' puedes ', ' podemos ', ' debemos ',
            ' gracias ', ' por favor ', ' buenos días ', ' buenas noches ', ' hola ',
            ' señor ', ' señora ', ' señorita ', ' doctor ', ' doctora ', ' claro ',
            ' entiendo ', ' comprendo ', ' verdad ', ' seguro ', ' todo ',
            ' nada ', ' algo ', ' alguien ', ' nadie ', ' siempre ', ' nunca ',
            ' también ', ' tampoco ', ' quizás ', ' tal vez ', ' mejor ', ' peor ',
            ' años ', ' día ', ' tiempo ', ' vida ', ' manera ', ' forma ',
            ' casa ', ' trabajo ', ' mundo ', ' persona ', ' lugar ', ' momento '
        ]
        
        for line in lines:
            s = line.strip()
            if not s or s.isdigit() or '-->' in s:
                continue  # Skip empty lines, sequence numbers, timestamps
            
            # Clean the line: remove XML/HTML/SSA tags
            clean_text = clean_subtitle_text(s)
            if not clean_text.strip():
                continue  # Skip if line is only tags
            
            total_text_lines += 1
            low = clean_text.lower()
            
            # Check for Spanish accents (strong indicator)
            if any(c in clean_text for c in 'áéíóúñüÁÉÍÓÚÑÜ'):
                spanish_indicators += 3  # Strong indicator
            
            # Check for common Spanish words
            for word in spanish_words:
                if word in low:
                    spanish_indicators += 1
                    break
            
            # Check for English indicators (common English words not in Spanish)
            english_words = [' the ', ' and ', ' to ', ' of ', ' in ', ' is ', ' are ', ' was ', ' were ',
                           ' this ', ' that ', ' with ', ' for ', ' it ', ' you ', ' he ', ' she ']
            if any(word in low for word in english_words):
                english_indicators += 2
        
        # Decision logic
        if total_text_lines == 0:
            return False  # Empty or invalid SRT
        
        # If we found Spanish indicators and few/no English indicators
        if spanish_indicators > 0 and english_indicators == 0:
            return True
        
        # If Spanish indicators outweigh English indicators significantly
        if spanish_indicators > english_indicators * 1.5:
            return True
        
        # If significant portion of lines have Spanish accents
        if spanish_indicators >= 3 and english_indicators < 3:
            return True
        
        return False
    except Exception:
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
    """Translate batch of text with formatting handling.

    Removes formatting tags before translation and restores them after.
    Falls back to returning original texts if all retries exhausted.
    """
    import time
    import requests

    # Step 1: Clean texts by removing formatting tags
    cleaned_texts = []
    formatting_info = []

    for text in texts:
        clean, tags = strip_formatting_from_text(text)
        cleaned_texts.append(clean)
        formatting_info.append((text, tags))

    # Step 2: Join cleaned texts for batch translation
    batch = delimiter.join(cleaned_texts)

    for attempt in range(max_retries):
        try:
            translated = translator.translate(batch)

            # Split by delimiter (ignoring any part count mismatches)
            parts = translated.split(delimiter)

            # Step 3: Restore formatting to translated parts
            result = []
            for i, (orig_text, tags) in enumerate(formatting_info):
                translated_part = parts[i].strip() if i < len(parts) else cleaned_texts[i]
                restored = apply_formatting_after_translation(translated_part, orig_text)
                result.append(restored)

            return result

        except requests.exceptions.Timeout as e:
            if attempt == max_retries - 1:
                raise Exception(f"Translation timeout after {max_retries} retries") from e

        except requests.exceptions.ConnectionError as e:
            if attempt == max_retries - 1:
                raise Exception(f"Connection error after {max_retries} retries") from e

        except Exception as e:
            if attempt == max_retries - 1:
                raise Exception(f"Translation failed after {max_retries} retries: {str(e)}") from e

        # Exponential backoff: 1s, 2s, 4s
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt
            time.sleep(wait_time)

    return texts

def translate_text(text: str, translator, max_retries: int = 3) -> str:
    """Translate single text with retry logic and formatting handling."""
    import time
    import requests

    if not text or not text.strip():
        return text

    # Clean formatting before translation
    clean_text, tags = strip_formatting_from_text(text)
    if not clean_text or not clean_text.strip():
        return text

    for attempt in range(max_retries):
        try:
            result = translator.translate(clean_text)
            formatted_result = apply_formatting_after_translation(result, text)
            return formatted_result

        except requests.exceptions.Timeout:
            if attempt == max_retries - 1:
                return text

        except Exception:
            if attempt == max_retries - 1:
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
        return 8000
    elif avg_line_len < 100:
        return 6000
    else:
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

    return batches


def translate_batches_parallel(batches: List[List[str]], translator,
                               max_workers: int = 2, progress_callback=None) -> List[List[str]]:
    """Translate multiple batches in parallel using ThreadPoolExecutor.

    Args:
        batches: List of line batches to translate
        translator: Translation object with translate() method
        max_workers: Number of parallel workers (default 2, max recommended 3)
        progress_callback: Optional callback function(current, total) to report progress

    Returns:
        List of translated batches (same structure as input)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not batches:
        return []

    if len(batches) == 1:
        # Single batch - no need for parallelization
        translated = translate_batch_text(batches[0], translator)
        if progress_callback:
            progress_callback(1, 1)
        return [translated]

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
                if progress_callback:
                    progress_callback(completed, len(batches))
            except Exception as e:
                # Log and raise the actual error instead of silencing it
                logger.error(f"Batch {idx} translation failed: {type(e).__name__}: {str(e)}")
                raise

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
                    'title': s.get('tags', {}).get('title', f'Subtitle {subtitle_index}')
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


def strip_formatting_from_text(text: str) -> tuple[str, List[tuple]]:
    r"""Extract plain text from HTML/XML/SSA formatting.

    Removes:
    - HTML/XML tags: <font ...>, </font>, <b>, </b>, etc.
    - SSA/ASS alignment codes: {\an5}, {\c&H...}, etc.
    - WebVTT tags: <v Name>, <c ...>, etc.

    Args:
        text: Text with potential formatting tags

    Returns:
        (clean_text, tag_info) where tag_info is list of (position, tag, length)
        for later restoration
    """
    # Keep track of removed elements for restoration
    tag_info = []
    clean_text = text
    offset = 0

    # Pattern 1: HTML/XML tags like <font ...>, </font>, <b>, etc.
    html_pattern = r'</?(?:font|b|i|u|br|color|v|c)[^>]*>'
    for match in re.finditer(html_pattern, text):
        pos = match.start() - offset
        tag = match.group()
        tag_info.append((pos, tag))
        clean_text = clean_text[:pos] + clean_text[pos + len(tag):]
        offset += len(tag)

    # Pattern 2: SSA/ASS codes like {\an5} or {\c&HFFB504&}
    ssa_pattern = r'\{\\[^}]+\}'
    match_count = 0
    for match in re.finditer(ssa_pattern, clean_text):
        pos = match.start()
        tag = match.group()
        tag_info.insert(match_count, (pos, tag))
        clean_text = clean_text[:pos] + clean_text[pos + len(tag):]
        match_count += 1

    return clean_text, tag_info


def restore_formatting_to_text(clean_text: str, tag_info: List[tuple], original_text: str) -> str:
    """Restore formatting tags back to text.

    Attempts to find original formatting structure and apply to translated text.
    Falls back to original if restoration fails.

    Args:
        clean_text: The original clean text (before translation removes it!)
        tag_info: List of (position, tag) tuples from strip_formatting_from_text()
        original_text: The original text with formatting

    Returns:
        Text with formatting restored or original text if restoration fails
    """
    if not tag_info:
        return original_text

    try:
        # If translation significantly changed text length, return formattings at start and end
        # This is safer than trying to match positions in changed text

        # Get all leading tags/codes
        leading_tags = []
        trailing_tags = []

        # Extract leading formatting
        text_copy = original_text
        leading_offset = 0
        for pos, tag in tag_info:
            if pos < 50:  # Likely leading formatting
                leading_tags.append(tag)
                text_copy = text_copy.replace(tag, '', 1)
                leading_offset += len(tag)
            elif pos > len(original_text) - 50:  # Likely trailing
                trailing_tags.append(tag)

        # Prepend leading tags
        result = ''.join(leading_tags) + clean_text + ''.join(trailing_tags)
        return result

    except Exception:
        return original_text


def clean_subtitle_line_for_translation(line: str) -> tuple[str, str]:
    """Clean a subtitle line for translation by removing formatting.

    Returns:
        (clean_text, original_text) tuple
    """
    stripped, _ = strip_formatting_from_text(line)
    return stripped.strip(), line


def apply_formatting_after_translation(clean_text: str, dirty_original: str) -> str:
    """Apply original formatting to translated text.

    Tries to reinsert tags at the same pattern positions.

    Args:
        clean_text: The translated clean text
        dirty_original: The original text with formatting

    Returns:
        Formatted translated text
    """
    # Extract tags/codes from original
    _, tag_info = strip_formatting_from_text(dirty_original)

    if not tag_info:
        return clean_text

    # Simple strategy: put leading tags at start, trailing at end
    leading_tags = [tag for pos, tag in tag_info if pos < 20]
    trailing_tags = [tag for pos, tag in tag_info if pos >= len(dirty_original) - 20]

    return ''.join(leading_tags) + clean_text + ''.join(trailing_tags)
