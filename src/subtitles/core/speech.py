#!/usr/bin/env python3
"""Speech recognition for subtitle timing.

Energy-based speech detection cannot tell dialogue from a score that plays
under every scene, so for same-language subtitles the audio is transcribed
with Whisper (faster-whisper) and each cue is timed by matching its words
to the spoken ones. When a subtitle's words mostly don't occur in the audio
(a translation of another script, e.g. the Japanese original under an
English dub), the transcript itself becomes the subtitle.

Everything Whisper downloads or caches lives under .work/ in the repo, not
in the user profile.
"""

import glob
import os
import re
import subprocess
import sys
import threading
from datetime import timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import srt

from subtitles.utils.logging_config import get_logger

logger = get_logger()

_WORK_DIR = Path(__file__).resolve().parents[3] / ".work"
_MODEL_DIR = Path(os.environ.get("SUBTITLES_WHISPER_DIR", _WORK_DIR / "whisper"))
_MODEL_NAME = os.environ.get("SUBTITLES_WHISPER_MODEL", "base.en")
os.environ.setdefault("HF_HOME", str(_WORK_DIR / "hf"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

SAMPLE_RATE = 16000
# Below this share of cues found in the audio, the subtitle is a different
# script rather than a timing problem.
MIN_MATCH_RATIO = 0.5

Word = Tuple[float, float, str]

_lock = threading.Lock()      # one transcription at a time: the GPU is shared
_model = None
_unavailable = False
_cache: Dict[str, List[Word]] = {}


def _add_cuda_dlls() -> None:
    """pip's nvidia-* wheels keep their DLLs in site-packages/nvidia/*/bin."""
    if sys.platform != "win32":
        return
    for site in sys.path:
        for bin_dir in glob.glob(os.path.join(site, "nvidia", "*", "bin")):
            try:
                os.add_dll_directory(bin_dir)
            except OSError:
                pass
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")


def _load():
    global _model, _unavailable
    if _model is not None or _unavailable:
        return _model
    try:
        _add_cuda_dlls()
        from faster_whisper import BatchedInferencePipeline, WhisperModel
    except ImportError:
        _unavailable = True
        return None

    for device, compute in (("cuda", "int8_float16"), ("cpu", "int8")):
        try:
            model = WhisperModel(_MODEL_NAME, device=device, compute_type=compute,
                                 download_root=str(_MODEL_DIR))
            _model = (BatchedInferencePipeline(model=model), device)
            logger.info(f"Whisper {_MODEL_NAME} loaded on {device}")
            return _model
        except Exception as e:
            logger.debug(f"Whisper on {device} unavailable: {e}")
    _unavailable = True
    logger.warning("Whisper could not be loaded; falling back to energy-based sync")
    return None


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def audio_language(video_path: Path) -> str:
    """ISO 639-1 code of the first audio track, from its tag ('' if untagged)."""
    tag = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream_tags=language", "-of", "csv=p=0", str(video_path)],
        capture_output=True, text=True
    ).stdout.strip().lower()
    return {"eng": "en", "en": "en", "spa": "es", "es": "es"}.get(tag, tag[:2] if tag not in ("und", "") else "")


def can_transcribe(video_path: Path) -> bool:
    """The bundled model is English-only; untagged audio is assumed English."""
    return available() and audio_language(video_path) in ("en", "")


def transcribe(video_path: Path) -> Optional[List[Word]]:
    """Word-level transcript of the first audio track, cached per video."""
    key = str(video_path)
    if key in _cache:
        return _cache[key]
    with _lock:
        if key in _cache:
            return _cache[key]
        loaded = _load()
        if loaded is None:
            return None
        pipeline, device = loaded
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(video_path), "-map", "0:a:0",
             "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-"],
            capture_output=True, check=True
        ).stdout
        audio = np.frombuffer(raw, np.float32)
        logger.info(f"Transcribing {video_path.name} ({len(audio) / SAMPLE_RATE / 60:.0f} min, {device})")
        segments, _ = pipeline.transcribe(audio, language="en", word_timestamps=True,
                                          batch_size=8, beam_size=1)
        words = [(w.start, w.end, w.word.strip()) for s in segments for w in (s.words or [])]
        _cache[key] = words
        return words


def on_gpu() -> bool:
    loaded = _load()
    return bool(loaded) and loaded[1] == "cuda"


def speech_activity(video_path: Path, frame_ms: int = 10, pad_frames: int = 0) -> Optional[np.ndarray]:
    """1 where the transcript has a word being spoken, 0 elsewhere.

    A cleaner sync target than loudness for subtitles in any language: music
    and effects never become "speech", only recognised words do.
    """
    words = transcribe(video_path)
    if not words:
        return None
    per_second = 1000 // frame_ms
    frames = int(max(end for _, end, _ in words) * per_second) + pad_frames
    activity = np.zeros(frames, np.float32)
    for start, end, _ in words:
        activity[int(start * per_second):int(end * per_second) + 1] = 1
    return activity


