#!/usr/bin/env python3
"""Generate subtitles for a video file. Downloads/extracts in Spanish or English then translates."""
import argparse
import ctypes
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from deep_translator import GoogleTranslator
from translate_utils import (
    is_english_line,
    translate_batch_text,
    DEFAULT_DELIM,
    has_embedded_subtitles,
    get_subtitle_streams,
    extract_subtitles as extract_subtitles_util
)
from config import get_config, load_config
from logging_config import get_logger

try:
    import ffmpeg
except ImportError:
    ffmpeg = None

logger = get_logger()


def validate_video_path(path_str: str) -> Path:
    """Validate and normalize video file path with detailed error reporting."""
    # First pass: strip whitespace and outer quotes
    path_str = path_str.strip().strip('"\'')

    video_path = Path(path_str)

    # Try multiple methods to check existence
    pathlib_exists = video_path.exists()
    os_path_exists = os.path.exists(str(video_path))
    os_path_isfile = os.path.isfile(str(video_path))

    # Windows-specific: use ctypes to check file access
    if sys.platform == 'win32':
        try:
            kernel32 = ctypes.windll.kernel32
            # GetFileAttributesW returns file attributes or INVALID_FILE_ATTRIBUTES (-1)
            attrs = kernel32.GetFileAttributesW(str(video_path))
            is_file = attrs != -1 and not (attrs & 0x10)  # 0x10 = FILE_ATTRIBUTE_DIRECTORY
        except Exception:
            pass

    # If using Windows long path support, try with \\?\ prefix
    if sys.platform == 'win32' and len(str(video_path.absolute())) > 260:
        long_path = f"\\\\?\\{video_path.absolute()}"
        long_exists = os.path.exists(long_path)

    # Try using Windows 'dir' command to verify file exists
    if sys.platform == 'win32':
        try:
            parent_dir = video_path.parent
            filename = video_path.name
            result = subprocess.run(
                ["cmd", "/c", f"dir /b \"{parent_dir}\" | findstr /i \"{filename}\""],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                pass
        except Exception:
            pass

    # Try listing parent directory with glob
    if video_path.parent.exists():
        try:
            parent_contents = list(video_path.parent.glob('*'))
            matches = [f for f in parent_contents if f.name.lower() == video_path.name.lower()]
            if matches:
                logger.info(f"Found matching file in directory listing: {matches[0].name}")
                return matches[0]
        except Exception:
            pass
    else:
        logger.error(f"Parent directory does not exist: {video_path.parent}")

    # Final check: if any method confirms existence, use the path
    if pathlib_exists or os_path_exists or os_path_isfile:
        logger.info(f"Video file validated: {video_path.name}")
        return video_path

    # If nothing worked, report detailed error
    logger.error(f"File not found: {video_path}")
    logger.error(f"Absolute path: {video_path.absolute()}")
    logger.error(f"Parent directory: {video_path.parent}")
    logger.error(f"Filename: {video_path.name}")

    # Last attempt: list all files in parent to see what's there
    try:
        if video_path.parent.exists():
            parent_files = list(video_path.parent.glob('*'))
            logger.error(f"Files in parent directory: {len(parent_files)}")
            # Show first few files for debugging
            for f in parent_files[:5]:
                logger.error(f"  - {f.name}")
            if len(parent_files) > 5:
                logger.error(f"  ... and {len(parent_files) - 5} more")
    except Exception as e:
        logger.error(f"Could not list parent directory: {e}")

    sys.exit(1)


def download_subtitle(video_path: Path, language: str) -> Optional[Path]:
    """Download subtitle using subliminal. Returns path to downloaded subtitle or None."""
    output_dir = video_path.parent

    cmd = [
        "subliminal",
        "download",
        "-l", language,
        "-v",
        str(video_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=output_dir, timeout=30)
    except subprocess.TimeoutExpired:
        logger.error(f"Subliminal timeout for language {language}")
        return None
    except Exception as e:
        logger.debug(f"Subliminal error: {e}")
        return None

    # Subliminal typically names the file with .lang.srt extension
    expected_srt = output_dir / f"{video_path.stem}.{language}.srt"
    if expected_srt.exists():
        return expected_srt

    # Fallback: look for any .srt file with similar name
    for srt_file in output_dir.glob(f"{video_path.stem}*.srt"):
        return srt_file

    return None


def translate_srt(input_srt: Path, output_srt: Path) -> None:
    """Translate an SRT file from English to Spanish."""
    config = get_config()
    translator = GoogleTranslator(source='en', target='es')

    text = input_srt.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines(True)

    # Identify English lines
    eng_indices = [i for i, line in enumerate(lines) if is_english_line(line)]

    if not eng_indices:
        logger.info("No English lines detected for translation")
        output_srt.write_text(text, encoding="utf-8")
        return

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
            translated = translate_batch_text(batch_lines, translator)
            for t, pos in zip(translated, batch_indices):
                translated_lines[pos] = t + ("\n" if lines[pos].endswith("\n") else "")
            batch_lines = []
            batch_indices = []
            translated_so_far += len(translated)
            if total_english:
                pct = int((translated_so_far / total_english) * 100)
                logger.debug(f"Translation progress: {pct}% ({translated_so_far}/{total_english})")

        batch_lines.append(line)
        batch_indices.append(idx)

    if batch_indices:
        translated = translate_batch_text(batch_lines, translator)
        for t, pos in zip(translated, batch_indices):
            translated_lines[pos] = t + ("\n" if lines[pos].endswith("\n") else "")
        translated_so_far += len(translated)
        if total_english:
            pct = int((translated_so_far / total_english) * 100)
            logger.debug(f"Translation progress: {pct}% ({translated_so_far}/{total_english})")

    output_srt.write_text("".join(translated_lines), encoding="utf-8")


def extract_embedded_spanish_subtitles(video_path: Path, output_srt: Path) -> bool:
    """Try to extract Spanish subtitles embedded in video."""
    config = get_config()
    logger.info("Attempting to extract Spanish subtitles from video...")

    if not has_embedded_subtitles(video_path):
        logger.debug("No embedded subtitles found")
        return False

    subtitle_streams = get_subtitle_streams(video_path)
    if not subtitle_streams:
        logger.warning("Could not detect subtitle streams")
        return False

    # Look for Spanish subtitles
    spanish_streams = [s for s in subtitle_streams
                      if str(s['language']).lower() in config.spanish_codes]

    if spanish_streams:
        best_stream = spanish_streams[0]
        logger.info(f"Found Spanish subtitle stream (index {best_stream['subtitle_index']})")
        if extract_subtitles_util(video_path, output_srt, best_stream['subtitle_index']):
            logger.info(f"Spanish subtitles extracted: {output_srt.name}")
            return True

    logger.debug("No Spanish subtitles found in video")
    return False


def extract_and_translate_embedded_english_subtitles(video_path: Path, output_srt: Path) -> bool:
    """Try to extract English subtitles from video and translate them.

    Selects the English subtitle stream with the most content to avoid
    extracting soundtrack-only subtitles (e.g., song lyrics).
    """
    logger.info("Attempting to extract English subtitles from video...")

    if not has_embedded_subtitles(video_path):
        logger.debug("No embedded subtitles found")
        return False

    subtitle_streams = get_subtitle_streams(video_path)
    if not subtitle_streams:
        logger.warning("Could not detect subtitle streams")
        return False

    # Look for English subtitles
    config = get_config()
    english_streams = [s for s in subtitle_streams
                      if str(s['language']).lower() in config.english_codes]

    if not english_streams:
        logger.debug("No English subtitles found in video")
        return False

    # Find the English subtitle with the most content (to avoid song-only subtitles)
    best_stream = None
    best_char_count = 0

    for stream in english_streams:
        # Extract temporarily to count characters
        temp_srt = video_path.parent / f"{video_path.stem}.temp_size_check_{stream['subtitle_index']}.srt"
        try:
            if extract_subtitles_util(video_path, temp_srt, stream['subtitle_index']):
                # Count characters in the extracted subtitle
                content = temp_srt.read_text(encoding="utf-8", errors="ignore")
                char_count = len(content)
                logger.debug(f"Stream {stream['subtitle_index']}: {char_count} characters")

                if char_count > best_char_count:
                    best_char_count = char_count
                    best_stream = stream

                # Clean up temp file
                temp_srt.unlink()
        except Exception as e:
            logger.debug(f"Error checking stream {stream['subtitle_index']}: {e}")
            if temp_srt.exists():
                temp_srt.unlink()

    if not best_stream:
        logger.debug("Could not extract any English subtitle")
        return False

    logger.info(f"Found English subtitle stream (index {best_stream['subtitle_index']}, {best_char_count} chars)")

    # Extract the best stream to temporary file
    temp_srt = video_path.parent / f"{video_path.stem}.temp_extracted.srt"
    if extract_subtitles_util(video_path, temp_srt, best_stream['subtitle_index']):
        logger.info("English subtitles extracted")
        logger.info("Translating to Spanish...")
        try:
            translate_srt(temp_srt, output_srt)
            logger.info(f"Saved as: {output_srt.name}")
            temp_srt.unlink()
            return True
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            if temp_srt.exists():
                temp_srt.unlink()
            return False

    return False


def find_and_translate_local_srt(video_path: Path, output_srt: Path) -> bool:
    """Search for .srt file with same name in folder. Translate if in English."""
    logger.info("Searching for local .srt file...")

    # Look for .srt with the same base name
    possible_srt = video_path.parent / f"{video_path.stem}.srt"

    if not possible_srt.exists():
        logger.debug(f"Not found: {possible_srt.name}")
        return False

    logger.info(f"Found: {possible_srt.name}")

    # Check if it's in English
    text = possible_srt.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines(True)
    eng_indices = [i for i, line in enumerate(lines) if is_english_line(line)]

    if not eng_indices:
        logger.info("File is in Spanish, copying...")
        output_srt.write_text(text, encoding="utf-8")
        return True

    logger.info(f"Detected English content in {len(eng_indices)} lines")
    logger.info("Translating to Spanish...")
    try:
        translate_srt(possible_srt, output_srt)
        logger.info(f"Saved as: {output_srt.name}")
        return True
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return False


def main() -> None:
    """Main entry point for subtitle generation."""
    parser = argparse.ArgumentParser(
        description="Generate Spanish subtitles for a video file",
        epilog="Supports: download, extraction, and translation"
    )
    parser.add_argument("path", help="Path to the video file")
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

    # Validate and normalize the video file path
    path_str = args.path.strip() if isinstance(args.path, str) else str(args.path)
    video_path = validate_video_path(path_str)

    # Supported video extensions from config
    if video_path.suffix.lower() not in config.video_formats:
        logger.error(f"Unsupported format: {video_path.suffix}")
        sys.exit(1)

    output_srt = video_path.parent / f"{video_path.stem}.srt"

    logger.info(f"Generating subtitles for: {video_path.name}")

    # Case 1: Try to download Spanish subtitles
    logger.info("Attempting to download Spanish subtitles...")
    spanish_srt = download_subtitle(video_path, "es")

    if spanish_srt:
        logger.info(f"Spanish subtitles downloaded: {spanish_srt.name}")
        if spanish_srt != output_srt:
            spanish_srt.rename(output_srt)
            logger.info(f"Renamed to: {output_srt.name}")
        logger.info("✅ Subtitles generated successfully")
        sys.exit(0)

    logger.warning("Spanish subtitles not found")

    # Case 2: Try to download English subtitles
    logger.info("Attempting to download English subtitles...")
    english_srt = download_subtitle(video_path, "en")

    if english_srt:
        logger.info(f"English subtitles downloaded: {english_srt.name}")
        logger.info("Translating to Spanish...")
        try:
            translate_srt(english_srt, output_srt)
            logger.info(f"Saved as: {output_srt.name}")
            try:
                english_srt.unlink()
                logger.debug("Cleaned up English subtitle")
            except Exception:
                pass
            logger.info("✅ Subtitles generated and translated")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            sys.exit(1)

    logger.warning("English subtitles not found")

    # Case 3: Try to extract Spanish subtitles embedded in video
    if extract_embedded_spanish_subtitles(video_path, output_srt):
        logger.info("✅ Subtitles extracted successfully")
        sys.exit(0)

    # Case 4: Try to extract English subtitles embedded in video and translate
    if extract_and_translate_embedded_english_subtitles(video_path, output_srt):
        logger.info("✅ Subtitles extracted and translated")
        sys.exit(0)

    # Case 5: Try to find and translate local .srt file
    if find_and_translate_local_srt(video_path, output_srt):
        logger.info("✅ Subtitles processed successfully")
        sys.exit(0)

    logger.error("Could not find or generate subtitles")
    sys.exit(1)


if __name__ == '__main__':
    main()
