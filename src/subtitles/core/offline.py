#!/usr/bin/env python3
"""Offline translation backend.

Google's free endpoint meters by IP and blocks for over half an hour once a
run exceeds its quota, which makes it unusable for a whole series. An Argos
model runs locally instead: no quota, no network, no rate limit.

Argos itself is not imported. Its sbd module pulls in stanza, and stanza
pulls in torch, so the published .argosmodel package is read directly: it is
a CTranslate2 model plus a SentencePiece tokenizer, both of which this reads
on their own.
"""

import os
import sys
import threading
from pathlib import Path
from typing import List, Optional

from subtitles.utils.logging_config import get_logger

logger = get_logger()

_ENV_VAR = "SUBTITLES_ARGOS_MODEL"

# The .exe unpacks the model next to its bundled data (see SubtitleTools.spec);
# from source it is read from the working copy.
if getattr(sys, "frozen", False):
    _DEFAULT_MODEL = Path(sys._MEIPASS) / "argos_model"
else:
    _DEFAULT_MODEL = Path(__file__).resolve().parents[3] / ".work" / "argos" / "en_es" / "en_es"

# Cues split across lines for display are usually one sentence, so they are
# translated as one. A leading dash means two speakers instead, and those
# lines have to stay apart.
_SPEAKER_PREFIXES = ("-", "–", "—")

_lock = threading.Lock()
_engine = None


class OfflineModelMissing(RuntimeError):
    """Raised when the Argos model directory cannot be found."""


def model_dir() -> Path:
    """Directory holding model/ and sentencepiece.model."""
    override = os.environ.get(_ENV_VAR)
    return Path(override) if override else _DEFAULT_MODEL


def _load():
    """Load the CTranslate2 model and tokenizer once per process."""
    global _engine
    with _lock:
        if _engine is not None:
            return _engine

        import ctranslate2
        import sentencepiece

        root = model_dir()
        ct_dir = root / "model"
        sp_file = root / "sentencepiece.model"

        if not (ct_dir / "model.bin").exists() or not sp_file.exists():
            raise OfflineModelMissing(
                f"Argos model not found under {root}. Set {_ENV_VAR} to its directory."
            )

        logger.info(f"Loading offline model from {root}")
        translator = ctranslate2.Translator(str(ct_dir), device="cpu")
        tokenizer = sentencepiece.SentencePieceProcessor(str(sp_file))
        _engine = (translator, tokenizer)
        return _engine


def _translate_segments(segments: List[str], beam_size: int, max_batch_size: int) -> List[str]:
    """Translate flat, single-line segments in one batch."""
    if not segments:
        return []

    translator, tokenizer = _load()
    encoded = [tokenizer.encode(s, out_type=str) for s in segments]
    results = translator.translate_batch(
        encoded,
        beam_size=beam_size,
        max_batch_size=max_batch_size,
        replace_unknowns=True,
    )
    return [tokenizer.decode(r.hypotheses[0]) for r in results]


def translate_texts(texts: List[str], beam_size: int = 2,
                    max_batch_size: int = 32) -> List[str]:
    """Translate cue texts, preserving speaker-split lines.

    Args:
        texts: Cue contents, each possibly spanning several lines.
        beam_size: CTranslate2 beam width; 2 is a good speed/quality point.
        max_batch_size: Segments per CTranslate2 batch.

    Returns:
        One translation per input, in the same order.
    """
    if not texts:
        return []

    # Flatten every cue into segments, remembering how to put them back.
    segments: List[str] = []
    spans: List[tuple] = []

    for text in texts:
        lines = [line for line in text.splitlines() if line.strip()]
        multi_speaker = len(lines) > 1 and any(
            line.lstrip().startswith(_SPEAKER_PREFIXES) for line in lines
        )
        if multi_speaker:
            start = len(segments)
            segments.extend(lines)
            spans.append((start, len(segments), True))
        else:
            start = len(segments)
            segments.append(" ".join(lines) if lines else text)
            spans.append((start, len(segments), False))

    translated = _translate_segments(segments, beam_size, max_batch_size)

    out: List[str] = []
    for (start, end, multi_speaker), original in zip(spans, texts):
        parts = translated[start:end]
        if not any(p.strip() for p in parts):
            out.append(original)
        elif multi_speaker:
            out.append("\n".join(parts))
        else:
            out.append(parts[0])
    return out
