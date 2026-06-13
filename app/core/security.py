import json
import time
import uuid

from fastapi.middleware.cors import CORSMiddleware
from guard.middleware import SecurityMiddleware
from guard.models import SecurityConfig
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import api_config
from app.core.errors import ERRORS
from app.core.logger import bind_context, clear_context, log

MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
MAX_UPLOAD_REQUEST_SIZE = 200 * 1024 * 1024  # 200MB (upload endpoints)
# Substring match — add upload route prefixes here that should allow large bodies.
LARGE_BODY_PATHS: tuple[str, ...] = ()
HEALTHCHECK_PATH = "/up"  # liveness probe — skip logging


def _get_header(headers: list[tuple[bytes, bytes]], name: bytes) -> str | None:
    for header_name, header_value in headers:
        if header_name == name:
            return header_value.decode("latin-1")
    return None


class LoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == HEALTHCHECK_PATH:
            await self.app(scope, receive, send)
            return

        clear_context()
        headers = scope["headers"]
        request_id = _get_header(headers, b"x-request-id") or str(uuid.uuid4())
        xff = _get_header(headers, b"x-forwarded-for")
        client = scope.get("client")
        client_ip = xff.split(",")[0].strip() if xff else (client[0] if client else "unknown")

        bind_context(request_id=request_id)
        status_code = 500
        start_time = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                raw_headers = list(message.get("headers", []))
                raw_headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": raw_headers}
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
                client_ip=client_ip,
            )


class RequestSizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope["method"] in ("POST", "PUT", "PATCH"):
            content_length = _get_header(scope["headers"], b"content-length")
            limit = MAX_UPLOAD_REQUEST_SIZE if any(p in scope["path"] for p in LARGE_BODY_PATHS) else MAX_REQUEST_SIZE
            if content_length and int(content_length) > limit:
                body = json.dumps({"error": ERRORS["file_too_large"], "data": {}}).encode("utf-8")
                await send(
                    {
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode("latin-1")),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return

        await self.app(scope, receive, send)


def get_guard_security_config() -> SecurityConfig:
    return SecurityConfig(
        rate_limit=1000,
        rate_limit_window=60,
        enforce_https=False,
        # CORS is handled by Starlette CORSMiddleware below so browser preflight
        # is answered before FastAPI route matching.
        enable_cors=False,
        block_cloud_providers=set(),
        blocked_user_agents=[],
        blocked_countries=[],
        whitelist=[],
        blacklist=[],
        enable_penetration_detection=False,
        security_headers={
            "enabled": True,
            "hsts": {"max_age": 31536000, "include_subdomains": True, "preload": True},
            "frame_options": "DENY",
            "content_type_options": "nosniff",
            "referrer_policy": "strict-origin-when-cross-origin",
            "cross_origin_resource_policy": "same-origin",
        },
    )


def setup_security_middleware(app) -> None:
    # Added last → outermost. Execution order (outer → inner):
    # CORS → Logging → RequestSizeLimit → guard SecurityMiddleware.
    app.add_middleware(SecurityMiddleware, config=get_guard_security_config())
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=api_config.CORS_ORIGINS,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=True,
        expose_headers=["Content-Length", "X-Request-ID"],
        max_age=86400,
    )
