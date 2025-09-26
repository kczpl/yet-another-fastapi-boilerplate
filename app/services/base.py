from fastapi import Depends
from app.core.db import get_db
from app.core.queue import get_queue
from pgqueuer.queries import Queries
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession


class Service:
    def __init__(
        self,
        db: Annotated[AsyncSession, Depends(get_db, use_cache=True)],
    ):
        self.db = db


class ServiceWithQueue(Service):
    def __init__(
        self,
        db: Annotated[AsyncSession, Depends(get_db, use_cache=True)],
        queue: Annotated[Queries, Depends(get_queue, use_cache=True)],
    ):
        self.db = db
        self.queue = queue
