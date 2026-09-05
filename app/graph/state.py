from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class ResearchState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    run_id: str
    urls: list[str]
    transcript_references: list[dict]
    transcription_errors: list[dict]
    video_analyses: list[dict]
    batch_synthesis: dict | None
