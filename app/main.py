from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import api_v1_router
from app.core.config import api_config
from app.core.db import AsyncDb, engine
from app.core.exceptions import setup_exception_handlers
from app.core.logger import log, setup_logging
from app.core.security import setup_security_middleware
from app.integrations.sentry.client import init_sentry

setup_logging()
init_sentry()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # uvicorn applies its own dictConfig after import time, clobbering our handlers —
    # re-run here to restore the unified format for uvicorn's own loggers.
    setup_logging()
    try:
        yield
    finally:
        await engine.dispose()


api = FastAPI(
    title="app",
    version=api_config.VERSION,
    docs_url="/docs" if api_config.SHOW_DOCS else None,
    redoc_url="/redoc" if api_config.SHOW_DOCS else None,
    openapi_url="/openapi.json" if api_config.SHOW_DOCS else None,
    lifespan=lifespan,
)

setup_exception_handlers(api)
api.include_router(api_v1_router)


@api.get("/up", include_in_schema=False)
async def up() -> Response:
    # Liveness probe — cheap on purpose (no DB round-trip); skipped by request logging.
    return Response(content="OK", media_type="text/plain")


@api.get("/ready", include_in_schema=False)
async def ready(db: AsyncDb) -> Response:
    # Readiness probe: a load balancer sends no requests to a process without the database.
    try:
        await db.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        log.warning("readiness_check_failed", error_type=type(error).__name__)
        return Response(content="Unavailable", status_code=503, media_type="text/plain")
    return Response(content="OK", media_type="text/plain")


app = setup_security_middleware(api)
