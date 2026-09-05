import hashlib
import re
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, ConfigDict


VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


class InvalidYouTubeUrl(ValueError):
    pass


class NormalizedYouTubeUrl(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_url: str
    canonical_url: str
    url_hash: str
    video_id: str


def normalize_youtube_url(value: str) -> NormalizedYouTubeUrl:
    source_url = value.strip()
    if VIDEO_ID_PATTERN.fullmatch(source_url):
        video_id = source_url
    else:
        parsed = urlparse(source_url)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        video_id = _video_id_from_url(host, parsed.path, parsed.query)

    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    return NormalizedYouTubeUrl(
        source_url=source_url,
        canonical_url=canonical_url,
        url_hash=hashlib.sha256(canonical_url.encode("utf-8")).hexdigest(),
        video_id=video_id,
    )


def _video_id_from_url(host: str, path: str, query: str) -> str:
    candidate = ""
    if host in {"youtu.be", "m.youtu.be"}:
        candidate = path.strip("/").split("/", 1)[0]
    elif host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        if path.rstrip("/") == "/watch":
            candidate = parse_qs(query).get("v", [""])[0]
        else:
            parts = [part for part in path.split("/") if part]
            if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
                candidate = parts[1]
    else:
        raise InvalidYouTubeUrl("Only YouTube URLs and video IDs are supported.")

    if not VIDEO_ID_PATTERN.fullmatch(candidate):
        raise InvalidYouTubeUrl("Could not find a valid YouTube video ID.")
    return candidate
