"""SubX provider: Spanish subtitles from Subdivx through the SubX API.

subdivx.com itself sits behind a bot challenge; SubX
(https://subx-api.duckdns.org/docs/) indexes it and serves search and
downloads to API-key holders. Needs ``apikey`` in provider_configs.
"""

from __future__ import annotations

import io
import logging
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from typing import ClassVar

from babelfish import Language
from guessit import guessit
from requests import Session

from subliminal.exceptions import (
    AuthenticationError,
    ConfigurationError,
    DownloadLimitExceeded,
    NotInitializedProviderError,
)
from subliminal.matches import guess_matches
from subliminal.providers import Provider
from subliminal.subtitle import Subtitle
from subliminal.utils import sanitize
from subliminal.video import Episode, Movie, Video

logger = logging.getLogger(__name__)

_EPISODE_TAG = re.compile(r"\s*\bS\d{1,2}E\d{1,3}\b.*$", re.IGNORECASE)
_YEAR_TAG = re.compile(r"\s*\(\d{4}\)\s*$")
_SUBTITLE_EXT = (".srt", ".ssa", ".ass", ".sub")


def _clean_title(title: str) -> str:
    """'Avatar: The Legend of Korra S02E10' -> 'Avatar: The Legend of Korra'."""
    return _YEAR_TAG.sub("", _EPISODE_TAG.sub("", title or "")).strip()


def _titles_match(found: str, wanted: list[str]) -> bool:
    """Exact match after sanitizing, or the found title ends with the wanted
    one ('Avatar: The Legend of Korra' for 'The Legend of Korra'). SubX's
    title search is fuzzy, so anything looser lets other shows through."""
    found = sanitize(found)
    for title in wanted:
        title = sanitize(title)
        if title and (found == title or found.endswith(" " + title)):
            return True
    return False


class SubxSubtitle(Subtitle):
    provider_name: ClassVar[str] = "subx"

    def __init__(self, language: Language, subtitle_id: str, *, title: str = "",
                 season: int | None = None, episode: int | None = None,
                 year: int | None = None, description: str = "", downloads: int = 0) -> None:
        super().__init__(language, subtitle_id,
                         page_link=f"https://subx-api.duckdns.org/api/subtitles/{subtitle_id}")
        self.title = title
        self.season = season
        self.episode = episode
        self.year = year
        self.description = description
        self.downloads = downloads

    @property
    def info(self) -> str:
        return self.description.splitlines()[0] if self.description else self.title

    def get_matches(self, video: Video) -> set[str]:
        matches: set[str] = set()
        name = _clean_title(self.title)
        if isinstance(video, Episode):
            if _titles_match(name, [video.series, *video.alternative_series]):
                matches.add("series")
            if video.season is not None and self.season == video.season:
                matches.add("season")
            if video.episodes and self.episode in video.episodes:
                matches.add("episode")
            if video.year and self.year == video.year:
                matches.add("year")
        elif isinstance(video, Movie):
            if _titles_match(name, [video.title, *video.alternative_titles]):
                matches.add("title")
            if video.year and self.year == video.year:
                matches.add("year")
        # Release info lives in free text ("De aRGENTeaM para The.Show.S02E10.720p.HDTV.x264-QCF")
        for token in re.findall(r"[\w.\-\[\]]+\.\w+(?:-\w+)?", self.description):
            matches |= guess_matches(video, guessit(token), partial=True) & {
                "release_group", "source", "resolution", "video_codec", "audio_codec", "streaming_service"}
        return matches


