from fastapi import FastAPI
from app.core.logger import setup_logging
from app.core.sentry import init_sentry
from app.core.exceptions import setup_exception_handlers
from app.core.security import setup_security_middleware
from app.core.config import config

from app.api.v1 import auth, users

setup_logging()
init_sentry()

# Hide docs in production and staging
SHOW_DOCS_ENVIRONMENT = ("development", "local")
app_configs = {
    "title": "FastAPI Boilerplate",
    "version": config.VERSION,
}
if config.ENVIRONMENT not in SHOW_DOCS_ENVIRONMENT:
    app_configs["openapi_url"] = None  # Hide docs

app = FastAPI(**app_configs)

setup_exception_handlers(app)
setup_security_middleware(app)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")


@app.get("/")
async def root() -> dict:
    return {"message": "hello"}


@app.get("/up")
async def up() -> dict:
    return {"message": "ok"}
