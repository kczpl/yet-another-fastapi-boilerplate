from collections.abc import Sequence
from ipaddress import ip_network

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from structlog.testing import capture_logs

from app.core import security
from app.core.config import api_config
from app.core.security import (
    HEALTHCHECK_PATH,
    MAX_REQUEST_SIZE,
    SECURITY_HEADERS,
    FixedWindowRateLimit,
    IPNetwork,
    LoggingMiddleware,
    SecurityMiddleware,
    setup_security_middleware,
)

CLIENT_IP = "203.0.113.7"


class FakeClock:
    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


async def _ok(scope: Scope, receive: Receive, send: Send) -> None:
    # The route sets its own X-Frame-Options so the tests can see the override.
    await PlainTextResponse("ok", headers={"X-Frame-Options": "SAMEORIGIN"})(scope, receive, send)


def _secured(*, blocked_ips: Sequence[IPNetwork] = (), rate_limit: FixedWindowRateLimit | None = None) -> ASGIApp:
    return SecurityMiddleware(_ok, blocked_ips=blocked_ips, rate_limit=rate_limit)


async def _get(app: ASGIApp, path: str = "/", client_ip: str = CLIENT_IP, **headers: str) -> Response:
    transport = ASGITransport(app=app, client=(client_ip, 123))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=headers)


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

    @pytest.mark.parametrize("length", ["invalid", "-1"])
    async def test_invalid_content_length_is_400(self, client: AsyncClient, length: str):
        response = await client.post("/api/v1/items", content=b"{}", headers={"Content-Length": length})
        assert response.status_code == 400

    async def test_chunked_body_cannot_bypass_limit(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(security, "MAX_REQUEST_SIZE", 16)

        async def chunks():
            yield b'{"name":'
            yield b'"too much data"}'

        response = await client.post("/api/v1/items", content=chunks(), headers={"Content-Type": "application/json"})
        assert response.status_code == 413
        assert response.json() == {"error": "api.general.file_too_large", "data": {}}

    async def test_body_at_limit_is_accepted(self, client: AsyncClient, monkeypatch):
        body = b'{"name":"ok"}'
        monkeypatch.setattr(security, "MAX_REQUEST_SIZE", len(body))
        response = await client.post("/api/v1/items", content=body, headers={"Content-Type": "application/json"})
        assert response.status_code == 201


class TestLoggingMiddleware:
    async def test_request_is_logged_with_static_event(self):
        with capture_logs() as logs:
            await _get(LoggingMiddleware(_ok), "/items", **{"X-Request-ID": "req-1"})

        assert len(logs) == 1
        assert logs[0]["event"] == "http_request"
        assert logs[0]["status_code"] == 200
        assert logs[0]["client_ip"] == CLIENT_IP

    async def test_healthcheck_is_not_logged(self):
        with capture_logs() as logs:
            response = await _get(LoggingMiddleware(_ok), HEALTHCHECK_PATH)

        assert response.status_code == 200
        assert logs == []


class TestSecurityMiddleware:
    async def test_security_headers_replace_route_values(self):
        response = await _get(_secured())

        assert response.text == "ok"
        assert response.headers.get_list("x-frame-options") == ["DENY"]
        for name, value in SECURITY_HEADERS.items():
            assert response.headers[name] == value

    async def test_request_over_limit_gets_429_with_retry_after(self):
        app = _secured(rate_limit=FixedWindowRateLimit(2, 60, clock=FakeClock(125.0)))

        statuses = [(await _get(app)).status_code for _ in range(2)]
        response = await _get(app)

        assert statuses == [200, 200]
        assert response.status_code == 429
        assert response.headers["retry-after"] == "55"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.json() == {"error": "api.general.rate_limit_exceeded", "data": {}}

    async def test_each_client_has_its_own_count(self):
        app = _secured(rate_limit=FixedWindowRateLimit(1, 60, clock=FakeClock(125.0)))

        first = await _get(app, client_ip="203.0.113.7")
        other_client = await _get(app, client_ip="203.0.113.8")
        repeated = await _get(app, client_ip="203.0.113.7")

        assert [first.status_code, other_client.status_code, repeated.status_code] == [200, 200, 429]

    async def test_new_window_resets_the_count(self):
        clock = FakeClock(125.0)
        app = _secured(rate_limit=FixedWindowRateLimit(1, 60, clock=clock))

        await _get(app)
        limited = await _get(app)
        clock.now = 180.0
        next_window = await _get(app)

        assert limited.status_code == 429
        assert next_window.status_code == 200

    async def test_healthcheck_is_not_rate_limited(self):
        app = _secured(rate_limit=FixedWindowRateLimit(1, 60, clock=FakeClock(125.0)))

        statuses = [(await _get(app, HEALTHCHECK_PATH)).status_code for _ in range(3)]

        assert statuses == [200, 200, 200]

    async def test_blocked_ip_gets_403_before_the_app(self):
        response = await _get(_secured(blocked_ips=[ip_network("203.0.113.0/24")]))

        assert response.status_code == 403
        assert response.json() == {"error": "api.general.ip_blocked", "data": {}}
        assert response.headers["x-frame-options"] == "DENY"

    async def test_client_outside_blocked_networks_reaches_the_app(self):
        response = await _get(_secured(blocked_ips=[ip_network("198.51.100.0/24"), ip_network("2001:db8::/32")]))

        assert response.status_code == 200
        assert response.text == "ok"

    async def test_blocked_websocket_is_closed_before_the_handshake(self):
        sent: list[Message] = []

        async def receive() -> Message:
            return {"type": "websocket.connect"}

        async def send(message: Message) -> None:
            sent.append(message)

        scope = {"type": "websocket", "path": "/ws", "headers": [], "client": (CLIENT_IP, 123)}
        await _secured(blocked_ips=[ip_network("203.0.113.7/32")])(scope, receive, send)

        assert sent == [{"type": "websocket.close", "code": 1008}]


class TestSecuritySetup:
    # A throwaway app per test: setup reads api_config when it builds the middleware.
    @staticmethod
    def _app() -> ASGIApp:
        app = FastAPI()

        @app.get("/ping")
        async def ping() -> dict:
            return {}

        return setup_security_middleware(app)

    async def test_429_keeps_cors_request_id_and_security_headers(self, monkeypatch):
        monkeypatch.setattr(api_config, "RATE_LIMIT_PER_MINUTE", 1)
        app = self._app()
        headers = {"Origin": "http://localhost:3000", "X-Request-ID": "limited"}

        await _get(app, "/ping", **headers)
        response = await _get(app, "/ping", **headers)

        assert response.status_code == 429
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert response.headers["x-request-id"] == "limited"
        assert response.headers["x-content-type-options"] == "nosniff"

    async def test_blocked_ips_come_from_config(self, monkeypatch):
        monkeypatch.setattr(api_config, "BLOCKED_IPS", [ip_network("203.0.113.0/24")])

        blocked = await _get(self._app(), "/ping")
        allowed = await _get(self._app(), "/ping", client_ip="198.51.100.1")

        assert blocked.status_code == 403
        assert allowed.status_code == 200
