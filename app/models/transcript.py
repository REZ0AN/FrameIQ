from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TranscriptSegment(BaseModel):
    start: float = Field(ge=0)
    duration: float = Field(ge=0)
    text: str = Field(min_length=1)


class TranscriptRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    source_url: str
    canonical_url: str
    url_hash: str
    video_id: str
    title: str
    language: str
    provider: str
    text: str
    segments: list[TranscriptSegment]
    created_at: datetime


class TranscriptSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    canonical_url: str
    video_id: str
    title: str
    language: str
    provider: str
    created_at: datetime
    latest_run_id: str | None


class NewTranscript(BaseModel):
    source_url: str
    canonical_url: str
    url_hash: str
    video_id: str
    title: str
    language: str
    provider: str
    text: str
    segments: list[TranscriptSegment]


class FetchedTranscript(BaseModel):
    title: str
    language: str
    provider: str
    segments: list[TranscriptSegment]


class TranscriptReference(BaseModel):
    transcript_id: str
    source_url: str
    canonical_url: str
    video_id: str
    title: str
    cached: bool


class TranscriptionFailure(BaseModel):
    source_url: str
    error: str


class TranscriptionOutcome(BaseModel):
    transcripts: list[TranscriptReference] = Field(default_factory=list)
    errors: list[TranscriptionFailure] = Field(default_factory=list)
