#!/usr/bin/env python3
"""Core subtitle translation logic."""

import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

import srt

from subtitles.core.cleaner import clean_and_merge_subtitles
from subtitles.core import offline
from subtitles.core.gtranslate import (
    TranslationError,
    translate as translate_payload,
)
from subtitles.utils.logging_config import get_logger

logger = get_logger()

# Marker used to translate many cues in one request. Google rewrote the old
# "|||<||>|" separator (adding spaces, dropping pipes), so chunks came back
# with a different number of parts and every later cue inherited another
# cue's text. "@@@" survives intact, and the split tolerates whitespace the
# translator may still add around it.
_SEPARATOR = "\n@@@\n"
_SEPARATOR_RE = re.compile(r'\s*@@@\s*')

# Google meters by request count, not by size, and accepts payloads far
# larger than this, so packing cues into few large requests is what keeps a
# 170-episode run under the quota.
_MAX_CHUNK_CHARS = 9000
_MAX_WORKERS = 2

# Names and interjections legitimately survive translation, but a file that
# is mostly untranslated means the service rejected the work.
_MAX_UNTRANSLATED_RATIO = 0.5

# The bundled offline model only goes English -> Spanish.
_OFFLINE_LANG = "es"
_OFFLINE_BATCH = 200

# Once Google fails, every later file in this process goes straight to the
# offline model instead of probing a quota that is already spent.
_google_failed = False
_google_lock = threading.Lock()


def _google_is_down() -> bool:
    with _google_lock:
        return _google_failed


def _mark_google_down() -> None:
    global _google_failed
    with _google_lock:
        _google_failed = True


def find_local_srt(video_path: Path) -> Optional[Path]:
    """Search for a .srt file with the same base name as video."""
    possible_srt = video_path.parent / f"{video_path.stem}.srt"
    return possible_srt if possible_srt.exists() else None


def _build_chunks(texts: List[str], max_chars: int) -> List[List[str]]:
    """Group texts into chunks small enough for a single translation request."""
    chunks: List[List[str]] = []
    current: List[str] = []
    current_len = 0

    for text in texts:
        cost = len(text) + len(_SEPARATOR)
        if current and current_len + cost > max_chars:
            chunks.append(current)
            current = []
            current_len = 0
        current.append(text)
        current_len += cost

    if current:
        chunks.append(current)

    return chunks


def _split_and_retry(texts: List[str], target_lang: str) -> List[str]:
    """Halve a failed chunk and translate each side separately.

    Retrying a bad chunk line by line turned one failure into as many
    requests as it had cues, which is how a brief throttle escalated into a
    hard block. Halving costs a couple of extra requests instead.
    """
    middle = len(texts) // 2
    return (
        _translate_chunk(texts[:middle], target_lang)
        + _translate_chunk(texts[middle:], target_lang)
    )


def _translate_chunk(texts: List[str], target_lang: str) -> List[str]:
    """Translate one chunk, always returning a list aligned with its input.

    A mismatch between the number of parts sent and received means the
    separator was mangled, so the chunk is halved and retried rather than
    letting the misalignment shift every following cue.

    Raises:
        TranslationError: Propagated untouched on the first Google failure so
            the caller can switch to the offline model; splitting would only
            add requests while the service is refusing them.
    """
    if not texts:
        return []

    if len(texts) == 1:
        return [translate_payload(texts[0], target_lang)]

    translated = translate_payload(_SEPARATOR.join(texts), target_lang)

    parts = [part.strip() for part in _SEPARATOR_RE.split(translated)]

    if len(parts) != len(texts):
        logger.warning(
            f"Separator lost: sent {len(texts)} lines, got {len(parts)}; "
            "splitting chunk in half"
        )
        return _split_and_retry(texts, target_lang)

    return [part or original for part, original in zip(parts, texts)]


