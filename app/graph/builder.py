from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.graph.context import AnalysisNodeContext
from app.graph.nodes import (
    collect_transcription,
    make_analysis_node,
    make_dispatch_node,
    make_synthesis_node,
    should_synthesize,
)
from app.graph.state import ResearchState
from app.repositories.protocols import TranscriptRepository
from app.services.analysis import AnalysisService
from app.services.transcription import TranscriptionService
from app.graph.tools import create_transcription_tool


def build_research_graph(
    transcription: TranscriptionService,
    transcripts: TranscriptRepository,
    analysis: AnalysisService,
    checkpointer: BaseCheckpointSaver,
):
    transcript_tool = create_transcription_tool(transcription)
    context = AnalysisNodeContext(transcripts=transcripts, analysis=analysis)
    builder = StateGraph(ResearchState)
    builder.add_node("dispatch_transcription", make_dispatch_node(transcript_tool.name))
    builder.add_node("transcription_tool", ToolNode([transcript_tool]))
    builder.add_node("collect_transcription", collect_transcription)
    builder.add_node("analyze_videos", make_analysis_node(context))
    builder.add_node("synthesize_batch", make_synthesis_node(context))
    builder.add_edge(START, "dispatch_transcription")
    builder.add_edge("dispatch_transcription", "transcription_tool")
    builder.add_edge("transcription_tool", "collect_transcription")
    builder.add_edge("collect_transcription", "analyze_videos")
    builder.add_conditional_edges(
        "analyze_videos",
        should_synthesize,
        {"synthesize": "synthesize_batch", "finish": END},
    )
    builder.add_edge("synthesize_batch", END)
    return builder.compile(checkpointer=checkpointer)
