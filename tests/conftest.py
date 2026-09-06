from collections.abc import Sequence
from pathlib import Path

import pytest

from app.main import create_app
from app.models.analysis import (
    BatchSynthesis,
    EvidencePoint,
    ReasoningAssessment,
    VideoAnalysis,
)
from app.models.transcript import FetchedTranscript, TranscriptRecord, TranscriptSegment
from app.services.url_normalizer import NormalizedYouTubeUrl
from app.settings import Settings


class FakeTranscriptProvider:
    def __init__(self, failing_ids: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self.failing_ids = failing_ids or set()

    async def fetch(
        self,
        video: NormalizedYouTubeUrl,
        languages: Sequence[str],
    ) -> FetchedTranscript:
        self.calls.append(video.video_id)
        if video.video_id in self.failing_ids:
            raise RuntimeError("Captions unavailable for test video.")
        return FetchedTranscript(
            title=f"Video {video.video_id}",
            language=languages[0],
            provider="fake-captions",
            segments=[
                TranscriptSegment(start=0, duration=4, text="A test claim."),
                TranscriptSegment(start=4, duration=4, text="Supporting evidence."),
            ],
        )


class FakeAnalysisService:
    async def analyze_videos(
        self,
        transcripts: Sequence[TranscriptRecord],
    ) -> list[VideoAnalysis]:
        return [_analysis(transcript.video_id, transcript.title) for transcript in transcripts]

    async def synthesize(
        self,
        analyses: Sequence[VideoAnalysis],
    ) -> BatchSynthesis:
        return BatchSynthesis(
            executive_summary=f"Compared {len(analyses)} videos.",
            common_ground=["They use evidence."],
            disagreements=["No material disagreement."],
            unique_contributions=["Each video has a distinct example."],
            combined_implications=["Review the evidence together."],
            follow_up_questions=["What evidence is still missing?"],
        )


class FakeHealthService:
    def __init__(self, available: bool) -> None:
        self.available = available

    async def database_is_available(self) -> bool:
        return self.available


def _analysis(video_id: str, title: str) -> VideoAnalysis:
    point = EvidencePoint(
        statement="The speaker makes a test claim.",
        evidence="A test claim.",
        timestamp="00:00",
    )
    return VideoAnalysis(
        video_id=video_id,
        title=title,
        executive_summary="A concise test analysis.",
        key_takeaways=["A key takeaway."],
        highlights=[point],
        discussion_themes=["Testing"],
        impacts=["Reliable behavior"],
        strengths=["Clear evidence"],
        weaknesses=["Limited scope"],
        reasoning=ReasoningAssessment(
            overall="The reasoning is coherent but brief.",
            claims=[point],
            assumptions=["The example is representative."],
            logical_gaps=["No broader evidence is supplied."],
        ),
    )


@pytest.fixture
def fake_provider() -> FakeTranscriptProvider:
    return FakeTranscriptProvider()


@pytest.fixture
def fake_analysis() -> FakeAnalysisService:
    return FakeAnalysisService()


@pytest.fixture
def app_builder(tmp_path: Path):
    def build(
        provider: FakeTranscriptProvider | None = None,
        analysis: FakeAnalysisService | None = None,
        health: FakeHealthService | None = None,
    ):
        settings = Settings(
            database_path=tmp_path / "test.sqlite3",
            reaper_interval_seconds=0.02,
            sse_poll_seconds=0.01,
        )
        return create_app(
            settings=settings,
            transcript_provider=provider or FakeTranscriptProvider(),
            analysis_service=analysis or FakeAnalysisService(),
            health_service=health,
        )

    return build
