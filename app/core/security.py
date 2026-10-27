import math
import time
import uuid
from collections.abc import Callable, Sequence
from ipaddress import IPv4Network, IPv6Network, ip_address

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import api_config
from app.core.exceptions import APIException, error_response
from app.core.logger import bind_context, clear_context, log

MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
HEALTHCHECK_PATH = "/up"  # liveness probe — skip logging and rate limit
RATE_LIMIT_WINDOW_SECONDS = 60

# Each HTTP response gets these headers. They replace a route value with the same name.
# No CSP or COEP: they block the CDN assets of /docs. Add them when the API serves no HTML.
SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "X-Permitted-Cross-Domain-Policies": "none",
}

type IPNetwork = IPv4Network | IPv6Network


def _response_headers(message: Message) -> MutableHeaders:
    message.setdefault("headers", [])
    return MutableHeaders(scope=message)


def _client_ip(scope: Scope) -> str | None:
    # Uvicorn takes the client from X-Forwarded-For only for the proxies in FORWARDED_ALLOW_IPS.
    client = scope.get("client")
    return client[0] if client else None


def _in_networks(address: str | None, networks: Sequence[IPNetwork]) -> bool:
    if not address or not networks:
        return False
    try:
        parsed = ip_address(address)
    except ValueError:
        return False
    return any(parsed in network for network in networks)


class LoggingMiddleware:
    # Generates/propagates X-Request-ID, binds it to the log context and logs one
    # line per request with method, path, status, duration and client IP.
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == HEALTHCHECK_PATH:
            await self.app(scope, receive, send)
            return

        clear_context()
        request_id = Headers(scope=scope).get("x-request-id") or str(uuid.uuid4())
        bind_context(request_id=request_id)
        status_code = 500
        start_time = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                _response_headers(message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start_time
            log.info(
                "http_request",
                method=scope["method"],
                path=scope["path"],
                status_code=status_code,
                duration_ms=round(duration * 1000, 1),
                client_ip=_client_ip(scope),
            )
            clear_context()


class RequestSizeLimitMiddleware:
    # Check Content-Length early, then count actual bytes (including chunked input).
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        try:
            content_length = int(Headers(scope=scope).get("content-length") or 0)
            if content_length < 0:
                raise ValueError("negative content length")
        except ValueError:
            await error_response(400, "bad_request", {})(scope, receive, send)
            return

        if content_length > MAX_REQUEST_SIZE:
            await error_response(413, "file_too_large", {})(scope, receive, send)
            return

        bytes_read = 0

        async def limited_receive() -> Message:
            nonlocal bytes_read
            message = await receive()
            bytes_read += len(message.get("body", b""))
            if bytes_read > MAX_REQUEST_SIZE:
                # FastAPI re-raises an HTTPException from body parsing and turns other errors into 400.
                raise APIException("file_too_large", 413)
            return message

        await self.app(scope, limited_receive, send)


class FixedWindowRateLimit:
    # A new window drops all counts, so memory holds only the clients of one window.
    def __init__(self, limit: int, window_seconds: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._clock = clock
        self._window = -1
        self._counts: dict[str, int] = {}

    def retry_after(self, key: str) -> int | None:
        now = self._clock()
        window = int(now // self._window_seconds)
        if window != self._window:
            self._window = window
            self._counts.clear()
        count = self._counts.get(key, 0) + 1
        self._counts[key] = count
        if count <= self._limit:
            return None
        return math.ceil((window + 1) * self._window_seconds - now)


class SecurityMiddleware:
    # Blocks client networks, limits requests per client IP and adds SECURITY_HEADERS.
    # The counts live in this process, so N processes allow N times the limit.
    def __init__(
        self,
        app: ASGIApp,
        *,
        blocked_ips: Sequence[IPNetwork] = (),
        rate_limit: FixedWindowRateLimit | None = None,
    ) -> None:
        self.app = app
        self._blocked_ips = tuple(blocked_ips)
        self._rate_limit = rate_limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket" and _in_networks(_client_ip(scope), self._blocked_ips):
            # A close before the handshake makes the server answer 403.
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        send = _with_security_headers(send)
        client_ip = _client_ip(scope)
        if _in_networks(client_ip, self._blocked_ips):
            await error_response(403, "ip_blocked", {})(scope, receive, send)
            return
        if retry_after := self._retry_after(scope["path"], client_ip):
            response = error_response(429, "rate_limit_exceeded", {}, headers={"Retry-After": str(retry_after)})
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _retry_after(self, path: str, client_ip: str | None) -> int | None:
        if self._rate_limit is None or path == HEALTHCHECK_PATH:
            return None
        return self._rate_limit.retry_after(client_ip or "unknown")


def _with_security_headers(send: Send) -> Send:
    async def send_with_headers(message: Message) -> None:
        if message["type"] == "http.response.start":
            _response_headers(message).update(SECURITY_HEADERS)
        await send(message)

    return send_with_headers


def setup_security_middleware(app: FastAPI) -> ASGIApp:
    # Body errors are handled inside FastAPI. The wrappers surround the entire app,
    # so even ServerErrorMiddleware's 500 response gets CORS, X-Request-ID and SECURITY_HEADERS.
    app.add_middleware(RequestSizeLimitMiddleware)
    limit = api_config.RATE_LIMIT_PER_MINUTE
    rate_limit = FixedWindowRateLimit(limit, RATE_LIMIT_WINDOW_SECONDS) if limit else None
    return CORSMiddleware(
        LoggingMiddleware(SecurityMiddleware(app, blocked_ips=api_config.BLOCKED_IPS, rate_limit=rate_limit)),
        allow_origins=api_config.CORS_ORIGINS,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=True,
        expose_headers=["Content-Length", "X-Request-ID"],
        max_age=86400,
    )
