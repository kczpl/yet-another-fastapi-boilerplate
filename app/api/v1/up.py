from fastapi import Depends
from app.core.db import get_db, AsyncSession
from fastapi import APIRouter
from sqlalchemy import text

router = APIRouter()


@router.get("/up")
async def up(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
