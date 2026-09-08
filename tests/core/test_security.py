from httpx import AsyncClient

from app.core.security import MAX_REQUEST_SIZE


class TestMiddleware:
    async def test_request_id_is_generated(self, client: AsyncClient):
        resp = await client.get("/api/v1/items")

        assert resp.headers["x-request-id"]

    async def test_request_id_is_propagated(self, client: AsyncClient):
        resp = await client.get("/api/v1/items", headers={"X-Request-ID": "req-123"})

        assert resp.headers["x-request-id"] == "req-123"

    async def test_security_headers_are_set(self, client: AsyncClient):
        resp = await client.get("/api/v1/items")

        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"
        assert resp.headers["strict-transport-security"].startswith("max-age=")

    async def test_oversized_body_is_rejected(self, client: AsyncClient):
        headers = {"Content-Length": str(MAX_REQUEST_SIZE + 1)}

        resp = await client.post("/api/v1/items", content=b"{}", headers=headers)

        assert resp.status_code == 413
        assert resp.json()["error"] == "api.general.file_too_large"
