from sqlalchemy.ext.asyncio import AsyncSession


class Service:
    def __init__(self, db: AsyncSession):
        self.db = db