def _translate_google(texts: List[str], target_lang: str, progress_callback=None) -> List[str]:
    """Translate a list of texts through Google, preserving input order.

    Raises:
        TranslationError: On the first failed request; queued chunks are
            dropped.
    """
    chunks = _build_chunks(texts, _MAX_CHUNK_CHARS)
    if not chunks:
        return []

    logger.info(f"Translating {len(chunks)} chunks...")

    results: List[Optional[List[str]]] = [None] * len(chunks)
    done = 0
    failure: Optional[TranslationError] = None

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {
            executor.submit(_translate_chunk, chunk, target_lang): index
            for index, chunk in enumerate(chunks)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                results[index] = future.result()
            except TranslationError as error:
                # Drop the queued chunks; the caller redoes the file offline.
                failure = failure or error
                for pending in futures:
                    pending.cancel()
            except Exception as error:
                logger.error(f"Chunk {index} failed: {error}")
                results[index] = list(chunks[index])
            done += 1
            if progress_callback:
                try:
                    progress_callback(done / len(chunks))
                except Exception:
                    pass

    if failure:
        raise failure

    ordered: List[str] = []
    for index, chunk in enumerate(chunks):
        ordered.extend(results[index] or chunk)
    return ordered


def _translate_offline(texts: List[str], progress_callback=None) -> List[str]:
    """Translate with the bundled model, reporting progress per batch."""
    out: List[str] = []
    for start in range(0, len(texts), _OFFLINE_BATCH):
        out.extend(offline.translate_texts(texts[start:start + _OFFLINE_BATCH]))
        if progress_callback:
            try:
                progress_callback(len(out) / len(texts))
            except Exception:
                pass
    return out


def _translate_texts(texts: List[str], target_lang: str, progress_callback=None) -> List[str]:
    """Translate with Google, restarting on the offline model at its first failure.

    Raises:
        TranslationError: Google failed and the offline model cannot cover
            this language.
        offline.OfflineModelMissing: Google failed and the model is absent.
    """
    offline_possible = target_lang == _OFFLINE_LANG

    if offline_possible and _google_is_down():
        return _translate_offline(texts, progress_callback)

    try:
        return _translate_google(texts, target_lang, progress_callback)
    except TranslationError as error:
        if not offline_possible:
            raise
        _mark_google_down()
        logger.warning(f"Google failed ({error}); restarting with the offline model")
        if progress_callback:
            try:
                progress_callback(0.0)
            except Exception:
                pass
        return _translate_offline(texts, progress_callback)


def translate_srt_file(
    input_srt: Path,
    output_srt: Path,
    target_lang: str = 'es',
    use_enhanced: bool = True,
    use_parallel: bool = False,
    progress_callback=None,
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
        retry_untranslated: If True, retry subtitles that remain untranslated

    Returns:
        True if translation succeeded
    """
    logger.info(f"Translating {input_srt.name} to {target_lang}")

    try:
        content = input_srt.read_text(encoding='utf-8', errors='ignore')
        subtitles = list(srt.parse(content))
    except Exception as e:
        logger.error(f"Failed to parse SRT: {e}")
        return False

    if not subtitles:
        logger.error("No subtitles found")
        return False

    original_count = len(subtitles)
    subtitles = clean_and_merge_subtitles(subtitles)
    if not subtitles:
        logger.error("No subtitles left after cleanup")
        return False
    if len(subtitles) != original_count:
        logger.info(f"Cleaned markup and merged duplicates: {original_count} -> {len(subtitles)} entries")

    # Typeset tracks repeat the same text hundreds of times; translate each
    # distinct text once and map the result back to every entry.
    unique_texts = list(dict.fromkeys(sub.content for sub in subtitles))
    logger.info(f"Translating {len(subtitles)} subtitle entries ({len(unique_texts)} unique texts)")

    try:
        translated = _translate_texts(unique_texts, target_lang, progress_callback)
    except offline.OfflineModelMissing as e:
        logger.error(f"Google failed and the offline model is unavailable: {e}")
        return False
    except TranslationError:
        # Nothing is written, so the next run redoes this file from scratch.
        logger.error(f"Translation service failed on {input_srt.name}; nothing saved")
        raise

    translation_map = dict(zip(unique_texts, translated))

    untranslated_texts = [
        text for text in unique_texts
        if translation_map.get(text, text).strip().lower() == text.strip().lower()
    ]

    # The offline model is deterministic, so a second pass cannot improve it.
    if retry_untranslated and untranslated_texts and not _google_is_down():
        logger.info(f"Found {len(untranslated_texts)} untranslated texts, retrying...")
        try:
            retried = _translate_google(untranslated_texts, target_lang)
        except TranslationError:
            # The main pass already landed; keep it rather than discarding a
            # nearly complete file over the leftovers.
            logger.warning("Google failed during retry pass; keeping what was translated")
            _mark_google_down()
            retried = untranslated_texts
        for original, result in zip(untranslated_texts, retried):
            if result and result.strip().lower() != original.strip().lower():
                translation_map[original] = result

    final_untranslated = 0
    for sub in subtitles:
        result = translation_map.get(sub.content, sub.content)
        if result.strip().lower() == sub.content.strip().lower():
            final_untranslated += 1
        sub.content = result

    if final_untranslated:
        logger.warning(f"{final_untranslated}/{len(subtitles)} subtitles remain untranslated")
        # Writing a mostly-English file would poison later runs, which skip
        # any video that already has an .srt next to it.
        if final_untranslated / len(subtitles) > _MAX_UNTRANSLATED_RATIO:
            logger.error("Most subtitles were not translated; aborting")
            return False

    try:
        output_srt.write_text(srt.compose(subtitles), encoding='utf-8')
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
