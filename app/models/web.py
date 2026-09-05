from pydantic import BaseModel, Field, field_validator

from app.models.analysis import ResearchReport
from app.models.run import AnalysisRun, RunItem
from app.models.transcript import TranscriptRecord


class AnalyzeSubmission(BaseModel):
    urls: str = Field(min_length=1, max_length=8_000)

    @field_validator("urls")
    @classmethod
    def require_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Enter at least one YouTube URL.")
        return stripped


class ResultsView(BaseModel):
    run: AnalysisRun
    items: list[RunItem]
    transcripts: list[TranscriptRecord]
    report: ResearchReport | None
