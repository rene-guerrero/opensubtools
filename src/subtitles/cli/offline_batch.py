#!/usr/bin/env python3
"""CLI for batch subtitle generation using the offline translation model.

Same pipeline as the online batch (extract the English track, clean the
typeset markup, translate, write an .srt beside the video) but the
translation runs locally, so a whole series can go through in one pass.

Usage:
  python -m subtitles.cli.offline_batch "path/to/videos/folder"
"""

import argparse
import sys
import time
from pathlib import Path

import srt

from subtitles.core.cleaner import clean_and_merge_subtitles
from subtitles.core.extractor import extract_english_subtitles, extract_subtitles_by_language
from subtitles.core.offline import OfflineModelMissing, model_dir, translate_texts
from subtitles.utils.config import get_config, load_config, LANGUAGE_CODE_MAP
from subtitles.utils.logging_config import get_logger
from subtitles.utils.paths import sort_paths_naturally

logger = get_logger()


def find_video_files(folder_path: Path, config) -> list:
    """Recursively find all video files, ordered the way episodes run."""
    formats = tuple(config.video_formats)
    videos = [
        p for p in folder_path.rglob("*")
        if p.is_file() and p.suffix.lower() in formats
    ]
    return sort_paths_naturally(videos)


def process_video(video: Path, target_lang: str) -> str:
    """Generate one subtitle file.

    Returns:
        'done', 'skipped', or a short reason for the failure.
    """
    output_srt = video.parent / f"{video.stem}.srt"
    if output_srt.exists():
        return "skipped"

    temp_srt = video.parent / f"{video.stem}.temp.srt"

    try:
        # An existing track in the target language beats translating.
        lang_codes = LANGUAGE_CODE_MAP.get(target_lang, [target_lang])
        if extract_subtitles_by_language(video, temp_srt, lang_codes):
            temp_srt.rename(output_srt)
            return "done"

        if not extract_english_subtitles(video, temp_srt):
            return "no english track"

        subtitles = list(srt.parse(temp_srt.read_text(encoding="utf-8", errors="ignore")))
        subtitles = clean_and_merge_subtitles(subtitles)
        if not subtitles:
            return "no dialogue after cleanup"

        # Typeset tracks repeat the same text many times; translate each
        # distinct text once and map it back to every cue.
        unique = list(dict.fromkeys(s.content for s in subtitles))
        translated = translate_texts(unique)
        mapping = dict(zip(unique, translated))

        for sub in subtitles:
            sub.content = mapping.get(sub.content, sub.content)

        output_srt.write_text(srt.compose(subtitles), encoding="utf-8")
        return "done"

    finally:
        temp_srt.unlink(missing_ok=True)
        for leftover in video.parent.glob(f"{video.stem}.temp.*.srt"):
            leftover.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch generate subtitles using the offline translation model"
    )
    parser.add_argument("folder", help="Folder to search for video files")
    parser.add_argument("--language", default="es", help="Target language code (default: es)")
    parser.add_argument("--config", default=None, help="Optional path to config.yaml")
    parser.add_argument("--limit", type=int, default=0, help="Stop after N videos (0 = all)")
    args = parser.parse_args()

    if args.config:
        load_config(args.config)

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"ERROR: Not a folder: {folder}")
        sys.exit(1)

    videos = find_video_files(folder, get_config())
    if not videos:
        print("No video files found")
        sys.exit(0)

    if args.limit:
        videos = videos[:args.limit]

    print(f"Model:  {model_dir()}")
    print(f"Found:  {len(videos)} video(s)\n")

    counts = {"done": 0, "skipped": 0, "failed": 0}
    failures = []
    started = time.time()

    for index, video in enumerate(videos, 1):
        label = f"[{index}/{len(videos)}] {video.name[:60]}"
        print(f"{label} ... ", end="", flush=True)

        t0 = time.time()
        try:
            result = process_video(video, args.language)
        except OfflineModelMissing as error:
            print("MODEL MISSING")
            print(f"\n{error}")
            sys.exit(1)
        except Exception as error:
            result = f"{type(error).__name__}: {error}"

        if result == "done":
            counts["done"] += 1
            print(f"OK ({time.time() - t0:.1f}s)")
        elif result == "skipped":
            counts["skipped"] += 1
            print("skipped (already has .srt)")
        else:
            counts["failed"] += 1
            failures.append((video.name, result))
            print(f"FAILED - {result}")

    elapsed = time.time() - started
    print(f"\n{'=' * 60}")
    print(f"Done in {elapsed / 60:.1f} min")
    print(f"  Translated: {counts['done']}")
    print(f"  Skipped:    {counts['skipped']}")
    print(f"  Failed:     {counts['failed']}")
    if failures:
        print("\nFailures:")
        for name, reason in failures:
            print(f"  {name[:60]}: {reason}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
