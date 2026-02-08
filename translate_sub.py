#!/usr/bin/env python3
"""Translate an English .srt file to Spanish. Produces a new .srt next to it."""
import argparse
from pathlib import Path
from typing import Optional

from deep_translator import GoogleTranslator
from translate_utils import (
    is_english_line,
    translate_batch_text,
    DEFAULT_DELIM
)
from config import get_config, load_config
from logging_config import get_logger

logger = get_logger()


def main() -> None:
    """Main entry point for SRT translation."""
    parser = argparse.ArgumentParser(
        description="Translate English .srt subtitles to Spanish",
        epilog="Translates only English lines, preserves numbering and timing"
    )
    parser.add_argument("path", help="Path to the input .srt file")
    parser.add_argument(
        "--config",
        help="Optional path to config.yaml file",
        default=None
    )
    args = parser.parse_args()

    # Load config if specified
    if args.config:
        load_config(args.config)

    config = get_config()
    input_path = Path(args.path)

    if not input_path.exists():
        logger.error(f"File not found: {input_path}")
        raise SystemExit(1)

    # Validate file type: only allow .srt subtitle files
    if input_path.suffix.lower() != ".srt":
        logger.error(f"Invalid format: expected .srt, got {input_path.suffix}")
        raise SystemExit(1)

    logger.info(f"Loading: {input_path.name}")
    text = input_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines(True)

    # Find English lines
    eng_indices = [i for i, line in enumerate(lines) if is_english_line(line)]

    if not eng_indices:
        logger.info("No English lines detected")
        output_path = input_path.parent / f"{input_path.stem}.srt"
        output_path.write_text(text, encoding="utf-8")
        logger.info(f"Saved: {output_path.name}")
        raise SystemExit(0)

    logger.info(f"Found {len(eng_indices)} English lines to translate")

    translator = GoogleTranslator(source='en', target='es')
    translated_lines = list(lines)
    total_english = len(eng_indices)
    translated_so_far = 0

    batch_lines = []
    batch_indices = []
    max_chars = config.max_batch_chars

    for idx in eng_indices:
        line = lines[idx].rstrip("\n")
        # If adding this line would exceed max chars, translate current batch
        current_batch_len = (sum(len(lines[i]) for i in batch_indices) +
                           len(DEFAULT_DELIM) * max(0, len(batch_indices) - 1))

        if batch_indices and (current_batch_len + len(line)) > max_chars:
            translated = translate_batch_text(batch_lines, translator)
            for t, pos in zip(translated, batch_indices):
                translated_lines[pos] = t + ("\n" if lines[pos].endswith("\n") else "")
            batch_lines = []
            batch_indices = []
            translated_so_far += len(translated)
            if total_english:
                pct = int((translated_so_far / total_english) * 100)
                logger.debug(f"Progress: {pct}% ({translated_so_far}/{total_english})")

        batch_lines.append(line)
        batch_indices.append(idx)

    # Process final batch
    if batch_indices:
        translated = translate_batch_text(batch_lines, translator)
        for t, pos in zip(translated, batch_indices):
            translated_lines[pos] = t + ("\n" if lines[pos].endswith("\n") else "")
        translated_so_far += len(translated)
        if total_english:
            pct = int((translated_so_far / total_english) * 100)
            logger.debug(f"Progress: {pct}% ({translated_so_far}/{total_english})")

    # Create the translated file with the same name as the original,
    # and rename the original if it contains English
    en_path = input_path.with_name(f"{input_path.stem}.en{input_path.suffix}")
    try:
        input_path.rename(en_path)
        renamed = True
        logger.info(f"Original renamed to: {en_path.name}")
    except Exception as e:
        logger.warning(f"Could not rename original: {e}")
        renamed = False

    # Write translated version to original filename
    translated_output_path = input_path
    translated_output_path.write_text("".join(translated_lines), encoding="utf-8")
    logger.info(f"Translated subtitles saved: {translated_output_path.name}")
    raise SystemExit(0)


if __name__ == '__main__':
    main()
