import asyncio
import json
from collections.abc import Callable

from langchain_core.messages import AIMessage, ToolMessage

from app.graph.context import AnalysisNodeContext
from app.graph.state import ResearchState
from app.models.analysis import ResearchReport, VideoAnalysis
from app.models.transcript import TranscriptionOutcome


def make_dispatch_node(tool_name: str) -> Callable:
    async def dispatch_transcription(state: ResearchState) -> dict:
        run_id = state["run_id"]
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": tool_name,
                            "args": {"run_id": run_id, "urls": state["urls"]},
                            "id": f"transcribe-{run_id}",
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        }

    return dispatch_transcription


async def collect_transcription(state: ResearchState) -> dict:
    tool_message = next(
        (message for message in reversed(state["messages"]) if isinstance(message, ToolMessage)),
        None,
    )
    if tool_message is None:
        raise RuntimeError("The transcription tool did not return a result.")
    content = tool_message.content
    if not isinstance(content, str):
        content = json.dumps(content)
    outcome = TranscriptionOutcome.model_validate_json(content)
    return {
        "transcript_references": [
            reference.model_dump() for reference in outcome.transcripts
        ],
        "transcription_errors": [error.model_dump() for error in outcome.errors],
    }


def make_analysis_node(context: AnalysisNodeContext) -> Callable:
    async def analyze_videos(state: ResearchState) -> dict:
        records = await asyncio.gather(
            *(
                context.transcripts.get_by_id(reference["transcript_id"])
                for reference in state.get("transcript_references", [])
            )
        )
        available = [record for record in records if record is not None]
        if not available:
            return {"video_analyses": []}
        analyses = await context.analysis.analyze_videos(available)
        payload = [analysis.model_dump() for analysis in analyses]
        return {
            "video_analyses": payload,
            "messages": [
                AIMessage(
                    content=json.dumps(
                        {"video_analyses": payload},
                        ensure_ascii=False,
                    )
                )
            ],
        }

    return analyze_videos


def should_synthesize(state: ResearchState) -> str:
    return "synthesize" if len(state.get("video_analyses", [])) > 1 else "finish"


def make_synthesis_node(context: AnalysisNodeContext) -> Callable:
    async def synthesize_batch(state: ResearchState) -> dict:
        analyses = [
            VideoAnalysis.model_validate(analysis)
            for analysis in state.get("video_analyses", [])
        ]
        synthesis = await context.analysis.synthesize(analyses)
        return {
            "batch_synthesis": synthesis.model_dump(),
            "messages": [
                AIMessage(
                    content=json.dumps(
                        {"batch_synthesis": synthesis.model_dump()},
                        ensure_ascii=False,
                    )
                )
            ],
        }

    return synthesize_batch


def report_from_state(state: ResearchState) -> ResearchReport:
    return ResearchReport(
        videos=[
            VideoAnalysis.model_validate(analysis)
            for analysis in state.get("video_analyses", [])
        ],
        batch_synthesis=state.get("batch_synthesis"),
    )