class SubxProvider(Provider):
    languages: ClassVar = {Language("spa")}
    video_types: ClassVar = (Episode, Movie)
    server_url: ClassVar[str] = "https://subx-api.duckdns.org/api"
    subtitle_class: ClassVar = SubxSubtitle

    def __init__(self, apikey: str | None = None, *, apiKey: str | None = None,  # noqa: N803
                 timeout: int = 20) -> None:
        key = (apikey or apiKey or "").strip()
        if not key:
            raise ConfigurationError("SubX needs an apikey in download.provider_configs.subx")
        self.apikey = key
        self.timeout = timeout
        self.session: Session | None = None

    def initialize(self) -> None:
        self.session = Session()
        self.session.headers["Authorization"] = f"Bearer {self.apikey}"
        self.session.headers["User-Agent"] = "OpenSubTools"
        self.session.headers["Accept"] = "application/json"

    def terminate(self) -> None:
        if self.session is not None:
            self.session.close()

    def _get(self, path: str, **params):
        if self.session is None:
            raise NotInitializedProviderError
        response = self.session.get(f"{self.server_url}{path}", params=params or None, timeout=self.timeout)
        if response.status_code in (401, 403):
            raise AuthenticationError("SubX rejected the API key")
        if response.status_code == 429:
            raise DownloadLimitExceeded(f"SubX rate limit; retry after {response.headers.get('Retry-After')}s")
        response.raise_for_status()
        return response

    def query(self, video: Video) -> list[SubxSubtitle]:
        if isinstance(video, Episode):
            titles = [video.series, *video.alternative_series]
            base = {"video_type": "episode", "season": video.season, "episode": video.episode}
        else:
            titles = [video.title, *video.alternative_titles]
            base = {"video_type": "movie"}
            if video.year:
                base["year"] = video.year

        items: dict[str, dict] = {}
        for title in titles:
            data = self._get("/subtitles/search", title=title, limit=100, **base).json()
            for item in data.get("items", []):
                items.setdefault(item["id"], item)
            if items:
                break

        subtitles = []
        for item in items.values():
            def as_int(value):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None
            subtitles.append(SubxSubtitle(
                Language("spa"), item["id"],
                title=item.get("title") or "",
                season=as_int(item.get("season")),
                episode=as_int(item.get("episode")),
                year=as_int(item.get("year")),
                description=item.get("description") or "",
                downloads=as_int(item.get("downloads")) or 0,
            ))
        # Most-downloaded first: subliminal keeps the first of equal scores.
        subtitles.sort(key=lambda s: s.downloads, reverse=True)
        logger.debug("SubX: %d subtitles for %s", len(subtitles), video.name)
        return subtitles

    def list_subtitles(self, video: Video, languages) -> list[SubxSubtitle]:
        if Language("spa") not in languages:
            return []
        return self.query(video)

    def download_subtitle(self, subtitle: SubxSubtitle) -> None:
        response = self._get(f"/subtitles/{subtitle.id}/download")
        subtitle.content = _extract(response.content, getattr(subtitle, "episode", None))


_SEVEN_ZIP = [shutil.which("7z"), r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe"]
_WIN_TAR = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "tar.exe")


def _open_rar(payload: bytes):
    """Most Subdivx files are RAR, which Python can't unpack alone.

    7-Zip is used through rarfile when installed; otherwise the bsdtar that
    ships with Windows 10+ (System32\\tar.exe), which reads RAR from a file.
    """
    import rarfile

    seven_zip = next((p for p in _SEVEN_ZIP if p and os.path.exists(p)), None)
    if seven_zip:
        rarfile.SEVENZIP_TOOL = seven_zip
        archive = rarfile.RarFile(io.BytesIO(payload))
        return archive.namelist(), archive.read

    if not os.path.exists(_WIN_TAR):
        raise RuntimeError("needs 7-Zip or Windows' tar.exe to read .rar files")
    fd, path = tempfile.mkstemp(suffix=".rar")
    try:
        os.write(fd, payload)
        os.close(fd)
        listing = subprocess.run([_WIN_TAR, "-tf", path], capture_output=True, check=True,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        names = [n for n in listing.stdout.decode("utf-8", "replace").splitlines() if n]
        contents = {}
        for name in names:
            if name.lower().endswith(_SUBTITLE_EXT):
                contents[name] = subprocess.run(
                    [_WIN_TAR, "-xOf", path, name], capture_output=True, check=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    finally:
        os.unlink(path)
    return names, lambda name: contents.get(name, b"")


def _extract(payload: bytes, episode: int | None) -> bytes | None:
    """Return the subtitle file from a plain, .zip or .rar payload."""
    archive = None
    if payload[:4] == b"PK\x03\x04":
        archive = zipfile.ZipFile(io.BytesIO(payload))
        names = archive.namelist()
        read = archive.read
    elif payload[:4] == b"Rar!":
        try:
            names, read = _open_rar(payload)
        except Exception as e:  # no extractor available, corrupt archive
            logger.warning("SubX: cannot open .rar subtitle: %s", e)
            return None
    else:
        return payload

    candidates = [n for n in names if n.lower().endswith(_SUBTITLE_EXT)]
    if not candidates:
        return None
    # Season packs: prefer the file tagged with this episode
    if episode is not None and len(candidates) > 1:
        tagged = [n for n in candidates if re.search(rf"[Ee]0*{episode}\b|x0*{episode}\b", n)]
        candidates = tagged or candidates
    srt_first = sorted(candidates, key=lambda n: (not n.lower().endswith(".srt"), -len(read(n))))
    return read(srt_first[0])
