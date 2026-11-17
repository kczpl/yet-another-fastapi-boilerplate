from collections.abc import Callable, Iterator
from importlib.util import find_spec
from typing import Any

from fastapi import APIRouter, Depends, FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from app.main import api

# The dependencies that authenticate a request. Add the auth dependency of your product here.
AUTH_DEPENDENCIES: set[Callable[..., Any]] = set()

# Routes without an authentication dependency. Each one has the reason.
PUBLIC_ROUTES = {
    ("GET", "/up"): "Liveness probe.",
    ("POST", "/api/v1/items"): "Example CRUD. Add authentication for your product.",
    ("GET", "/api/v1/items"): "Example CRUD. Add authentication for your product.",
    ("GET", "/api/v1/items/{item_id}"): "Example CRUD. Add authentication for your product.",
    ("PATCH", "/api/v1/items/{item_id}"): "Example CRUD. Add authentication for your product.",
    ("DELETE", "/api/v1/items/{item_id}"): "Example CRUD. Add authentication for your product.",
    ("POST", "/api/v1/items/{item_id}/summarize"): "Example AI route. Add authentication for your product.",
}
# Routes that exist only with an optional extra.
AI_ROUTES = {("POST", "/api/v1/items/{item_id}/summarize")}


def _dependency_calls(dependant: Dependant) -> set[Callable[..., Any] | None]:
    calls: set[Callable[..., Any] | None] = set()
    for dependency in dependant.dependencies:
        calls.add(dependency.call)
        calls |= _dependency_calls(dependency)
    return calls


def _routes(app: FastAPI) -> Iterator[tuple[str, str, Dependant]]:
    # Included routers are not flat in app.routes. The context gives the full path and
    # the dependencies of each router level.
    for context in iter_route_contexts(app.routes):
        if isinstance(context.original_route, APIRoute):
            for method in sorted(context.original_route.methods or ()):
                yield method, context.path or "", context.dependant


def _unauthenticated(app: FastAPI, auth: set[Callable[..., Any]]) -> set[tuple[str, str]]:
    return {(method, path) for method, path, dependant in _routes(app) if not _dependency_calls(dependant) & auth}


def test_finds_routes_without_an_auth_dependency():
    def authenticate() -> None:
        return None

    router = APIRouter(prefix="/v1")
    router.get("/open")(lambda: None)
    router.get("/closed", dependencies=[Depends(authenticate)])(lambda: None)
    app = FastAPI()
    app.include_router(router)

    assert _unauthenticated(app, {authenticate}) == {("GET", "/v1/open")}


def test_each_route_authenticates_or_is_listed_as_public():
    # A new route without authentication must not go public by accident.
    unlisted = _unauthenticated(api, AUTH_DEPENDENCIES) - set(PUBLIC_ROUTES)
    assert unlisted == set(), "Add an auth dependency, or list the route in PUBLIC_ROUTES with the reason."


def test_public_routes_exist():
    present = {(method, path) for method, path, _ in _routes(api)}
    optional = AI_ROUTES if find_spec("pydantic_ai") is None else set()
    assert set(PUBLIC_ROUTES) - present - optional == set()
