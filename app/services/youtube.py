import asyncio
import html
import json
import re
from collections.abc import Sequence

import httpx
from defusedxml import ElementTree
from youtube_transcript_api import YouTubeTranscriptApi
from yt_dlp import YoutubeDL

from app.models.transcript import FetchedTranscript, TranscriptSegment
from app.services.url_normalizer import NormalizedYouTubeUrl


class TranscriptUnavailable(RuntimeError):
    pass


class YouTubeCaptionProvider:
    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self._timeout_seconds = timeout_seconds

    async def fetch(
        self,
        video: NormalizedYouTubeUrl,
        languages: Sequence[str],
    ) -> FetchedTranscript:
        title_task = asyncio.create_task(self._fetch_title(video))
        try:
            segments, language = await asyncio.to_thread(
                self._fetch_primary,
                video.video_id,
                languages,
            )
            title = await title_task
            return FetchedTranscript(
                title=title,
                language=language,
                provider="youtube-transcript-api",
                segments=segments,
            )
        except Exception as primary_error:
            title = await title_task
            try:
                return await self._fetch_fallback(video, languages, title)
            except Exception as fallback_error:
                raise TranscriptUnavailable(
                    f"Captions were unavailable ({primary_error}; {fallback_error})."
                ) from fallback_error

    def _fetch_primary(
        self,
        video_id: str,
        languages: Sequence[str],
    ) -> tuple[list[TranscriptSegment], str]:
        transcript = YouTubeTranscriptApi().fetch(video_id, languages=tuple(languages))
        segments = [
            TranscriptSegment(
                start=float(item.start),
                duration=float(item.duration),
                text=_normalize_text(item.text),
            )
            for item in transcript
            if _normalize_text(item.text)
        ]
        if not segments:
            raise TranscriptUnavailable("The caption track contained no text.")
        return segments, getattr(transcript, "language_code", "unknown")

    async def _fetch_title(self, video: NormalizedYouTubeUrl) -> str:
        try:
            async with httpx.AsyncClient(timeout=min(self._timeout_seconds, 4.0)) as client:
                response = await client.get(
                    "https://www.youtube.com/oembed",
                    params={"url": video.canonical_url, "format": "json"},
                )
                response.raise_for_status()
                title = str(response.json().get("title", "")).strip()
                return title or video.video_id
        except Exception:
            return video.video_id

    async def _fetch_fallback(
        self,
        video: NormalizedYouTubeUrl,
        languages: Sequence[str],
        title: str,
    ) -> FetchedTranscript:
        info = await asyncio.to_thread(_ytdlp_info, video.canonical_url)
        source, language = _select_subtitle_track(info, languages)
        extension, subtitle_url = _select_subtitle_url(info, source, language)
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.get(subtitle_url)
            response.raise_for_status()
        segments = _parse_subtitle_payload(extension, response.text)
        if not segments:
            raise TranscriptUnavailable("The fallback caption track contained no text.")
        return FetchedTranscript(
            title=(str(info.get("title") or title or video.video_id)),
            language=language,
            provider="yt-dlp",
            segments=segments,
        )


def _ytdlp_info(url: str) -> dict:
    options = {"quiet": True, "skip_download": True, "no_warnings": True}
    with YoutubeDL(options) as downloader:
        return downloader.extract_info(url, download=False)


def _select_subtitle_track(
    info: dict,
    languages: Sequence[str],
) -> tuple[str, str]:
    groups = (
        ("manual", info.get("subtitles") or {}),
        ("automatic", info.get("automatic_captions") or {}),
    )
    for source, tracks in groups:
        for language in languages:
            if language in tracks:
                return source, language
        for language in languages:
            root = language.split("-", 1)[0]
            match = next(
                (code for code in tracks if code.split("-", 1)[0] == root),
                None,
            )
            if match:
                return source, match
    for source, tracks in groups:
        if tracks:
            return source, next(iter(tracks))
    raise TranscriptUnavailable("No manual or automatic caption track was found.")


def _select_subtitle_url(
    info: dict,
    source: str,
    language: str,
) -> tuple[str, str]:
    group_name = "subtitles" if source == "manual" else "automatic_captions"
    tracks = info.get(group_name, {}).get(language, [])
    for extension in ("json3", "vtt", "srv3", "ttml"):
        match = next(
            (track for track in tracks if track.get("ext") == extension and track.get("url")),
            None,
        )
        if match:
            return extension, str(match["url"])
    fallback = next((track for track in tracks if track.get("url")), None)
    if fallback is None:
        raise TranscriptUnavailable("The selected caption track had no download URL.")
    return str(fallback.get("ext", "unknown")), str(fallback["url"])


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _parse_subtitle_payload(extension: str, payload: str) -> list[TranscriptSegment]:
    stripped = payload.strip()
    if not stripped:
        return []
    if extension == "json3" or stripped.startswith("{"):
        return _parse_json3(stripped)
    if extension == "vtt" or stripped.startswith("WEBVTT"):
        return _parse_vtt(stripped)
    return _parse_xml(stripped)


def _parse_json3(payload: str) -> list[TranscriptSegment]:
    data = json.loads(payload)
    segments: list[TranscriptSegment] = []
    for event in data.get("events", []):
        text = _normalize_text(
            "".join(part.get("utf8", "") for part in event.get("segs", []))
        )
        if text:
            segments.append(
                TranscriptSegment(
                    start=float(event.get("tStartMs", 0)) / 1000,
                    duration=float(event.get("dDurationMs", 0)) / 1000,
                    text=text,
                )
            )
    return segments


_VTT_TIMING = re.compile(
    r"(?P<start>\d\d:\d\d:\d\d\.\d{3}|\d\d:\d\d\.\d{3})\s+-->\s+"
    r"(?P<end>\d\d:\d\d:\d\d\.\d{3}|\d\d:\d\d\.\d{3})"
)


def _parse_vtt(payload: str) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    for block in re.split(r"\n\s*\n", payload):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timing_index = next(
            (index for index, line in enumerate(lines) if _VTT_TIMING.search(line)),
            None,
        )
        if timing_index is None:
            continue
        timing = _VTT_TIMING.search(lines[timing_index])
        if timing is None:
            continue
        text = _normalize_text(
            " ".join(
                re.sub(r"<[^>]+>", "", line) for line in lines[timing_index + 1 :]
            )
        )
        if text:
            start = _parse_vtt_time(timing.group("start"))
            end = _parse_vtt_time(timing.group("end"))
            segments.append(
                TranscriptSegment(start=start, duration=max(0, end - start), text=text)
            )
    return segments


def _parse_vtt_time(value: str) -> float:
    parts = value.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return int(parts[0]) * 60 + float(parts[1])


def _parse_xml(payload: str) -> list[TranscriptSegment]:
    root = ElementTree.fromstring(payload)
    segments: list[TranscriptSegment] = []
    for node in root.iter("text"):
        text = _normalize_text("".join(node.itertext()))
        if text:
            segments.append(
                TranscriptSegment(
                    start=float(node.attrib.get("start", 0)),
                    duration=float(node.attrib.get("dur", 0)),
                    text=text,
                )
            )
    for node in root.iter("p"):
        text = _normalize_text("".join(node.itertext()))
        if text and "t" in node.attrib:
            segments.append(
                TranscriptSegment(
                    start=float(node.attrib["t"]) / 1000,
                    duration=float(node.attrib.get("d", 0)) / 1000,
                    text=text,
                )
            )
    return segments
