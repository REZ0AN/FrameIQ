from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "YouTube Research Canvas"
    database_path: Path = Path("data/youtube_analyzer.sqlite3")
    ai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AI_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
        ),
    )
    ai_model: str = Field(
        default="gpt-5.6-terra",
        validation_alias=AliasChoices("AI_MODEL", "OPENAI_MODEL"),
    )
    ai_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AI_BASE_URL", "OPENAI_BASE_URL"),
    )
    transcript_languages: tuple[str, ...] = ("en", "hi", "bn")
    max_batch_size: int = 10
    transcript_concurrency: int = 3
    analysis_concurrency: int = 2
    reaper_interval_seconds: float = 15.0
    sse_poll_seconds: float = 0.5
    transcript_chunk_characters: int = 50_000
