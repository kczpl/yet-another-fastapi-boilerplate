from importlib.util import find_spec

from fastapi import APIRouter

from app.features.items import routes

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(routes.router)

# Installing the AI extra enables its example endpoint without coupling core CRUD to Celery.
if find_spec("pydantic_ai") is not None:
    from app.features.items import ai_routes

    api_v1_router.include_router(ai_routes.router)
