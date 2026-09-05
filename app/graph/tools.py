from langchain_core.tools import BaseTool, tool

from app.services.transcription import TranscriptionService


def create_transcription_tool(service: TranscriptionService) -> BaseTool:
    @tool
    async def transcript_youtube_urls(run_id: str, urls: list[str]) -> str:
        """Fetch and persist captions for one or more normalized YouTube URLs."""
        del urls  # URLs are validated and persisted before the background graph starts.
        outcome = await service.transcribe_run(run_id)
        return outcome.model_dump_json()

    return transcript_youtube_urls
