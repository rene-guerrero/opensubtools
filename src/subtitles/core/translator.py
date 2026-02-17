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
    progress_callback = None
) -> bool:
    """Translate SRT file to target language using srt library.

    Args:
        input_srt: Path to input SRT file
        output_srt: Path to save translated SRT
        target_lang: Target language code (default: 'es')
        use_enhanced: Ignored (kept for compatibility)
        use_parallel: Ignored (kept for compatibility)
        progress_callback: Optional callback function for progress updates (0.0 to 1.0)

    Returns:
        True if translation succeeded
    """
    logger.info(f"Translating {input_srt.name} to {target_lang}")

    # Read and parse SRT file
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

    # Use separator that won't be translated
    separator = "|||<||>|"
    max_chars = 4500

    try:
        all_texts = [sub.content for sub in subtitles]

        # Build chunks
        chunks = []
        current = []
        current_len = 0

        for text in all_texts:
            if current_len + len(text) + len(separator) > max_chars and current:
                chunks.append(separator.join(current))
                current = []
                current_len = 0
            current.append(text)
            current_len += len(text) + len(separator)

        if current:
            chunks.append(separator.join(current))

        logger.info(f"Translating {len(chunks)} chunks...")

        # Translate with 5 workers
        def translate_chunk(args):
            idx, chunk = args
            try:
                trans = GoogleTranslator(source='en', target=target_lang).translate(chunk)
                return idx, trans if trans else chunk
            except:
                return idx, chunk

        results = {}
        completed = 0

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(translate_chunk, (i, c)): i for i, c in enumerate(chunks)}
            for future in as_completed(futures):
                idx, result = future.result()
                results[idx] = result
                completed += 1
                if progress_callback:
                    progress_callback(completed / len(chunks))

        time.sleep(0.5)

        # Rebuild subtitles
        result_idx = 0
        for idx in sorted(results.keys()):
            parts = results[idx].split(separator)
            for part in parts:
                if result_idx < len(subtitles):
                    subtitles[result_idx].content = part.strip()
                    result_idx += 1

        # Write translated SRT
        output_content = srt.compose(subtitles)
        output_srt.write_text(output_content, encoding='utf-8')
        logger.info(f"Saved to: {output_srt.name}")
        return True

    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return False


def find_and_translate_local_srt(
    video_path: Path,
    output_srt: Path,
    target_lang: str = 'es'
) -> bool:
    """Find local SRT and translate if needed.

    Args:
        video_path: Path to video file
        output_srt: Path to save translated SRT
        target_lang: Target language code

    Returns:
        True if found and translated successfully
    """
    from subtitles.utils.translate import is_srt_spanish

    # Find local SRT
    local_srt = find_local_srt(video_path)
    if not local_srt:
        return False

    logger.info(f"Found local .srt file: {local_srt.name}")

    # Check if it's already in target language
    if target_lang == 'es' and is_srt_spanish(local_srt):
        logger.info("File is already in Spanish, copying...")
        content = local_srt.read_text(encoding='utf-8', errors='ignore')
        output_srt.write_text(content, encoding='utf-8')
        return True

    # Translate to target language
    logger.info(f"Translating to {target_lang}...")
    return translate_srt_file(local_srt, output_srt, target_lang=target_lang)
