#!/usr/bin/env python3
"""Core subtitle translation logic."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional
import srt
from deep_translator import GoogleTranslator
from subtitles.utils.logging_config import get_logger

logger = get_logger()


def find_local_srt(video_path: Path) -> Optional[Path]:
    """Search for a .srt file with the same base name as video."""
    possible_srt = video_path.parent / f"{video_path.stem}.srt"
    return possible_srt if possible_srt.exists() else None


def translate_srt_file(
    input_srt: Path,
    output_srt: Path,
    target_lang: str = 'es',
    use_enhanced: bool = True,
    use_parallel: bool = False,
    progress_callback = None,
    retry_untranslated: bool = True
) -> bool:
    """Translate SRT file to target language using srt library.

    Args:
        input_srt: Path to input SRT file
        output_srt: Path to save translated SRT
        target_lang: Target language code (default: 'es')
        use_enhanced: Ignored (kept for compatibility)
        use_parallel: Ignored (kept for compatibility)
        progress_callback: Optional callback function for progress updates (0.0 to 1.0)
        retry_untranslated: If True, retry translation for subtitles that remain untranslated (default: True)

    Returns:
        True if translation succeeded
    """
    logger.info(f"Translating {input_srt.name} to {target_lang}")
    logger.info(f"Input path exists before read: {input_srt.exists()}")
    logger.info(f"Input path absolute: {input_srt.absolute()}")

    try:
        content = input_srt.read_text(encoding='utf-8', errors='ignore')
        subtitles = list(srt.parse(content))
    except Exception as e:
        logger.error(f"Failed to parse SRT: {e}")
        return False

    if not subtitles:
        logger.error("No subtitles found")
        return False

    logger.info(f"Translating {len(subtitles)} subtitle entries")

    separator = "|||<||>|"
    max_chars = 4500

    def translate_chunks(texts: list, separator: str, max_chars: int, target_lang: str):
        """Translate a list of texts in chunks."""
        chunks = []
        current = []
        current_len = 0

        for text in texts:
            if current_len + len(text) + len(separator) > max_chars and current:
                chunks.append(separator.join(current))
                current = []
                current_len = 0
            current.append(text)
            current_len += len(text) + len(separator)

        if current:
            chunks.append(separator.join(current))

        logger.info(f"Translating {len(chunks)} chunks...")

        def translate_chunk(args):
            idx, chunk = args
            try:
                trans = GoogleTranslator(source='en', target=target_lang).translate(chunk)
                return idx, trans if trans else chunk, trans is None
            except Exception:
                return idx, chunk, True

        results = {}

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(translate_chunk, (i, c)): i for i, c in enumerate(chunks)}
            for future in as_completed(futures):
                idx, result, failed = future.result()
                results[idx] = result

        time.sleep(0.5)
        return results

    all_original_texts = [sub.content for sub in subtitles]
    results = translate_chunks(all_original_texts, separator, max_chars, target_lang)

    translated_contents = []
    for idx in sorted(results.keys()):
        parts = results[idx].split(separator)
        translated_contents.extend([p.strip() for p in parts])

    while len(translated_contents) < len(subtitles):
        translated_contents.append("")

    for i, sub in enumerate(subtitles):
        if i < len(translated_contents):
            sub.content = translated_contents[i]

    untranslated_indices = []
    for i, sub in enumerate(subtitles):
        if i < len(all_original_texts):
            if sub.content.strip().lower() == all_original_texts[i].strip().lower():
                untranslated_indices.append(i)

    if retry_untranslated and untranslated_indices:
        logger.info(f"Found {len(untranslated_indices)} untranslated subtitles, retrying...")
        
        texts_to_retry = [subtitles[i].content for i in untranslated_indices]
        retry_results = translate_chunks(texts_to_retry, separator, max_chars, target_lang)

        retry_contents = []
        for idx in sorted(retry_results.keys()):
            parts = retry_results[idx].split(separator)
            retry_contents.extend([p.strip() for p in parts])

        for i, orig_idx in enumerate(untranslated_indices):
            if i < len(retry_contents):
                subtitles[orig_idx].content = retry_contents[i]

    final_untranslated = 0
    for i, sub in enumerate(subtitles):
        if i < len(all_original_texts):
            if sub.content.strip().lower() == all_original_texts[i].strip().lower():
                final_untranslated += 1

    if final_untranslated > 0:
        logger.warning(f"{final_untranslated} subtitles may remain untranslated")

    try:
        output_content = srt.compose(subtitles)
        output_srt.write_text(output_content, encoding='utf-8')
        logger.info(f"Saved to: {output_srt.name}")
        return True
    except Exception as e:
        logger.error(f"Failed to write SRT: {e}")
        return False


def find_and_translate_local_srt(
    video_path: Path,
    output_srt: Path,
    target_lang: str = 'es'
) -> bool:
    """Disabled - always return False to regenerate from scratch."""
    return False
