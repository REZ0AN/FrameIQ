from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RunMode(StrEnum):
    SINGLE = "single"
    BATCH = "batch"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    INTERRUPTED = "interrupted"

    @property
    def terminal(self) -> bool:
        return self in {
            self.COMPLETED,
            self.COMPLETED_WITH_ERRORS,
            self.FAILED,
            self.INTERRUPTED,
        }


class RunItemStatus(StrEnum):
    QUEUED = "queued"
    COMPLETED = "completed"
    FAILED = "failed"


class NewRunItem(BaseModel):
    position: int = Field(ge=0)
    source_url: str
    canonical_url: str | None = None
    url_hash: str | None = None
    video_id: str | None = None
    status: RunItemStatus = RunItemStatus.QUEUED
    error: str | None = None


class RunItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    run_id: str
    position: int
    source_url: str
    canonical_url: str | None
    url_hash: str | None
    video_id: str | None
    transcript_id: str | None
    status: RunItemStatus
    error: str | None


class AnalysisRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    input_value: str
    mode: RunMode
    status: RunStatus
    total_count: int
    success_count: int
    error_count: int
    error: str | None
    heartbeat_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RunStatusEvent(BaseModel):
    run_id: str
    status: RunStatus
    success_count: int
    error_count: int
    total_count: int
    message: str
    terminal: bool
