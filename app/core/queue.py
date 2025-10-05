from pgqueuer.queries import Queries
from fastapi import Request
from fastapi import FastAPI
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import asyncpg
from pgqueuer.db import AsyncpgDriver
from app.core.config import database_config


@asynccontextmanager
async def queue_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    conn = await asyncpg.connect(database_config.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"))
    try:
        driver = AsyncpgDriver(conn)
        app.extra["pgq_queries"] = Queries(driver=driver)
        yield
    finally:
        await conn.close()


def get_queue(request: Request) -> Queries:
    return request.app.extra["pgq_queries"]
