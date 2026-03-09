import logging
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.metrics import metrics_registry
from app.db.migrations import run_migrations
from app.db.session import SessionLocal
from app.services.scheduler import SyncScheduler
from app.services.sync import SyncService

logger = logging.getLogger(__name__)


def _init_sentry_if_enabled() -> None:
    settings = get_settings()
    if not settings.sentry_dsn:
        return

    try:
        import sentry_sdk
    except ImportError:
        logger.warning("SENTRY_DSN is set, but sentry_sdk is not installed")
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )
    logger.info("Sentry initialized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    run_migrations(settings)

    sync_service = SyncService(session_factory=SessionLocal, settings=settings)
    scheduler = SyncScheduler(sync_service=sync_service, settings=settings)
    app.state.scheduler = scheduler

    await scheduler.start()
    logger.info("Application startup completed")

    try:
        yield
    finally:
        await scheduler.stop()
        logger.info("Application shutdown completed")


def create_app() -> FastAPI:
    configure_logging()
    _init_sentry_if_enabled()
    settings = get_settings()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.middleware("http")
    async def metrics_http_middleware(request: Request, call_next) -> Response:
        started = perf_counter()
        status_code = 500
        path = request.url.path
        method = request.method

        try:
            response = await call_next(request)
            status_code = response.status_code
            route = request.scope.get("route")
            if route and hasattr(route, "path"):
                path = str(route.path)
            return response
        finally:
            elapsed = perf_counter() - started
            labels = {"path": path, "method": method, "status": str(status_code)}
            metrics_registry.inc_counter("notion_graph_api_requests_total", labels=labels)
            metrics_registry.observe_histogram(
                "notion_graph_api_request_duration_seconds",
                elapsed,
                labels={"path": path, "method": method},
            )

    return app


app = create_app()
