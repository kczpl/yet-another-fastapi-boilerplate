from app.core.db import AsyncDb


class Service:
    def __init__(self, db: AsyncDb):
        self.db = db
