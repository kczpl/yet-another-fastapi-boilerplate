import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import api_config
from app.core.errors import ERRORS
from app.core.logger import bind_context, clear_context, log

MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
HEALTHCHECK_PATH = "/up"  # liveness probe — skip logging

# Browser-facing hardening headers. Rate limiting, IP filtering and WAF rules
# belong at the edge (load balancer / reverse proxy), not in the app process.
SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


def _response_headers(message: Message) -> MutableHeaders:
    message.setdefault("headers", [])
    return MutableHeaders(scope=message)


def _client_ip(scope: Scope) -> str:
    # Uvicorn resolves forwarded headers only for explicitly trusted proxies.
    client = scope.get("client")
    return client[0] if client else "unknown"


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
                f"{scope['method']} {scope['path']} {status_code} ({duration:.3f}s)",
                method=scope["method"],
                path=scope["path"],
                status_code=status_code,
                duration=f"{duration:.3f}s",
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
            response = JSONResponse(status_code=400, content={"error": ERRORS["bad_request"], "data": {}})
            await response(scope, receive, send)
            return

        if content_length > MAX_REQUEST_SIZE:
            response = JSONResponse(status_code=413, content={"error": ERRORS["file_too_large"], "data": {}})
            await response(scope, receive, send)
            return

        bytes_read = 0

        async def limited_receive() -> Message:
            nonlocal bytes_read
            message = await receive()
            bytes_read += len(message.get("body", b""))
            if bytes_read > MAX_REQUEST_SIZE:
                raise HTTPException(status_code=413, detail="Request body too large")
            return message

        await self.app(scope, limited_receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                _response_headers(message).update(SECURITY_HEADERS)
            await send(message)

        await self.app(scope, receive, send_wrapper)


def setup_security_middleware(app: FastAPI) -> ASGIApp:
    # Body errors are handled inside FastAPI. Response wrappers surround the
    # entire app so even ServerErrorMiddleware's 500 response gets their headers.
    app.add_middleware(RequestSizeLimitMiddleware)
    return CORSMiddleware(
        SecurityHeadersMiddleware(LoggingMiddleware(app)),
        allow_origins=api_config.CORS_ORIGINS,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=True,
        expose_headers=["Content-Length", "X-Request-ID"],
        max_age=86400,
    )
