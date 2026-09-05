from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CanvasDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    markdown_text: str
    updated_at: datetime


class CanvasUpdate(BaseModel):
    markdown_text: str = Field(min_length=1, max_length=500_000)

    @field_validator("markdown_text")
    @classmethod
    def require_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Canvas Markdown cannot be empty.")
        return value
