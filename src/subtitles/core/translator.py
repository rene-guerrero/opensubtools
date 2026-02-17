#!/usr/bin/env python3
"""Core subtitle translation logic.

Handles translation of SRT content from English to Spanish.
"""

from pathlib import Path
from typing import Optional, List

from deep_translator import GoogleTranslator

from subtitles.utils.config import get_config
from subtitles.utils.logging_config import get_logger
from subtitles.utils.translate import (
    translate_batch_text,
    translate_text,
    is_english_line,
    is_english_line_enhanced,
    is_srt_spanish,
    create_smart_batches,
    optimize_batch_size,
    translate_batches_parallel,
    DEFAULT_DELIM
)

logger = get_logger()


def find_local_srt(video_path: Path) -> Optional[Path]:
    """Search for a .srt file with the same base name as video.

    Args:
        video_path: Path to the video file

    Returns:
        Path to .srt file or None if not found
    """
    possible_srt = video_path.parent / f"{video_path.stem}.srt"
    return possible_srt if possible_srt.exists() else None


def translate_srt_file(
    input_srt: Path, 
    output_srt: Path, 
    use_enhanced: bool = True,
    use_parallel: bool = True
) -> bool:
    """Translate SRT file from English to Spanish.

    Args:
        input_srt: Path to input SRT file
        output_srt: Path to save translated SRT
        use_enhanced: Use enhanced English detection
        use_parallel: Use parallel translation

    Returns:
        True if translation succeeded
    """
    config = get_config()
    translator = GoogleTranslator(source='en', target='es')

    try:
        text = input_srt.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"Could not read input file: {e}")
        return False

    lines = text.splitlines(True)
    
    # Detect English lines
    detection_func = is_english_line_enhanced if use_enhanced else is_english_line
    eng_indices = [i for i, line in enumerate(lines) if detection_func(line)]

    if not eng_indices:
        # No English content, copy as-is
        output_srt.write_text(text, encoding="utf-8")
        return True

    logger.info(f"Translating {len(eng_indices)} lines to Spanish")

    translated_lines = list(lines)
    translation_cache: dict = {}

    # Extract lines to translate
    lines_to_translate = [lines[idx].rstrip("\n") for idx in eng_indices]

    # Determine optimal batch size and create batches
    optimal_batch_size = optimize_batch_size(lines_to_translate)
    batch_lines_list = create_smart_batches(lines_to_translate, optimal_batch_size)

    # Translate batches
    batch_failed = False

    if len(batch_lines_list) > 1 and use_parallel:
        translated_batches = translate_batches_parallel(
            batch_lines_list, translator,
            max_workers=config.parallel_workers,
            progress_callback=lambda c, t: logger.debug(f"Progress: {int(c/t*100)}%")
        )
    else:
        translated_batches = []
        for i, batch in enumerate(batch_lines_list):
            logger.debug(f"Batch {i+1}/{len(batch_lines_list)}")
            translated_batches.append(translate_batch_text(batch, translator))

    # Check if batch translation succeeded
    for batch_idx, (original_batch, translated_batch) in enumerate(
        zip(batch_lines_list, translated_batches)
    ):
        if translated_batch == original_batch:
            batch_failed = True
        else:
            # Cache successful translations
            for orig, trans in zip(original_batch, translated_batch):
                translation_cache[orig] = trans

    # If batch succeeded, use cached translations
    if not batch_failed and translation_cache:
        for idx in eng_indices:
            original = lines[idx].rstrip("\n")
            if original in translation_cache:
                translated_lines[idx] = translation_cache[original] + (
                    "\n" if lines[idx].endswith("\n") else ""
                )

        output_srt.write_text("".join(translated_lines), encoding="utf-8")
        logger.info(f"Translation saved to: {output_srt.name}")
        return True

    # Fallback: translate individual lines
    logger.warning("Batch translation failed, trying individual lines")
    failed_count = 0

    for progress_idx, idx in enumerate(eng_indices):
        original = lines[idx].rstrip("\n")

        # Check cache first
        if original in translation_cache:
            translated = translation_cache[original]
            translated_lines[idx] = translated + (
                "\n" if lines[idx].endswith("\n") else ""
            )
            continue

        # Translate individual line
        try:
            translated = translate_text(original, translator)

            if translated != original:
                translated_lines[idx] = translated + (
                    "\n" if lines[idx].endswith("\n") else ""
                )
                translation_cache[original] = translated
            else:
                failed_count += 1

        except Exception:
            failed_count += 1

    if failed_count > 0:
        logger.warning(f"{failed_count} lines could not be translated")

    output_srt.write_text("".join(translated_lines), encoding="utf-8")
    logger.info(f"Translation saved to: {output_srt.name}")
    return True


def find_and_translate_local_srt(video_path: Path, output_srt: Path) -> bool:
    """Search for .srt file with same name in folder. Translate if in English.

    Args:
        video_path: Path to video file
        output_srt: Path to save translated SRT

    Returns:
        True if found and processed successfully
    """
    logger.info("Searching for local .srt file...")

    possible_srt = video_path.parent / f"{video_path.stem}.srt"

    if not possible_srt.exists():
        logger.debug(f"Not found: {possible_srt.name}")
        return False

    logger.info(f"Found: {possible_srt.name}")

    # Check if it's in Spanish
    if is_srt_spanish(possible_srt):
        logger.info("File is already in Spanish, copying...")
        text = possible_srt.read_text(encoding="utf-8", errors="ignore")
        output_srt.write_text(text, encoding="utf-8")
        return True

    # File appears to be in English, translate it
    logger.info("File appears to be in English, translating...")
    try:
        translate_srt_file(possible_srt, output_srt)
        logger.info(f"Saved as: {output_srt.name}")
        return True
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return False
