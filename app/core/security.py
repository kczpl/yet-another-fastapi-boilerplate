import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import api_config
from app.core.errors import ERRORS
from app.core.logger import bind_context, clear_context, log

MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
MAX_UPLOAD_REQUEST_SIZE = 200 * 1024 * 1024  # 200MB (upload endpoints)
# Substring match — add upload route prefixes here that should allow large bodies.
LARGE_BODY_PATHS: tuple[str, ...] = ()
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
    forwarded_for = Headers(scope=scope).get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
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
                _response_headers(message).append("X-Request-ID", request_id)
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


class RequestSizeLimitMiddleware:
    # Rejects oversized bodies from the Content-Length header before reading them.
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and self._too_large(scope):
            response = JSONResponse(status_code=413, content={"error": ERRORS["file_too_large"], "data": {}})
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)

    @staticmethod
    def _too_large(scope: Scope) -> bool:
        content_length = int(Headers(scope=scope).get("content-length") or 0)
        is_upload = any(path in scope["path"] for path in LARGE_BODY_PATHS)
        return content_length > (MAX_UPLOAD_REQUEST_SIZE if is_upload else MAX_REQUEST_SIZE)


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


def setup_security_middleware(app: FastAPI) -> None:
    # Added last → outermost. Execution order (outer → inner):
    # CORS → SecurityHeaders → Logging → RequestSizeLimit.
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=api_config.CORS_ORIGINS,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=True,
        expose_headers=["Content-Length", "X-Request-ID"],
        max_age=86400,
    )
