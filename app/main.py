from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.dependencies import AppContainer
from app.graph.builder import build_research_graph
from app.repositories.database import initialize_database
from app.repositories.sqlite_canvases import SQLiteCanvasRepository
from app.repositories.sqlite_runs import SQLiteRunRepository
from app.repositories.sqlite_transcripts import SQLiteTranscriptRepository
from app.routes import canvas, dashboard, events, health, input, results
from app.services.analysis import AnalysisService, OpenAICompatibleAnalysisService
from app.services.canvases import CanvasService
from app.services.dashboard import DashboardService
from app.services.executor import RunExecutor
from app.services.health import HealthService, SQLiteHealthService
from app.services.markdown import MarkdownRenderer
from app.services.reaper import ThreadReaper
from app.services.runs import RunService
from app.services.transcription import TranscriptProvider, TranscriptionService
from app.services.youtube import YouTubeCaptionProvider
from app.settings import Settings


APP_DIRECTORY = Path(__file__).resolve().parent


def _format_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def create_app(
    settings: Settings | None = None,
    transcript_provider: TranscriptProvider | None = None,
    analysis_service: AnalysisService | None = None,
    health_service: HealthService | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database_path = resolved_settings.database_path.resolve()
        await initialize_database(database_path)
        run_repository = SQLiteRunRepository(database_path)
        transcript_repository = SQLiteTranscriptRepository(database_path)
        canvas_repository = SQLiteCanvasRepository(database_path)
        await run_repository.interrupt_unfinished()

        provider = transcript_provider or YouTubeCaptionProvider()
        analysis = analysis_service or OpenAICompatibleAnalysisService(
            api_key=(
                resolved_settings.ai_api_key.get_secret_value()
                if resolved_settings.ai_api_key
                else None
            ),
            model=resolved_settings.ai_model,
            base_url=resolved_settings.ai_base_url,
            prompt_path=APP_DIRECTORY / "prompts" / "research_report.txt",
            concurrency=resolved_settings.analysis_concurrency,
            chunk_characters=resolved_settings.transcript_chunk_characters,
        )
        transcription = TranscriptionService(
            transcripts=transcript_repository,
            runs=run_repository,
            provider=provider,
            languages=resolved_settings.transcript_languages,
            concurrency=resolved_settings.transcript_concurrency,
        )

        async with AsyncSqliteSaver.from_conn_string(str(database_path)) as checkpointer:
            await checkpointer.setup()
            graph = build_research_graph(
                transcription=transcription,
                transcripts=transcript_repository,
                analysis=analysis,
                checkpointer=checkpointer,
            )
            run_service = RunService(
                runs=run_repository,
                transcripts=transcript_repository,
                graph=graph,
                max_batch_size=resolved_settings.max_batch_size,
            )
            executor = RunExecutor(graph=graph, runs=run_repository)
            reaper = ThreadReaper(
                runs=run_repository,
                executor=executor,
                interval_seconds=resolved_settings.reaper_interval_seconds,
            )
            application.state.container = AppContainer(
                settings=resolved_settings,
                runs=run_service,
                executor=executor,
                health=health_service or SQLiteHealthService(database_path),
                dashboard=DashboardService(
                    runs=run_repository,
                    transcripts=transcript_repository,
                ),
                canvases=CanvasService(
                    runs=run_repository,
                    documents=canvas_repository,
                    checkpoints=checkpointer,
                    markdown=MarkdownRenderer(),
                ),
            )
            reaper.start()
            try:
                yield
            finally:
                await reaper.stop()
                await executor.shutdown()

    application = FastAPI(title=resolved_settings.app_name, lifespan=lifespan)
    application.state.templates = Jinja2Templates(directory=APP_DIRECTORY / "templates")
    application.state.templates.env.globals["format_timestamp"] = _format_timestamp
    application.mount(
        "/static",
        StaticFiles(directory=APP_DIRECTORY / "static"),
        name="static",
    )
    application.include_router(input.router)
    application.include_router(results.router)
    application.include_router(canvas.router)
    application.include_router(events.router)
    application.include_router(health.router)
    application.include_router(dashboard.router)
    return application


app = create_app()
