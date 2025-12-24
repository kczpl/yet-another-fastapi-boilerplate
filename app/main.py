from fastapi import FastAPI

# from app.api.v1 import auth, up, users
from app.core.config import config
from app.core.exceptions import setup_exception_handlers
from app.core.logger import setup_logging
from app.core.security import setup_security_middleware
from app.core.sentry import init_sentry

setup_logging()
init_sentry()

app = FastAPI(
    title="Numonis API",
    version=config.VERSION,
    docs_url="/docs" if config.SHOW_DOCS else None,
    redoc_url="/redoc" if config.SHOW_DOCS else None,
)

setup_exception_handlers(app)
setup_security_middleware(app)

# app.include_router(up.router)
# app.include_router(auth.router, prefix="/api/v1")
# app.include_router(users.router, prefix="/api/v1")


@app.get("/")
async def root() -> dict:
    return {"message": "hello"}
