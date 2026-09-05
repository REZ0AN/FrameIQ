from dataclasses import dataclass

from app.repositories.protocols import TranscriptRepository
from app.services.analysis import AnalysisService


@dataclass(frozen=True)
class AnalysisNodeContext:
    transcripts: TranscriptRepository
    analysis: AnalysisService
