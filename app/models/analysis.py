from pydantic import BaseModel, ConfigDict, Field


class StrictAnalysisModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidencePoint(StrictAnalysisModel):
    statement: str
    evidence: str
    timestamp: str | None


class ReasoningAssessment(StrictAnalysisModel):
    overall: str
    claims: list[EvidencePoint]
    assumptions: list[str]
    logical_gaps: list[str]


class VideoAnalysis(StrictAnalysisModel):
    video_id: str
    title: str
    executive_summary: str
    key_takeaways: list[str]
    highlights: list[EvidencePoint]
    discussion_themes: list[str]
    impacts: list[str]
    strengths: list[str]
    weaknesses: list[str]
    reasoning: ReasoningAssessment


class ChunkAnalysis(StrictAnalysisModel):
    summary: str
    key_points: list[EvidencePoint]
    themes: list[str]
    impacts: list[str]
    strengths: list[str]
    weaknesses: list[str]
    assumptions: list[str]
    logical_gaps: list[str]


class BatchSynthesis(StrictAnalysisModel):
    executive_summary: str
    common_ground: list[str]
    disagreements: list[str]
    unique_contributions: list[str]
    combined_implications: list[str]
    follow_up_questions: list[str]


class ResearchReport(StrictAnalysisModel):
    videos: list[VideoAnalysis] = Field(default_factory=list)
    batch_synthesis: BatchSynthesis | None = None
