#!/usr/bin/env python3
"""Google Translate transport.

deep_translator's GoogleTranslator scrapes https://translate.google.com/m,
which now answers 429 to every request, so each call raised TooManyRequests
and callers silently kept the untranslated English text. The public
translate_a/single endpoint still works, so requests go there instead, over
POST so a batch is not limited by URL length.

That endpoint meters by IP and a block outlasts any sensible wait, so a 429
is not retried: it raises RateLimitError at once and the caller moves on to
the offline model. Requests still pass through a process-wide pacer to keep
a run under the quota for as long as possible.
"""

import random
import threading
import time
from typing import Optional

import requests

from subtitles.utils.logging_config import get_logger

logger = get_logger()

_ENDPOINT = "https://translate.googleapis.com/translate_a/single"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Minimum gap between any two requests, across every thread. Measured 2026-09:
# roughly 80 requests over 18 episodes was enough to trip the quota, and the
# block that followed outlasted 30 minutes, so pace well under that.
_MIN_INTERVAL = 3.0


class TranslationError(Exception):
    """Raised when a text could not be translated after every retry."""


class RateLimitError(TranslationError):
    """Raised when Google is actively throttling this IP.

    Kept distinct so callers can stop sending requests wholesale instead of
    retrying individual lines, which only deepens an already blocked quota.
    """


class _Throttle:
    """Process-wide request pacing shared by every worker thread."""

    def __init__(self, min_interval: float):
        self._lock = threading.Lock()
        self._min_interval = min_interval
        self._next_allowed = 0.0

    def wait(self) -> None:
        """Block until this thread is allowed to issue a request."""
        with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next_allowed - now)
            self._next_allowed = now + delay + self._min_interval
        if delay:
            time.sleep(delay)


_throttle = _Throttle(_MIN_INTERVAL)

_session_lock = threading.Lock()
_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """Return the shared session, keeping connections alive between chunks."""
    global _session
    with _session_lock:
        if _session is None:
            _session = requests.Session()
            _session.headers.update({"User-Agent": _USER_AGENT})
        return _session


def translate(text: str, target_lang: str, source_lang: str = "en",
              max_retries: int = 1, timeout: int = 30) -> str:
    """Translate a single payload, raising TranslationError if it never lands.

    Args:
        text: Payload to translate; may contain newlines and separators.
        target_lang: Target language code, e.g. 'es'.
        source_lang: Source language code, or 'auto'.
        max_retries: Attempts before giving up. One by default: the first
            failure hands the run to the offline model.
        timeout: Per-request timeout in seconds.

    Returns:
        The translated payload.

    Raises:
        RateLimitError: Google answered 429. Raised on the first hit, never
            retried.
        TranslationError: Any other failure that outlived the retries.
    """
    if not text or not text.strip():
        return text

    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        _throttle.wait()
        try:
            response = _get_session().post(
                _ENDPOINT,
                params={
                    "client": "gtx",
                    "sl": source_lang,
                    "tl": target_lang,
                    "dt": "t",
                },
                data={"q": text},
                timeout=timeout,
            )

            if response.status_code == 429:
                raise RateLimitError("rate limited (429)")

            response.raise_for_status()

            payload = response.json()
            if not payload or not payload[0]:
                raise TranslationError("empty response")

            result = "".join(part[0] for part in payload[0] if part and part[0])
            return result

        except RateLimitError:
            raise
        except Exception as error:
            last_error = error
            if attempt < max_retries - 1:
                # Jittered backoff so parallel workers do not retry in lockstep.
                time.sleep((2 ** attempt) + random.uniform(0, 0.5))

    raise TranslationError(f"translation failed after {max_retries} attempts: {last_error}")
