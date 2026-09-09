from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from app.api import api_v1_router
from app.core.config import api_config
from app.core.db import engine
from app.core.exceptions import setup_exception_handlers
from app.core.logger import setup_logging
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


app = setup_security_middleware(api)
