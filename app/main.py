from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.queue import queue_lifespan
from app.core.logger import setup_logging
from app.core.sentry import init_sentry
from app.core.exception_handlers import setup_exception_handlers

from app.api.v1 import auth, users

setup_logging()
init_sentry()


app = FastAPI(lifespan=queue_lifespan)

setup_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")


@app.get("/")
async def root() -> dict:
    return {"message": "hello"}


@app.get("/up")
async def up() -> dict:
    return {"message": "ok"}
