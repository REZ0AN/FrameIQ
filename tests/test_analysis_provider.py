from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import app.services.analysis as analysis_module
from app.models.analysis import BatchSynthesis
from app.services.analysis import OpenAICompatibleAnalysisService
from app.settings import Settings


class FakeCompletions:
    def __init__(self, parsed: BatchSynthesis) -> None:
        self.parsed = parsed
        self.calls: list[dict[str, Any]] = []

    async def parse(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        message = SimpleNamespace(parsed=self.parsed)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeOpenAIClient:
    def __init__(self, completions: FakeCompletions) -> None:
        self.beta = SimpleNamespace(
            chat=SimpleNamespace(completions=completions),
        )


@pytest.mark.asyncio
async def test_gemini_uses_openai_compatible_structured_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Analyze only the supplied transcript.", encoding="utf-8")
    expected = BatchSynthesis(
        executive_summary="Combined summary.",
        common_ground=[],
        disagreements=[],
        unique_contributions=[],
        combined_implications=[],
        follow_up_questions=[],
    )
    completions = FakeCompletions(expected)
    client_arguments: dict[str, Any] = {}

    def build_client(**kwargs: Any) -> FakeOpenAIClient:
        client_arguments.update(kwargs)
        return FakeOpenAIClient(completions)

    monkeypatch.setattr(analysis_module, "AsyncOpenAI", build_client)
    service = OpenAICompatibleAnalysisService(
        api_key="gemini-key",
        model="gemini-2.5-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        prompt_path=prompt_path,
        concurrency=1,
        chunk_characters=1_000,
    )

    result = await service.synthesize([])

    assert result == expected
    assert client_arguments == {
        "api_key": "gemini-key",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "max_retries": 0,
    }
    request = completions.calls[0]
    assert request["model"] == "gemini-2.5-flash"
    assert request["messages"][0] == {
        "role": "system",
        "content": "Analyze only the supplied transcript.",
    }
    assert request["response_format"] is BatchSynthesis
    assert "reasoning_effort" not in request


def test_legacy_openai_settings_remain_supported() -> None:
    settings = Settings(
        _env_file=None,
        OPENAI_API_KEY="legacy-key",
        OPENAI_MODEL="legacy-model",
        OPENAI_BASE_URL="https://example.test/v1/",
    )

    assert settings.ai_api_key is not None
    assert settings.ai_api_key.get_secret_value() == "legacy-key"
    assert settings.ai_model == "legacy-model"
    assert settings.ai_base_url == "https://example.test/v1/"
