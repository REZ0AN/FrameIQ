from pydantic import BaseModel, ConfigDict

from app.models.run import AnalysisRun
from app.models.transcript import TranscriptSummary


class DashboardView(BaseModel):
    model_config = ConfigDict(frozen=True)

    runs: list[AnalysisRun]
    transcripts: list[TranscriptSummary]