def _norm(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", word.lower())


_MARKUP_RE = re.compile(r"<[^>]+>|\{[^}]*\}|\[[^\]]*\]|\([^)]*\)|♪")


def align(subtitles: List[srt.Subtitle], words: List[Word]) -> Tuple[List[Optional[float]], float]:
    """Offset in seconds for each cue found in the transcript (None if not).

    Matching runs of two or more words anchor a cue; a word's offset is its
    spoken start minus where it would fall inside the cue. Returns the
    offsets and the share of cues anchored.
    """
    spoken = [(start, _norm(w)) for start, _, w in words if _norm(w)]
    tokens = []
    for index, cue in enumerate(subtitles):
        cue_words = [_norm(w) for w in _MARKUP_RE.sub(" ", cue.content).split()]
        cue_words = [w for w in cue_words if w]
        for k, w in enumerate(cue_words):
            tokens.append((index, k / len(cue_words), w))

    matcher = SequenceMatcher(None, [t[2] for t in tokens], [s[1] for s in spoken], autojunk=False)
    found: Dict[int, List[float]] = {}
    for block in matcher.get_matching_blocks():
        if block.size < 2:
            continue
        for d in range(block.size):
            index, position, _ = tokens[block.a + d]
            cue = subtitles[index]
            expected = cue.start.total_seconds() + position * (cue.end - cue.start).total_seconds()
            found.setdefault(index, []).append(spoken[block.b + d][0] - expected)

    offsets: List[Optional[float]] = [None] * len(subtitles)
    for index, values in found.items():
        offsets[index] = float(np.median(values))

    # A cue whose offset disagrees with both anchored neighbours by seconds
    # matched a repeated phrase in the wrong place.
    anchored = [i for i, o in enumerate(offsets) if o is not None]
    raw = list(offsets)
    for pos, i in enumerate(anchored):
        neighbours = [raw[j] for j in anchored[max(0, pos - 3):pos] + anchored[pos + 1:pos + 4]]
        if len(neighbours) >= 3 and abs(raw[i] - float(np.median(neighbours))) > 2.0:
            offsets[i] = None

    ratio = sum(o is not None for o in offsets) / max(len(subtitles), 1)
    return offsets, ratio


def apply_alignment(subtitles: List[srt.Subtitle], offsets: List[Optional[float]]) -> List[srt.Subtitle]:
    """Shift anchored cues by their own offset and the rest by their anchors'.

    A cue between two anchors that agree takes their offset. Between anchors
    that disagree, the video cut or added material there; such a cue takes
    the nearer anchor's offset and is dropped if that lands it on top of an
    anchored cue (it was in the cut part).
    """
    anchored = [i for i, o in enumerate(offsets) if o is not None]
    if not anchored:
        return subtitles

    result = []
    for i, cue in enumerate(subtitles):
        offset = offsets[i]
        guessed = offset is None
        if guessed:
            before = max((j for j in anchored if j < i), default=None)
            after = min((j for j in anchored if j > i), default=None)
            if before is None:
                offset = offsets[after]
            elif after is None:
                offset = offsets[before]
            elif abs(offsets[before] - offsets[after]) <= 1.0:
                offset = (offsets[before] + offsets[after]) / 2
            else:
                gap_before = (cue.start - subtitles[before].end).total_seconds()
                gap_after = (subtitles[after].start - cue.end).total_seconds()
                offset = offsets[before] if gap_before <= gap_after else offsets[after]
        shift = timedelta(seconds=offset)
        result.append((guessed, srt.Subtitle(cue.index, cue.start + shift, cue.end + shift, cue.content)))

    kept = []
    for pos, (guessed, cue) in enumerate(result):
        if cue.start < timedelta(0):
            continue
        if guessed:
            overlaps = any(
                not other_guessed and other.start < cue.end and cue.start < other.end
                for other_guessed, other in result[max(0, pos - 3):pos + 4]
                if other is not cue
            )
            if overlaps:
                continue
        kept.append(cue)
    return kept


def transcript_to_subtitles(words: List[Word], max_chars: int = 84,
                            max_seconds: float = 6.0, pause: float = 0.7) -> List[srt.Subtitle]:
    """Group transcript words into readable cues.

    A cue ends at sentence punctuation once it has some length, at a pause in
    speech, or when it would exceed two lines or six seconds.
    """
    cues: List[srt.Subtitle] = []
    current: List[Word] = []

    def flush():
        if current:
            text = " ".join(w for _, _, w in current)
            cues.append(srt.Subtitle(len(cues) + 1, timedelta(seconds=current[0][0]),
                                     timedelta(seconds=max(current[-1][1], current[0][0] + 0.8)),
                                     _two_lines(text)))
            current.clear()

    for word in words:
        if current:
            text_len = sum(len(w) + 1 for _, _, w in current) + len(word[2])
            if (word[0] - current[-1][1] > pause or text_len > max_chars
                    or word[1] - current[0][0] > max_seconds):
                flush()
        current.append(word)
        if word[2].endswith((".", "?", "!")) and sum(len(w) + 1 for _, _, w in current) > 25:
            flush()
    flush()

    for current_cue, following in zip(cues, cues[1:]):
        if current_cue.end > following.start:
            current_cue.end = following.start
    return cues


def _two_lines(text: str, width: int = 42) -> str:
    if len(text) <= width:
        return text
    middle = len(text) // 2
    spaces = [i for i, c in enumerate(text) if c == " "]
    split = min(spaces, key=lambda i: abs(i - middle)) if spaces else len(text)
    return text[:split] + "\n" + text[split + 1:]
