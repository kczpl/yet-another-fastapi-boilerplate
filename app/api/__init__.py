from fastapi import APIRouter

from app.features.items.routes import items

# Aggregates feature routers under the versioned prefix. Add new feature routers here.
api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(items.router)
