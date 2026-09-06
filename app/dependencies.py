from dataclasses import dataclass

from fastapi import Request

from app.services.canvases import CanvasService
from app.services.dashboard import DashboardService
from app.services.executor import RunExecutor
from app.services.health import HealthService
from app.services.runs import RunService
from app.settings import Settings


@dataclass(frozen=True)
class AppContainer:
    settings: Settings
    runs: RunService
    executor: RunExecutor
    health: HealthService
    dashboard: DashboardService
    canvases: CanvasService


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def get_run_service(request: Request) -> RunService:
    return get_container(request).runs


def get_run_executor(request: Request) -> RunExecutor:
    return get_container(request).executor


def get_health_service(request: Request) -> HealthService:
    return get_container(request).health


def get_dashboard_service(request: Request) -> DashboardService:
    return get_container(request).dashboard


def get_canvas_service(request: Request) -> CanvasService:
    return get_container(request).canvases
