from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import raise_conflict, setup_exception_handlers


def _app_with_failing_routes() -> FastAPI:
    # A throwaway app so the global one is not mutated by test-only routes.
    failing_app = FastAPI()
    setup_exception_handlers(failing_app)

    @failing_app.get("/conflict")
    async def conflict():
        raise_conflict("conflict", reason="taken")

    @failing_app.get("/boom")
    async def boom():
        raise RuntimeError("boom")

    return failing_app


async def _get(path: str):
    # raise_app_exceptions=False: Starlette re-raises unhandled errors after the
    # 500 response is sent, which would otherwise surface in the test itself.
    transport = ASGITransport(app=_app_with_failing_routes(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


class TestErrorEnvelope:
    async def test_api_exception_carries_i18n_key_and_kwargs(self):
        resp = await _get("/conflict")

        assert resp.status_code == 409
        assert resp.json() == {"error": "api.general.conflict", "data": {"reason": "taken"}}

    async def test_unhandled_exception_returns_generic_500(self):
        resp = await _get("/boom")

        assert resp.status_code == 500
        assert resp.json() == {"error": "api.general.internal_server_error", "data": {}}

    async def test_unknown_route_uses_envelope(self, client: AsyncClient):
        resp = await client.get("/api/v1/nope")

        assert resp.status_code == 404
        assert resp.json() == {"error": "api.general.not_found", "data": {"detail": "Not Found"}}

    async def test_method_not_allowed_uses_envelope(self, client: AsyncClient):
        resp = await client.delete("/api/v1/items")

        assert resp.status_code == 405
        assert resp.json()["error"] == "api.general.method_not_allowed"

    async def test_missing_field_maps_to_required_parameter_missing(self, client: AsyncClient):
        resp = await client.post("/api/v1/items", json={})

        assert resp.status_code == 422
        details = resp.json()["data"]["details"]
        assert details == [
            {"field": "body.name", "message": "api.general.required_parameter_missing", "type": "missing"}
        ]
