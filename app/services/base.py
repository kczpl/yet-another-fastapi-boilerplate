from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db


class Service:
    def __init__(self, db: Annotated[AsyncSession, Depends(get_db, use_cache=True)]):
        self.db = db
